"""Read-only existing-project G1 capture controls; never claims runtime acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from storage_guard import ensure_guarded

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compiler", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--wargame-root", type=Path, required=True)
    p.add_argument("--seeder-root", type=Path, required=True)
    args = p.parse_args()
    ensure_guarded()
    args.output.mkdir(parents=True, exist_ok=False)
    commands = []
    reports = []
    def run(label, argv, success=True, env=None, cwd=None):
        with (args.output/(label+".stdout.log")).open("xb") as out, (args.output/(label+".stderr.log")).open("xb") as err:
            result = subprocess.run([str(v) for v in argv], stdout=out, stderr=err, timeout=30, env=env, cwd=cwd)
        commands.append(dict(label=label, argv=[str(v) for v in argv], exitCode=result.returncode))
        (args.output/"commands.json").write_text(json.dumps(commands,indent=2)+"\n")
        assert (result.returncode == 0) == success, label
        return (args.output/(label+".stdout.log")).read_bytes()
    for name, root, inputs, components in [
        ("wargame", args.wargame_root, ["Cargo.toml","Cargo.lock","src/contracts.rs","src/api.rs","web/package.json","web/next.config.ts","web/src/app/page.tsx"], [
            dict(id="service",kind="cargo-package",root=".",entrypoints=["Cargo.toml","src/api.rs"]),
            dict(id="web",kind="next-app",root="web",entrypoints=["web/package.json","web/src/app/page.tsx"]),
            dict(id="types",kind="contracts",root="src",entrypoints=["src/contracts.rs"])]),
        ("seeder", args.seeder_root, ["package.json","packages/web/package.json","packages/web/next.config.ts"], [
            dict(id="web",kind="next-app",root="packages/web",entrypoints=["packages/web/package.json","packages/web/next.config.ts"]),
            dict(id="workspace",kind="configuration",root=".",entrypoints=["package.json"])])
    ]:
        # Selected source/configuration only. No .env, credentials, app execution or recursive capture.
        expected = {v: sha((root/v).read_bytes()) for v in inputs}
        git_head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
        git_status = subprocess.check_output(["git","status","--porcelain=v1","--untracked-files=no"],cwd=root,text=True)
        definition = dict(profile="patamaps-project-inputs-1",id="urn:qualification:"+name,nonsecretInputs=True,
                          inputs=inputs,components=components,secretReferences={"database":"PATAMAPS_QUALIFICATION_UNRESOLVED_DATABASE"})
        profile = args.output/(name+".profile.json")
        profile.write_text(json.dumps(definition,indent=2)+"\n")
        captured = args.output/(name+".capture.json")
        sentinel="patamaps-controlled-reference-sentinel-not-a-real-secret"
        capture_env={**os.environ,"PATAMAPS_QUALIFICATION_UNRESOLVED_DATABASE":sentinel}
        run(name+"-capture",[args.compiler,"project-capture",profile,"--root",root,"--output",captured],env=capture_env)
        assert sentinel.encode() not in captured.read_bytes()
        record=json.loads(captured.read_bytes())
        assert {r["receipt"]["path"]:r["receipt"]["digest"] for r in record["inputs"]} == expected
        assert all(r["receipt"]["digest"]==sha(r["content"].encode()) for r in record["inputs"])
        replay=json.loads(run(name+"-verify",[args.compiler,"project-verify",captured]))
        assert replay["status"]=="verified-project-input-bindings"
        assert replay["secretResolution"]=="not-performed" and replay["admission"]=="not-performed"
        # Replay with only the capture argument, no source/tool arguments and an empty cwd/PATH.
        # Original sources remain on the host; the native unit control separately moves required paths.
        isolated=args.output/(name+"-empty-root");isolated.mkdir()
        offline=subprocess.run([str(args.compiler.resolve()),"project-verify",str(captured.resolve())],cwd=isolated,
                               env={"PATH":"/unavailable","HOME":str(isolated)},capture_output=True,timeout=30)
        (args.output/(name+"-offline.stdout.log")).write_bytes(offline.stdout)
        (args.output/(name+"-offline.stderr.log")).write_bytes(offline.stderr)
        assert offline.returncode==0 and json.loads(offline.stdout)==replay
        staged=args.output/(name+"-staged")
        isolated_env={"PATH":"/unavailable","HOME":str(isolated)}
        staged_receipt=json.loads(run(name+"-stage",[args.compiler.resolve(),"project-stage",captured.resolve(),"--destination",staged.resolve()],env=isolated_env,cwd=isolated))
        assert staged_receipt["status"]=="staged-project-inputs" and staged_receipt["digest"]==record["digest"]
        assert expected=={v:sha((staged/v).read_bytes()) for v in inputs}
        recaptured=args.output/(name+"-recaptured.json")
        run(name+"-recapture",[args.compiler,"project-capture",profile,"--root",staged,"--output",recaptured])
        assert json.loads(recaptured.read_bytes())["digest"]==record["digest"]
        run(name+"-stage-existing",[args.compiler.resolve(),"project-stage",captured.resolve(),"--destination",staged.resolve()],success=False,env=isolated_env,cwd=isolated)
        assert "PROJECT_STAGE_DESTINATION_UNAVAILABLE" in (args.output/(name+"-stage-existing.stderr.log")).read_text()
        assert expected=={v:sha((staged/v).read_bytes()) for v in inputs}
        tampered=json.loads(captured.read_bytes());tampered["inputs"][0]["content"]+="\nTAMPER"
        bad=args.output/(name+"-tampered.json");bad.write_text(json.dumps(tampered)+"\n")
        run(name+"-tamper",[args.compiler,"project-verify",bad],success=False)
        assert expected=={v:sha((root/v).read_bytes()) for v in inputs}
        assert git_head==subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
        assert git_status==subprocess.check_output(["git","status","--porcelain=v1","--untracked-files=no"],cwd=root,text=True)
        reports.append(dict(project=name,head=git_head,trackedWorkingTreeDirty=bool(git_status),selectedInputs=expected,
                            captureDigest=record["digest"],selectedInputsUnchanged=True,trackedStatusUnchanged=True,
                            offlineReplay="passed",retainedSelectedInputStaging="passed-source-free-arguments-and-empty-PATH",stagedRecaptureDigest="identical",existingDestination="refused-with-bytes-preserved",controlledSecretSentinelAbsent=True,tamperedBytes="refused",scope="selected-input-capture-and-staging-only",
                            applicationBuild="not-performed",runtime="not-performed"))
    receipt=dict(status="passed-g1-selected-input-controls",compilerDigest=sha(args.compiler.read_bytes()),
                 projects=reports,commands=commands,rawCaptureLocation=str(args.output),fullWorkflowAccepted=False,
                 secretResolution="not-performed",activation="not-performed")
    (args.output/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
