"""Execute independently owned Rust/TS consumers before and after a real move."""
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/patamaps")
parser.add_argument("--tsc", type=Path, required=True)
parser.add_argument("--node", type=Path, required=True)
args = parser.parse_args()
CLI = str(args.cli.resolve())
TSC = str(args.tsc.resolve())
NODE = str(args.node.resolve())
RUSTC = str(Path.home() / ".cargo/bin/rustc")
NOW = "2026-10-10T12:00:00Z"
PACK = str(ROOT / "relation-packs/routing.json")
NATIVE_ENV = {**os.environ, "PATH": "/usr/bin:/bin"}
assert shutil.which("node",path=NATIVE_ENV["PATH"]) is None, "The no-Node control requires a PATH without Node"

def run(argv, cwd, expected=0, native=False):
    result = subprocess.run([str(a) for a in argv], cwd=cwd, text=True, capture_output=True,
                            env=NATIVE_ENV if native else None)
    assert result.returncode == expected, f"{argv}\nexit {result.returncode}\n{result.stdout}\n{result.stderr}"
    return result.stdout

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def graph(identity, entities, mappings=None, authorities=None):
    return {"schemaVersion":"0.1.0", "documentType":"graph", "id":identity, "namespace":"independent-native",
            "entities":entities, "mappings":mappings or [], "authorities":authorities or []}

def provenance(owner):
    return {"status":"declared", "assertedBy":owner}

def authority(identity, concept, fact, owner):
    return {"id":identity, "concept":concept, "source":concept, "facts":[fact], "mode":"canonical", "provenance":provenance(owner)}

