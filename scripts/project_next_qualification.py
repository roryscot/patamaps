"""Qualify explicit Next inputs through captured discovery; never claims runtime."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from storage_guard import ensure_guarded

ROLES = {"page", "layout", "template", "route", "loading", "error", "global-error", "not-found", "default"}
EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("compiler", "node", "typescript", "definition", "source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--app-router-root", required=True)
    parser.add_argument("--require-endpoint", nargs=2, action="append", default=[], metavar=("METHOD", "PATH"),
                        help="Require exactly one observed endpoint with this method and path; no runtime claim")
    args = parser.parse_args()
    ensure_guarded()
    cli, node = args.compiler.resolve(strict=True), args.node.resolve(strict=True)
    source, output = args.source.resolve(strict=True), args.output.resolve()
    assert not output.is_relative_to(source), "Output must be outside the original project"
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    def run(label, argv, success=True, env=None, cwd=None, input_bytes=None):
        argv = [str(v) for v in argv]
        with (output/(label+".stdout.log")).open("xb") as out, (output/(label+".stderr.log")).open("xb") as err:
            result = subprocess.run(argv, cwd=cwd or output, env=env, input=input_bytes, stdout=out, stderr=err, timeout=120)
        commands.append(dict(label=label, argv=argv, exitCode=result.returncode))
        (output/"commands.json").write_text(json.dumps(commands, indent=2)+"\n")
        assert (result.returncode == 0) == success, label
        return (output/(label+".stdout.log")).read_bytes()
    definition = json.loads(run("profile", [cli, "json", "parse"],
                                input_bytes=args.definition.read_bytes()))
    # The native capture validates the complete profile, paths and explicit nonsecret declaration.
    write(output/"profile.json", definition)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=source, text=True)
    driver_digest = sha(Path(__file__).read_bytes())
    write(output/"source-before.json", dict(head=head, trackedStatus=status, driverDigest=driver_digest))
    run("capture", [cli, "project-capture", output/"profile.json", "--root", source, "--output", output/"capture.json"])
    capture = json.loads((output/"capture.json").read_bytes())
    app_root = args.app_router_root
    assert app_root and all(p not in ("", ".", "..") for p in app_root.split("/")) and "\\" not in app_root
    assert any(c["kind"] == "next-app" and (c["root"] == "." or app_root.startswith(c["root"]+"/") or app_root == c["root"])
               for c in definition["components"]), "Router root must belong to a declared Next component"
    special = [v["receipt"]["path"] for v in capture["inputs"]
               if v["receipt"]["path"].startswith(app_root+"/")
               and Path(v["receipt"]["path"]).stem in ROLES
               and Path(v["receipt"]["path"]).suffix in EXTENSIONS]
    assert special, "No explicitly captured Next special files"
    run("stage", [cli, "project-stage", output/"capture.json", "--destination", output/"source"])
    tools = output/"tooling";tools.mkdir()
    ignore = shutil.ignore_patterns("node_modules", "target", ".git", "__pycache__")
    shutil.copytree(ROOT/"adapters", tools/"adapters", ignore=ignore)
    shutil.copytree(ROOT/"sdk/typescript", tools/"node_modules/patamaps-native-sdk-draft", ignore=ignore)
    ts = tools/"node_modules/typescript";(ts/"lib").mkdir(parents=True)
    for name in ("package.json", "lib/typescript.js", "LICENSE.txt", "ThirdPartyNoticeText.txt"):
        shutil.copyfile(args.typescript/name, ts/name)
    code = sorted(p.relative_to(output).as_posix() for p in tools.rglob("*")
                  if p.is_file() and p.suffix in {".js", ".mjs", ".json"})
    packs = ["routing", "application-topology", "build-deployment"]
    for pack in packs:
        shutil.copyfile(ROOT/("relation-packs/"+pack+".json"), output/(pack+".json"))
    identity = definition["id"]+":next-observations"
    native = dict(executable=str(cli), arguments=["discover-native"], codeInputs=[],
                  bounds=dict(maximumElapsedMs=60000, maximumStdoutBytes=16777216, maximumStderrBytes=65536))
    config = dict(schemaVersion="0.1.0", documentType="workspace-config", id=identity, namespace="project-next-qualification",
                  revision="1", sources=[
                      dict(adapter="process", id=identity+":files", invocation=native,
                           inputs=["source/"+v["receipt"]["path"] for v in capture["inputs"]],
                           config=dict(provider="files", nonsecretInputs=True)),
                      dict(adapter="process", id=identity+":next",
                           invocation=dict(executable=str(node), arguments=["tooling/adapters/metamap-process.mjs"], codeInputs=code,
                                           bounds=dict(maximumElapsedMs=60000, maximumStdoutBytes=16777216, maximumStderrBytes=65536)),
                           inputs=["source/"+name for name in special], config=dict(adapter="nextjs-app-router", root="source/"+app_root))],
                  packs=[n+".json" for n in packs], policy="policy.json",
                  projections=[dict(path="projection.json", emissions=[dict(path="observations/routes.json", language="json")])],
                  context=dict(scope="selected-source-observations", configurationExecution="not-performed"),
                  evaluatedAt="2026-10-16T00:00:00Z")
    policy = dict(schemaVersion="0.1.0", documentType="policy", id=identity+":policy", graph=dict(id=identity, revision="1"),
                  mappings=[dict(select=dict(provenanceStatuses=["observed"]), coverage="partial",
                                 determinism="deterministic", reversibility="irreversible")], constraints=[], evidence=[])
    projection = dict(schemaVersion="0.1.0", documentType="projection-spec", id=identity+":projection",
                      select=dict(kinds=["routing:route"]), slots=[])
    for name, value in (("workspace", config), ("policy", policy), ("projection", projection)):
        write(output/(name+".json"), value)
    generated = json.loads(run("generate", [cli, "generate", "workspace.json", "--root", output]))
    baseline = generated["baseline"];write(output/"baseline.json", baseline)
    graph = baseline["captures"][0]["inputs"]["graph"]
    entities = graph["entities"]
    required_endpoints = []
    for method, path in args.require_endpoint:
        assert method in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
        assert path.startswith("/") and not any(ord(c) < 32 for c in path)
        matches = [e["id"] for e in entities if e["kind"] == "routing:endpoint"
                   and e.get("attributes", {}).get("method") == method
                   and e.get("attributes", {}).get("path") == path]
        assert len(matches) == 1, ("Required observed endpoint missing or ambiguous", method, path, matches)
        required_endpoints.append(dict(method=method, path=path, observedId=matches[0]))
    counts = {kind:sum(e["kind"] == kind for e in entities)
              for kind in sorted({e["kind"] for e in entities})}
    # Missing a declared selected source must fail; the exact bytes stay retained.
    selected = output/"source"/special[0]
    retained = selected.with_name(selected.name+".retained-missing-control")
    selected.rename(retained)
    try:
        run("missing-input", [cli, "generate", "workspace.json", "--root", output], success=False)
    finally:
        retained.rename(selected)
    for name in ("source", "tooling"):
        (output/name).rename(output/(name+".retained-offline"))
    isolated = output/"isolated";isolated.mkdir()
    replay = json.loads(run("offline", [cli, "verify-workspace", output/"baseline.json"], cwd=isolated,
                            env=dict(PATH="/patamaps-no-programs", HOME=str(isolated))))
    assert replay["status"] == "verified-record-bindings"
    run("recapture-original", [cli, "project-capture", output/"profile.json", "--root", source,
                               "--output", output/"original-recaptured.json"])
    assert json.loads((output/"original-recaptured.json").read_bytes())["digest"] == capture["digest"]
    assert head == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    assert status == subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=source, text=True)
    assert driver_digest == sha(Path(__file__).read_bytes()), "Qualification driver changed"
    receipt = dict(status="passed-selected-next-observations", sourceCommit=head, originalTrackedStatus=status,
                   qualificationDriverDigest=driver_digest,
                   captureDigest=capture["digest"], baselineDigest=baseline["digest"], specialFileCount=len(special),
                   entityKindCounts=counts, requiredEndpointObservations=required_endpoints, compilerDigest=sha(cli.read_bytes()), nodeDigest=sha(node.read_bytes()),
                   selectedSourcesUnchanged=True, originalHeadAndStatusUnchanged=True,
                   missingSelectedInput="refused", offlineReplay="passed-source-and-tools-configured-paths-unavailable",
                   externalProgramsAbsentFromPath=True, commands=commands,
                   scope=dict(nextConfiguration="captured-as-file-bytes; not-executed-or-interpreted",
                              routeRuntime="not-performed", serverActionSemantics="not-established",
                              proxySemantics="not-established", processDependencyClosure="not-proved; cache-disabled", admission="observations-only",
                              activation="not-performed", fullGoalComplete=False))
    write(output/"receipt.json", receipt)
    print(json.dumps(dict(status=receipt["status"], specialFileCount=len(special), entityKindCounts=counts)))

if __name__ == "__main__":
    main()
