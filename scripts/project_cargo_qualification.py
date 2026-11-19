"""Real standalone Cargo observation, with explicit opt-in and unchanged-source controls."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/parity"))
from storage_guard import ensure_guarded

def digest(path):
    value=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            value.update(block)
    return "sha256:"+value.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ["compiler","cargo","rustc","cargo-home","source","output"]:
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--platform",required=True)
    p.add_argument("--manifest",type=Path,default=Path("Cargo.toml"))
    p.add_argument("--lockfile",type=Path,default=Path("Cargo.lock"))
    p.add_argument("--lockless",action="store_true",help="Qualify declared-local metadata without capturing Cargo.lock")
    p.add_argument("--package-name",default="wargame-workbench")
    p.add_argument("--toolchain-file",type=Path,default=Path("rust-toolchain.toml"))
    args=p.parse_args()
    if not args.compiler.is_absolute():
        args.compiler=(ROOT/args.compiler).resolve()
    ensure_guarded()
    args.output.mkdir(parents=True,exist_ok=False)
    commands=[]
    def run(label,argv,cwd=ROOT,raw=None,success=True):
        r=subprocess.run([str(v) for v in argv],cwd=cwd,input=raw,capture_output=True,timeout=90)
        (args.output/(label+".stdout.log")).write_bytes(r.stdout)
        (args.output/(label+".stderr.log")).write_bytes(r.stderr)
        commands.append(dict(label=label,argv=[str(v) for v in argv],exitCode=r.returncode))
        (args.output/"commands.json").write_text(json.dumps(commands,indent=2)+"\n")
        assert (r.returncode==0)==success,(label,str(args.output/(label+".stderr.log")))
        return r
    manifest=args.manifest.as_posix()
    lockfile=args.lockfile.as_posix()
    selected=[manifest]
    if args.lockless:
        if (args.source/args.lockfile).exists():
            raise ValueError("--lockless requires Cargo.lock to be absent from the source root")
    else:
        selected.append(lockfile)
    if (args.source/args.toolchain_file).is_file():
        selected.append(args.toolchain_file.as_posix())
    before={v:digest(args.source/v) for v in selected}
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=args.source,text=True).strip()
    # Complete manifests/lock/toolchain are declared nonsecret. No credentials/config capture.
    definition=dict(profile="patamaps-project-inputs-1",id="urn:qualification:standalone-cargo",nonsecretInputs=True,
                    inputs=selected,components=[dict(id="service",kind="cargo-package",root=".",entrypoints=[manifest])])
    profile=args.output/"project.json";profile.write_text(json.dumps(definition)+"\n")
    captured=args.output/"capture.json"
    run("capture",[args.compiler,"project-capture",profile,"--root",args.source,"--output",captured])
    record=json.loads(captured.read_bytes())
    cargo=args.cargo.resolve();rustc=args.rustc.resolve()
    config=dict(provider="cargo",nonsecretInputs=True,manifest=manifest,workspaceManifest=manifest,
                cargo=str(cargo),cargoDigest=digest(cargo),rustc=str(rustc),rustcDigest=digest(rustc),
                cargoHome=str(args.cargo_home.resolve()),platform=args.platform,features=[],defaultFeatures=True,view="declared-local")
    if not args.lockless:
        config["lockfile"]=lockfile
    def observe(label,root_mode=None,refuse=False):
        context=dict(config)
        if root_mode:context["rootMode"]=root_mode
        request=dict(schemaVersion="0.1.0",documentType="adapter-request",profile="patamaps-workspace-draft-1",
                     sourceId="urn:qualification:standalone",namespace="project-adoption",config=context,
                     inputs=record["inputs"],invocationDigest="sha256:"+"0"*64,requestDigest="")
        unsigned=json.dumps(request).encode()
        request["requestDigest"]=json.loads(run(label+"-digest",[args.compiler,"json","digest"],raw=unsigned).stdout)
        raw=json.dumps(request).encode()
        (args.output/(label+".request.json")).write_bytes(raw)
        result=run(label,[args.compiler,"discover-native"],cwd=args.source,raw=raw,success=not refuse)
        if refuse:
            assert b"NATIVE_CARGO_ROOT_ISOLATION" in result.stderr
            return None
        response=json.loads(result.stdout)
        assert response["requestDigest"]==request["requestDigest"]
        observation=response["shard"]["metadata"]["observation"]
        assert observation["rootMode"]=="standalone-package"
        assert observation["compilationEstablished"] is False and observation["buildScriptsExecuted"] is False
        assert observation["metadataDigest"]=="sha256:"+hashlib.sha256(observation["metadataBytes"].encode()).hexdigest()
        metadata=json.loads(observation["metadataBytes"])
        assert metadata["workspace_root"]==str(args.source.resolve())
        packages=[x["attributes"]["name"] for x in response["shard"]["entities"] if x["kind"]=="cargo-package"]
        assert packages==[args.package_name],(args.package_name,packages)
        targets=[x for x in response["shard"]["entities"] if x["kind"]=="cargo-target"]
        assert len(targets)>1
        return dict(packageNames=packages,targetCount=len(targets),metadataDigest=observation["metadataDigest"],
                    rootMode=observation["rootMode"],view=observation["view"])
    observe("default-still-refuses",refuse=True)
    observed=observe("explicit-standalone","standalone-package")
    assert before=={v:digest(args.source/v) for v in selected}
    assert head==subprocess.check_output(["git","rev-parse","HEAD"],cwd=args.source,text=True).strip()
    lockfile_absent_after=args.lockless and not (args.source/args.lockfile).exists()
    assert not args.lockless or lockfile_absent_after, "declared-local observation created Cargo.lock"
    receipt=dict(status="passed-standalone-cargo-observation",sourceCommit=head,selectedInputs=before,
                 compilerDigest=digest(args.compiler),cargoDigest=digest(cargo),rustcDigest=digest(rustc),
                 observation=observed,sourceInputsUnchanged=True,lockfileCaptured=not args.lockless,
                 lockfileAbsentAfter=lockfile_absent_after,projectBuildScriptsExecuted=False,
                 compilation="not-performed",runtime="not-performed",fullWorkflowAccepted=False,commands=commands)
    (args.output/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