with tempfile.TemporaryDirectory(prefix="patamaps-native-") as directory:
    work = Path(directory)
    operation, handler, schema = "urn:operation:greet", "urn:service:greeting-handler", "urn:contract:name"
    contract = graph("urn:shard:contract", [{"id":operation,"kind":"routing:command"}, {"id":schema,"kind":"routing:schema"}],
                     authorities=[authority("urn:authority:contract",operation,"routing-identity","team:contract")])
    service = graph("urn:shard:service", [{"id":handler,"kind":"routing:handler", "locators":[
        {"uri":"rust:crate::service::greet"}, {"uri":"typescript:./handler.ts#greet"}],
        "attributes":{"__proto__":{"admin":True},"untrusted":"\";throw new Error('injection');//"}}],
        authorities=[authority("urn:authority:service",handler,"implementation","team:service")])
    links = graph("urn:shard:consumer", [], mappings=[
        {"id":"urn:map:handler","relation":"routing:handled_by","sources":[operation],"targets":[handler],
         "cardinality":"one-to-one","lossiness":"lossless","provenance":provenance("team:consumer")},
        {"id":"urn:map:input","relation":"routing:accepts","sources":[operation],"targets":[schema],
         "cardinality":"one-to-one","lossiness":"lossless","provenance":provenance("team:consumer")},
    ])
    spec = {"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:projection:native","select":{"ids":[operation]},
            "slots":[{"name":"handler","relation":"routing:handled_by","direction":"outgoing","cardinality":"exactly-one","targetKinds":["routing:handler"]}]}
    write(work / "contract.json",contract); write(work / "service.json",service); write(work / "links.json",links); write(work / "spec.json",spec)
    (work / "handler.ts").write_text('export function greet(input: string): string { return `Hello, ${input}!`; }\n')
    (work / "service.rs").write_text('pub fn greet(input: &str) -> String { format!("Hello, {}!", input) }\n')
    (work / "main.rs").write_text('mod service; mod bindings; fn main() { let id = bindings::SemanticId::parse("urn:operation:greet").unwrap(); assert_eq!(id.as_str(), "urn:operation:greet"); println!("{}", bindings::dispatch(id, "Ada")); }\n')
    (work / "consumer.ts").write_text('import {bindings, dispatch, type SemanticId} from "./bindings.js"; const id: SemanticId = "urn:operation:greet"; if (!Object.hasOwn(bindings[id].handler.attributes, "__proto__")) throw new Error("data lost"); if (({} as {admin?: boolean}).admin) throw new Error("prototype polluted"); console.log(dispatch(id, "Ada"));\n')
    (work / "invalid.ts").write_text('import {dispatch} from "./bindings.js"; dispatch("urn:operation:missing", "Ada");\n')
    write(work / "package.json", {"type":"module"})
    hashes = []
    for moved in [False, True]:
        if moved:
            (work / "service.rs").rename(work / "moved.rs")
            (work / "handler.ts").rename(work / "moved-handler.ts")
            (work / "main.rs").write_text((work / "main.rs").read_text().replace("mod service;", "mod moved;"))
            service["entities"][0]["locators"] = [{"uri":"rust:crate::moved::greet"}, {"uri":"typescript:./moved-handler.ts#greet"}]
            write(work / "service.json", service)
        run([CLI,"compose","contract.json","service.json","links.json","--id","urn:graph:native","--namespace","native",
             "--relation-pack",PACK,"--output","graph.json", "--overwrite"],work,native=True)
        digest = json.loads(run([CLI,"validate","graph.json","--relation-pack",PACK],work,native=True))["graph"]
        policy = {"schemaVersion":"0.1.0","documentType":"policy","id":"urn:policy:native","graph":{"id":"urn:graph:native","digest":digest},
                  "mappings":[{"mapping":m["id"],"coverage":"total","determinism":"deterministic","reversibility":"irreversible"} for m in links["mappings"]],
                  "constraints":[{"id":"urn:constraint:authority","kind":"core:requires-authority","subjects":[operation],"parameters":{"fact":"routing-identity"}}],"evidence":[]}
        write(work / "policy.json",policy)
        run([CLI,"compile","graph.json","policy.json","--as-of",NOW,"--relation-pack",PACK,"-o","generation.json","--overwrite"],work,native=True)
        base = [CLI,"link","graph.json","policy.json","spec.json","--as-of",NOW,"--relation-pack",PACK,"--generation","generation.json","--binding-slot","handler"]
        for language, path in [("rust","bindings.rs"),("typescript","bindings.ts")]:
            run([*base,"--format",language,"-o",path,"--overwrite"],work,native=True)
        run([RUSTC,"--edition=2024","main.rs","-o","consumer-rust"],work,native=True)
        assert run([work / "consumer-rust"],work,native=True).strip() == "Hello, Ada!"
        run([NODE,TSC,"--strict","--target","ES2022","--module","NodeNext","--moduleResolution","NodeNext","--outDir","dist","consumer.ts","bindings.ts"],work)
        assert run([NODE,"dist/consumer.js"],work).strip() == "Hello, Ada!"
        invalid = subprocess.run([NODE,TSC,"--strict","--target","ES2022","--module","NodeNext","--moduleResolution","NodeNext","--noEmit","invalid.ts","bindings.ts"],cwd=work,capture_output=True,text=True)
        assert invalid.returncode != 0 and "not assignable" in invalid.stdout, invalid.stdout + invalid.stderr
        hashes.append(hashlib.sha256((work / "bindings.rs").read_bytes()).hexdigest())
    assert hashes[0] != hashes[1], "A changed locator must regenerate the artifact"
    previous = (work / "bindings.rs").read_bytes()
    rejected = json.loads((work / "graph.json").read_text())
    rejected["mappings"][0]["targets"] = ["urn:service:absent"]
    write(work / "rejected.json", rejected)
    run([CLI,"link","rejected.json","policy.json","spec.json","--as-of",NOW,"--relation-pack",PACK,"--format","rust","--binding-slot","handler","-o","bindings.rs","--overwrite"],work,expected=1,native=True)
    assert (work / "bindings.rs").read_bytes() == previous
    forged = json.loads((work / "generation.json").read_text()); forged["activeMappings"] = []
    write(work / "forged.json",forged)
    report = json.loads(run([CLI,"link","graph.json","policy.json","spec.json","--as-of",NOW,"--relation-pack",PACK,"--generation","forged.json"],work,expected=1,native=True))
    assert any(i["code"] == "PROJECTION_GENERATION_RECHECK_FAILED" for i in report["issues"])
    run([CLI,"canonical","policy.json","-o","generation.json"],work,expected=2,native=True)
    print("PASS: independently owned Rust and TypeScript consumers, actual module move, stable semantic ID, strict type refusal, escaped data, rejected-output preservation, forged generation rejection, no-clobber output; native compiler and Rust runtime executed with Node absent from PATH.")
