"""Actual portable stages of the same fixture used by the Linux lifecycle test."""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--cli", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args(); args.cli = args.cli.resolve()
env = {**os.environ, "CARGO_INCREMENTAL":"0", "CARGO_PROFILE_DEV_DEBUG":"0", "CARGO_PROFILE_TEST_DEBUG":"0"}
cargo = Path.home()/".cargo/bin/cargo"; rustc = Path.home()/".cargo/bin/rustc"
commands = []
def run(argv, cwd, expected=0, native=False):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, env={**env,"PATH":"/usr/bin:/bin"} if native else env, capture_output=True, text=True, timeout=180)
    commands.append({"argv":[str(x) for x in argv],"exitCode":result.returncode,"stdout":result.stdout,"stderr":result.stderr})
    assert result.returncode == expected, commands[-1]
    return result.stdout
with tempfile.TemporaryDirectory(prefix="patamaps-lifecycle-pure-") as directory:
    work = Path(directory); generated = work/"generated"
    env["PATAMAPS_TEST_LIFECYCLE_OUTPUT"] = str(generated)
    run([cargo,"test","-p","patamaps-activator","--test","transport","--locked","--offline",
         "complete_lifecycle_pure_stages_check_proof_unknown_policy_and_unique_budget","--","--exact"],ROOT)
    env.pop("PATAMAPS_TEST_LIFECYCLE_OUTPUT")
    captured = json.loads((generated/"capture.json").read_text())
    assert captured["result"]["projection"]["semantics"]["risk"]["totalCost"] == 3
    assert json.loads(run([args.cli,"replay",generated/"capture.json"],work))["status"] == "verified"
    inspected = json.loads(run([args.cli,"inspect",generated/"capture.json","--subject","urn:command:greet"],work))
    assert inspected["record"]["admission"] == "viable"
    saved_capture = (generated/"capture.json").read_bytes()
    inputs = json.loads(json.dumps(captured["inputs"])); inputs["policy"]["mappings"] = [
        {"mapping":identity,"coverage":"total","determinism":"deterministic","reversibility":"irreversible"}
        for identity in ["urn:mapping:alias","urn:mapping:implementation-handler"]]
    for name,value in [("graph",inputs["graph"]),("policy",inputs["policy"]),("spec",inputs["projectionSpec"]),
                       ("receipts",captured["sources"])]: (work/(name+".json")).write_text(json.dumps(value))
    pack_args=[]
    for i,pack in enumerate(inputs["packs"]):
        path=work/f"pack-{i}.json";path.write_text(json.dumps(pack));pack_args.extend(["--relation-pack",path])
    rejected=json.loads(run([args.cli,"capture","graph.json","policy.json","--spec","spec.json",
                             "--source-receipts","receipts.json","--as-of",inputs["evaluatedAt"],*pack_args],work))
    assert rejected["result"]["status"] == "rejected"
    request={"schemaVersion":"0.1.0","documentType":"repair-request","baseline":rejected,"consumer":"urn:consumer:linux",
        "allowedFacts":[{"subject":"urn:policy:linux","fact":"policy.mappings"}],"protectedFacts":[],
        "edits":[{"id":"restore-declaration","semanticCost":1,"operation":{"kind":"supply-declaration",
            "declaration":{"mapping":"urn:mapping:greet","coverage":"total","determinism":"deterministic","reversibility":"irreversible"}}}],
        "bounds":{"maximumCandidates":2,"maximumEdits":1,"maximumDerivationDepth":8,"maximumElapsedMilliseconds":60000,"maximumWorkUnits":2000000}}
    (work/"request.json").write_text(json.dumps(request))
    repair=json.loads(run([args.cli,"repair","request.json"],work));assert repair["status"]=="complete" and repair["applied"] is False
    assert len(repair["proposals"])==1 and any(a.get("viable") and a["authorization"]=="approval-required" for a in repair["attempts"])
    selected = next(a for a in repair["attempts"] if a["id"] in repair["proposals"])
    repaired_capture = selected["candidate"]
    assert selected["authorization"] == "approval-required" and selected["viable"] is True
    (work/"repaired-capture.json").write_text(json.dumps(repaired_capture))
    assert json.loads(run([args.cli,"replay","repaired-capture.json"],work))["status"] == "verified"
    repaired_inputs = repaired_capture["inputs"]
    for name,value in [("graph",repaired_inputs["graph"]),("policy",repaired_inputs["policy"]),
                       ("spec",repaired_inputs["projectionSpec"]),("context",repaired_inputs["context"]),
                       ("generation",repaired_capture["result"]["generation"]),("parameters",{"id":"42"})]:
        (work/("repaired-"+name+".json")).write_text(json.dumps(value))
    repaired_pack_args=[]
    for i,pack in enumerate(repaired_inputs["packs"]):
        path=work/f"repaired-pack-{i}.json";path.write_text(json.dumps(pack));repaired_pack_args.extend(["--relation-pack",path])
    repaired_args=["repaired-graph.json","repaired-policy.json","repaired-spec.json",
                   "--context","repaired-context.json","--as-of",repaired_inputs["evaluatedAt"],*repaired_pack_args]
    run([args.cli,"link",*repaired_args,"--generation","repaired-generation.json",
         "--binding-slot","handler","--format","rust","--output",generated/"repaired-bindings.rs"],work)
    repaired_tree=json.loads(run([args.cli,"path-tree",*repaired_args,"--parameters","repaired-parameters.json"],work))
    assert repaired_tree["tree"]["greet"][":id"]["_"] == "/greet/42"
    repaired_source=next(s["content"] for s in repaired_capture["sources"] if s["id"]=="urn:source:linux")
    assert repaired_source == next(s["content"] for s in captured["sources"] if s["id"]=="urn:source:linux")
    assert (generated/"capture.json").read_bytes() == saved_capture
    assert captured == json.loads(saved_capture), "Repair must not mutate the reported accepted capture"
    (generated/"service.rs").write_text(repaired_source)
    (generated/"main.rs").write_text('mod service;#[path="bindings-0.rs"]mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:command:greet").unwrap();println!("{}",bindings::dispatch(id,"Ada"));}')
    run([rustc,"--edition=2024","main.rs","-o","consumer"],generated)
    assert run([generated/"consumer"],generated).strip()=="Hello, Ada!"
    (generated/"repaired-main.rs").write_text('mod service;#[path="repaired-bindings.rs"]mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:command:greet").unwrap();assert!(bindings::SemanticId::parse("urn:missing").is_none());println!("{}",bindings::dispatch(id,"Ada"));}')
    assert shutil.which("node",path="/usr/bin:/bin") is None
    run([rustc,"--edition=2024","--crate-name","repaired_consumer","repaired-main.rs","-o","repaired-consumer"],generated,native=True)
    assert run([generated/"repaired-consumer"],generated,native=True).strip()=="Hello, Ada!"
    assert (generated/"capture.json").read_bytes()==saved_capture and captured==json.loads(saved_capture)
    report={"engines":json.loads(run([args.cli,"engine"],work)),"scope":"Portable compiler stages of the Linux lifecycle fixture; protected activation is not evaluated",
        "sourceShards":2,"capturedSources":3,"checkedDerivations":1,"usedMappingClosure":3,"ordinalCost":3,
        "unknownIdentity":"explicitly tolerated; supported-only policy refuses in the shared Rust test",
        "inspection":inspected,"repair":repair,"capture":captured,"commands":commands,"nativeConsumption":"Hello, Ada!",
        "authorization":"not-evaluated","activation":"not-evaluated", "originalCaptureUnchanged":True,
        "repairedCapture":repaired_capture,"repairedNativeConsumption":"Hello, Ada!","repairedNativePath":"/greet/42","repairedRuntimeNodeInPath":False}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+"\n")
print("PASS: composed owned sources, checked chain, explicit unknown policy, unique cost-three budget, replay, read-only inspection/repair and actual native dispatch; protected host acceptance is recorded separately.")
