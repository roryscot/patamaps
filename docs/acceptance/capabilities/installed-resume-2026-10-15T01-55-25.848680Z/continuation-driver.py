"""Install the current source package and execute independent native consumers."""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from identity import identities
from retained_copy import copy_tree
from storage_guard import ensure_guarded, node_runtime


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


TYPED_TREE_RUNTIME = r'''import {nativeTree,nativeTreeParams,hydrateNativeTree} from "./native_tree.mjs";
import {hydrateAlternateTree} from "./alternate_tree.mjs";
import {edgeTree,hydrateEdgeTree} from "./edge_tree.mjs";
import {hydrateParams} from "./params_tree.mjs";
import {hydrate_patamapsParams} from "./prefixed_tree.mjs";
function check(value: boolean, message: string): void { if (!value) throw new Error(message); }
function refuses(action: () => unknown): void {
  let refused = false;
  try { action(); } catch { refused = true; }
  check(refused, "Expected path refusal");
}
const nativeBefore = JSON.stringify(nativeTree);
const hydrated = hydrateNativeTree({networkId:"99"});
check(hydrated.network[":networkId"]._ === "/network/99", "Hydrated native path");
check(JSON.stringify(nativeTree) === nativeBefore, "Native template changed");
check(JSON.stringify(nativeTreeParams) === JSON.stringify([":networkId"]), "Parameter inventory");
check(hydrateNativeTree({":networkId":"99"}).network[":networkId"]._ === "/network/99", "Explicit alias");
check(hydrateParams({networkId:"99"}).network[":networkId"]._ === "/network/99", "Export shadow");
check(hydrate_patamapsParams({networkId:"99"}).network[":networkId"]._ === "/network/99", "Prefix shadow");
refuses(() => hydrateNativeTree({}));
refuses(() => hydrateNativeTree(Object.create({networkId:"99"})));
for (const value of ["a/b","a?b","a#b","a\ufeffb","\ud800"]) {
  refuses(() => hydrateNativeTree({networkId:value}));
}
refuses(() => hydrateNativeTree(Object.fromEntries(Array.from({length:1025},(_,i)=>["p"+i,"x"]))));
refuses(() => hydrateNativeTree({networkId:"\u{1f600}".repeat(4_194_305)}));
check(hydrateNativeTree({networkId:"a\u0085b"}).network[":networkId"]._ === @@NATIVE_UNICODE_PATH@@, "Unicode decision differs from native");
check(hydrateAlternateTree({id:"value"}).users[":id"]._ === "--users--value", "Alternate delimiter path");
refuses(() => hydrateAlternateTree({id:"a--b"}));
const edgeBefore = JSON.stringify(edgeTree);
const edge = hydrateEdgeTree({id:":next",next:"literal",rest:"a/b"});
check(edge.users[":id"][":next"]._ === "/users/:next/literal", "Substitution was reinterpreted");
check(edge.files["*rest?"]._ === "/files/a/b", "Catch-all path");
check(hydrateEdgeTree({id:"x",next:"y"}).files["*rest?"]._ === "/files", "Absent optional path");
check(Object.hasOwn(edge,"__proto__"), "Prototype-like child lost");
check(edge["__proto__"][":id"]._ === "/__proto__/:next", "Prototype-like path");
for (const rest of ["bad?query","bad#fragment","\udfff"]) {
  refuses(() => hydrateEdgeTree({id:"x",next:"y",rest}));
}
refuses(() => hydrateEdgeTree({id:"x".repeat(6_000_000),next:"y"}));
(edge.users[":id"][":next"].$ as unknown as {label:string}).label = "changed output";
check(JSON.stringify(edgeTree) === edgeBefore, "Hydrated occupant aliases template");
console.log(JSON.stringify({
  nativePath:hydrated.network[":networkId"]._,
  literalPath:edge.users[":id"][":next"]._,
  catchAll:edge.files["*rest?"]._,
  prototypeChild:Object.hasOwn(edge,"__proto__"),
  ownershipPreserved:true,unicodeAndBoundsRefused:true
}));
'''
TYPED_TREE_INVALID = r'''import {hydrateNativeTree} from "./native_tree.mjs";
const impossible: "/network/:networkId" = hydrateNativeTree({networkId:"99"}).network[":networkId"]._;
console.log(impossible);
'''


def main():
    ensure_guarded()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    output = ROOT / "docs/acceptance/capabilities" / f"installed-resume-{stamp}"
    output.mkdir(parents=True)
    work = ROOT / '.tools/capabilities/installed-nwstqeg6'
    env = {**os.environ, "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    env["CARGO_TARGET_DIR"] = str(ROOT / "target/package-test")
    if sys.platform == "darwin":
        env["SDKROOT"] = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
    cargo = Path.home() / ".cargo/bin/cargo"
    rustc = Path.home() / ".cargo/bin/rustc"
    commands = []
    receipt = {"status": "running", "scope": "Development source/native package installation, Rust library customization and generated compiler-free Rust consumer, Python/TypeScript installed wrappers. Protected Linux host and complete scientific/discovery migrations are recorded separately.", "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "deleted": [], "registryPublication": "not-requested", "productionActivation": "not-requested"}
    receipt["resumedFrom"] = 'docs/acceptance/capabilities/installed-2026-10-15T01-50-34.899574Z/receipt.json'
    receipt["resumedFromDigest"] = 'sha256:9219b514c8d43d736df70f526158326225a17d5c69007606561e2096e02a7400'
    receipt["inheritedPackageCommand"] = {'label': 'package', 'argv': ['/Volumes/dev_src_case_sensitive/patamaps-intel-20261014/.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3', '-B', '/Volumes/dev_src_case_sensitive/patamaps-intel-20261014/scripts/package.py', '--binary', '/Volumes/dev_src_case_sensitive/patamaps-intel-20261014/target/debug/patamaps', '--build-profile', 'development', '--output', '/Volumes/dev_src_case_sensitive/patamaps-intel-20261014/.tools/capabilities/installed-nwstqeg6/package', '--acceptance-output', '/Volumes/dev_src_case_sensitive/patamaps-intel-20261014/docs/acceptance/capabilities/installed-2026-10-15T01-50-34.899574Z'], 'exitCode': 0, 'expectedExitCodes': [0], 'stdout': {'path': 'docs/acceptance/capabilities/installed-2026-10-15T01-50-34.899574Z/package.stdout.log', 'digest': 'sha256:0cb1ba1d1d36c16d7937141114ab6a6d8f830bc9cba6fd1e7efebbaebb251ed7'}, 'stderr': {'path': 'docs/acceptance/capabilities/installed-2026-10-15T01-50-34.899574Z/package.stderr.log', 'digest': 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}}
    receipt["continuationScope"] = "Reuse the exact retained package/extraction after a 2 GB supervisor stop. All archive, complete extracted inventory, current-source and remaining installed-consumer assertions are unchanged. No deletion or policy change."
    (output / "original-driver.py").write_text('"""Install the current source package and execute independent native consumers."""\n\nimport hashlib\nimport json\nimport os\nimport subprocess\nimport sys\nimport tarfile\nimport tempfile\nfrom datetime import datetime, timezone\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / "scripts/parity"))\nfrom identity import identities\nfrom retained_copy import copy_tree\nfrom storage_guard import ensure_guarded, node_runtime\n\n\ndef digest(raw):\n    return "sha256:" + hashlib.sha256(raw).hexdigest()\n\n\nTYPED_TREE_RUNTIME = r\'\'\'import {nativeTree,nativeTreeParams,hydrateNativeTree} from "./native_tree.mjs";\nimport {hydrateAlternateTree} from "./alternate_tree.mjs";\nimport {edgeTree,hydrateEdgeTree} from "./edge_tree.mjs";\nimport {hydrateParams} from "./params_tree.mjs";\nimport {hydrate_patamapsParams} from "./prefixed_tree.mjs";\nfunction check(value: boolean, message: string): void { if (!value) throw new Error(message); }\nfunction refuses(action: () => unknown): void {\n  let refused = false;\n  try { action(); } catch { refused = true; }\n  check(refused, "Expected path refusal");\n}\nconst nativeBefore = JSON.stringify(nativeTree);\nconst hydrated = hydrateNativeTree({networkId:"99"});\ncheck(hydrated.network[":networkId"]._ === "/network/99", "Hydrated native path");\ncheck(JSON.stringify(nativeTree) === nativeBefore, "Native template changed");\ncheck(JSON.stringify(nativeTreeParams) === JSON.stringify([":networkId"]), "Parameter inventory");\ncheck(hydrateNativeTree({":networkId":"99"}).network[":networkId"]._ === "/network/99", "Explicit alias");\ncheck(hydrateParams({networkId:"99"}).network[":networkId"]._ === "/network/99", "Export shadow");\ncheck(hydrate_patamapsParams({networkId:"99"}).network[":networkId"]._ === "/network/99", "Prefix shadow");\nrefuses(() => hydrateNativeTree({}));\nrefuses(() => hydrateNativeTree(Object.create({networkId:"99"})));\nfor (const value of ["a/b","a?b","a#b","a\\ufeffb","\\ud800"]) {\n  refuses(() => hydrateNativeTree({networkId:value}));\n}\nrefuses(() => hydrateNativeTree(Object.fromEntries(Array.from({length:1025},(_,i)=>["p"+i,"x"]))));\nrefuses(() => hydrateNativeTree({networkId:"\\u{1f600}".repeat(4_194_305)}));\ncheck(hydrateNativeTree({networkId:"a\\u0085b"}).network[":networkId"]._ === @@NATIVE_UNICODE_PATH@@, "Unicode decision differs from native");\ncheck(hydrateAlternateTree({id:"value"}).users[":id"]._ === "--users--value", "Alternate delimiter path");\nrefuses(() => hydrateAlternateTree({id:"a--b"}));\nconst edgeBefore = JSON.stringify(edgeTree);\nconst edge = hydrateEdgeTree({id:":next",next:"literal",rest:"a/b"});\ncheck(edge.users[":id"][":next"]._ === "/users/:next/literal", "Substitution was reinterpreted");\ncheck(edge.files["*rest?"]._ === "/files/a/b", "Catch-all path");\ncheck(hydrateEdgeTree({id:"x",next:"y"}).files["*rest?"]._ === "/files", "Absent optional path");\ncheck(Object.hasOwn(edge,"__proto__"), "Prototype-like child lost");\ncheck(edge["__proto__"][":id"]._ === "/__proto__/:next", "Prototype-like path");\nfor (const rest of ["bad?query","bad#fragment","\\udfff"]) {\n  refuses(() => hydrateEdgeTree({id:"x",next:"y",rest}));\n}\nrefuses(() => hydrateEdgeTree({id:"x".repeat(6_000_000),next:"y"}));\n(edge.users[":id"][":next"].$ as unknown as {label:string}).label = "changed output";\ncheck(JSON.stringify(edgeTree) === edgeBefore, "Hydrated occupant aliases template");\nconsole.log(JSON.stringify({\n  nativePath:hydrated.network[":networkId"]._,\n  literalPath:edge.users[":id"][":next"]._,\n  catchAll:edge.files["*rest?"]._,\n  prototypeChild:Object.hasOwn(edge,"__proto__"),\n  ownershipPreserved:true,unicodeAndBoundsRefused:true\n}));\n\'\'\'\nTYPED_TREE_INVALID = r\'\'\'import {hydrateNativeTree} from "./native_tree.mjs";\nconst impossible: "/network/:networkId" = hydrateNativeTree({networkId:"99"}).network[":networkId"]._;\nconsole.log(impossible);\n\'\'\'\n\n\ndef main():\n    ensure_guarded()\n    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")\n    output = ROOT / "docs/acceptance/capabilities" / f"installed-{stamp}"\n    output.mkdir(parents=True)\n    work = Path(tempfile.mkdtemp(prefix="installed-", dir=ROOT / ".tools/capabilities"))\n    env = {**os.environ, "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0", "PYTHONDONTWRITEBYTECODE": "1"}\n    env["CARGO_TARGET_DIR"] = str(ROOT / "target/package-test")\n    if sys.platform == "darwin":\n        env["SDKROOT"] = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()\n    cargo = Path.home() / ".cargo/bin/cargo"\n    rustc = Path.home() / ".cargo/bin/rustc"\n    commands = []\n    receipt = {"status": "running", "scope": "Development source/native package installation, Rust library customization and generated compiler-free Rust consumer, Python/TypeScript installed wrappers. Protected Linux host and complete scientific/discovery migrations are recorded separately.", "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "deleted": [], "registryPublication": "not-requested", "productionActivation": "not-requested"}\n    path = output / "receipt.json"\n\n    def save():\n        path.write_text(json.dumps(receipt, indent=2) + "\\n")\n\n    def run(label, argv, cwd=ROOT, environment=env, accepted=(0,)):\n        result = subprocess.run([str(v) for v in argv], cwd=cwd, env=environment, capture_output=True)\n        item = {"label": label, "argv": [str(v) for v in argv], "exitCode": result.returncode, "expectedExitCodes": list(accepted)}\n        for stream in ["stdout", "stderr"]:\n            raw = getattr(result, stream)\n            log = output / f"{label}.{stream}.log"\n            log.write_bytes(raw)\n            item[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": digest(raw)}\n        commands.append(item)\n        save()\n        print(json.dumps({"check": label, "exitCode": result.returncode, "expectedExitCodes": list(accepted)}), flush=True)\n        if result.returncode not in accepted:\n            raise RuntimeError(f"{label} failed; inspect retained logs in {output}")\n        return result.stdout.decode()\n\n    save()\n    try:\n        package = work / "package"\n        run("package", [sys.executable, "-B", ROOT / "scripts/package.py", "--binary", ROOT / "target/debug/patamaps", "--build-profile", "development", "--output", package, "--acceptance-output", output])\n        distribution = json.loads((package / "distribution.json").read_text())\n        expected = {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}\n        assert distribution["engines"] == expected\n        for kind in ["sourceArchive", "nativeArchive"]:\n            archive = package / distribution[kind]["path"]\n            assert digest(archive.read_bytes()) == distribution[kind]["digest"]\n        extracted = work / "source"\n        extracted.mkdir()\n        with tarfile.open(package / distribution["sourceArchive"]["path"]) as archive:\n            archive.extractall(extracted, filter="data")\n        source, = extracted.iterdir()\n        raw_inventory = (source / "source-inventory.json").read_bytes()\n        assert digest(raw_inventory) == distribution["sourceInventoryDigest"]\n        inventory = json.loads(raw_inventory)\n        assert distribution["acceptanceOutputOutsideSourcePayload"] == output.relative_to(ROOT).as_posix()\n        assert not any(Path(item["path"]).is_relative_to(output.relative_to(ROOT)) for item in inventory)\n        assert {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()} == {item["path"] for item in inventory} | {"source-inventory.json"}\n        for item in inventory:\n            raw = (source / item["path"]).read_bytes()\n            assert len(raw) == item["bytes"] and digest(raw) == item["digest"]\n            assert raw == (ROOT / item["path"]).read_bytes(), item["path"]\n        assert (source / "vendor/icu_collator/Cargo.toml").is_file()\n        assert (source / "docs/TEST_CLASSIFICATION.md").is_file()\n        assert identities(source) == identities(ROOT)\n        installation = work / "installation"\n        run("install", [cargo, "install", "--path", source / "crates/patamaps-cli", "--locked", "--offline", "--debug", "--root", installation], work)\n        cli = installation / "bin/patamaps"\n        assert json.loads(run("installed-engine", [cli, "engine"], work, {})) == expected\n\n        consumer = work / "consumer"\n        consumer.mkdir()\n        (consumer / "src").mkdir()\n        dependencies = "\\n".join(f\'{name}={{path={json.dumps(str(source / "crates" / name))}}}\' for name in ["patamaps-contracts", "patamaps-core", "patamaps-projection", "patamaps-governance", "patamaps-activator", "patamaps-workspace", "patamaps-inspect"])\n        dependencies += \'\\nserde_json="1"\\nbase64="0.22"\\ned25519-dalek="2"\'\n        (consumer / "Cargo.toml").write_text(\'[workspace]\\n[package]\\nname="patamaps-independent-native-consumer"\\nversion="0.0.0"\\nedition="2024"\\n[dependencies]\\n\'+dependencies+\'\\n\')\n        # These are consumer-owned fixtures, outside the checkout and package.\n        for name in ["graph", "policy", "projection-spec"]:\n            (consumer / f"{name}.json").write_bytes((source / f"fixtures/routing/{name}.json").read_bytes())\n        for name in ["core", "routing"]:\n            (consumer / f"{name}.json").write_bytes((source / f"relation-packs/{name}.json").read_bytes())\n        (consumer / "src/main.rs").write_text(\'\'\'use patamaps_contracts::*;\nuse patamaps_core::*;\nuse std::time::Duration;\nfn main(){\n let mut graph:GraphDocument=parse(&std::fs::read("graph.json").unwrap()).unwrap();\n let handler=graph.entities.iter_mut().find(|e| e.kind=="routing:handler").unwrap();\n handler.locators=Some(vec![parse(br#"{"uri":"rust:crate::service::greet"}"#).unwrap()]);\n let packs=vec![parse(&std::fs::read("core.json").unwrap()).unwrap(),parse(&std::fs::read("routing.json").unwrap()).unwrap()];\n let checked=CheckedGraph::check(graph,packs).unwrap();\n let mut policy:PolicyDocument=parse(&std::fs::read("policy.json").unwrap()).unwrap();\n policy.constraints.push(Constraint{id:"urn:constraint:installed".into(),kind:"consumer:requires-active".into(),subjects:vec!["urn:example:command:create-user".into()],parameters:None});\n let mut registry=ConstraintRegistry::new();\n registry.register("consumer:requires-active",ContentBinding{id:"urn:evaluator:installed".into(),digest:byte_digest(include_bytes!("main.rs"))},|c:&Constraint,ctx:&ConstraintEvaluationContext<\'_>|{ctx.poll()?;Ok(if ctx.active("urn:example:mapping:create-user-handler"){vec![]}else{vec![Issue::error("consumer:requires-active:MISSING","Required active binding absent",&c.subjects[0])]})}).unwrap();\n let controls=WorkControl::new(CancellationToken::default(),Duration::from_secs(60),100000);\n let admitted=admit_with_constraints(&checked,&policy,EvaluationOptions{context:JsonObject::new(),evaluated_at:"2026-10-10T12:00:00Z".into()},&registry,&controls).unwrap();\n let spec:ProjectionSpec=parse(&std::fs::read("projection-spec.json").unwrap()).unwrap();\n let projected=patamaps_projection::project(&admitted,&spec).unwrap();\n std::fs::write("bindings.rs",patamaps_projection::emit_rust(&projected,Some("handler")).unwrap()).unwrap();\n println!("{}",String::from_utf8(canonical_bytes(admitted.record()).unwrap()).unwrap());\n}\n\'\'\')\n        generation = json.loads(run("rust-sdk", [cargo, "run", "--offline", "--quiet", "--bin", "patamaps-independent-native-consumer"], consumer))\n        assert generation["customConstraintEvaluators"][0]["evaluator"]["digest"] == digest((consumer / "src/main.rs").read_bytes())\n        (consumer / "src/bin").mkdir()\n        memory_source = source / "scripts/capabilities/consumers/memory.rs"\n        assert memory_source.read_bytes() == (ROOT / "scripts/capabilities/consumers/memory.rs").read_bytes()\n        (consumer / "src/bin/memory.rs").write_bytes(memory_source.read_bytes())\n        memory = json.loads(run("rust-memory-host", [cargo, "run", "--offline", "--quiet", "--bin", "memory"], consumer, {**env, "PATH": str(cargo.parent) + ":/usr/bin:/bin"}))\n        assert memory["profile"] == "patamaps-memory-draft-1"\n        assert all(memory[k] is True for k in ["bootstrap", "move", "rollback", "retryRechecked", "rejectionPreservesState"])\n        source_consumer = source / "scripts/capabilities/consumers/source.rs"\n        assert source_consumer.read_bytes() == (ROOT / "scripts/capabilities/consumers/source.rs").read_bytes()\n        (consumer / "src/bin/source.rs").write_bytes(source_consumer.read_bytes())\n        source_report = json.loads(run("rust-source-inspection", [cargo, "run", "--offline", "--quiet", "--bin", "source"], consumer, {**env, "PATH": str(cargo.parent) + ":/usr/bin:/bin"}))\n        assert source_report["profile"] == "patamaps-source-evaluation-draft-1"\n        assert all(source_report[k] is True for k in ["offlineVerified", "distinctCandidate", "selectedRetained", "inputsUnchanged"])\n        assert (source / "scripts/capabilities/source_reporting.py").read_bytes() == (ROOT / "scripts/capabilities/source_reporting.py").read_bytes()\n        source_cli = json.loads(run("installed-source-cli", [sys.executable, "-B", ROOT / "scripts/capabilities/source_reporting.py", "--cli", cli], consumer))\n        assert source_cli["status"] == "passed"\n        # Exercise the native typed-policy/tree workflow through installed Rust libraries.\n        typed_fixtures = consumer / "typed-fixtures"\n        typed_fixtures.mkdir()\n        for name in ["graph", "pack", "request", "policy", "projection-spec"]:\n            (typed_fixtures / f"{name}.json").write_bytes((source / f"fixtures/laws/{name}.json").read_bytes())\n        (typed_fixtures / "core.json").write_bytes((source / "relation-packs/core.json").read_bytes())\n        typed_source = source / "scripts/capabilities/consumers/typed_tree.rs"\n        assert typed_source.read_bytes() == (ROOT / "scripts/capabilities/consumers/typed_tree.rs").read_bytes()\n        (consumer / "src/bin/typed_tree.rs").write_bytes(typed_source.read_bytes())\n        typed_tree = json.loads(run("rust-typed-tree", [cargo, "run", "--offline", "--quiet", "--bin", "typed_tree"], consumer, {**env, "PATH": str(cargo.parent) + ":/usr/bin:/bin"}))\n        assert typed_tree["profile"] == "patamaps-native-typed-consumer-acceptance"\n        assert all(typed_tree[k] is True for k in ["typedTreeHydration", "templateUnchanged", "inputBytesUnchanged", "budgetBoundary", "replayTamperRefusal", "unavailableRiskStaysNull"])\n        (consumer / "typed_runtime.rs").write_text(\'#[path="typed_bindings.rs"]mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:a").unwrap();assert_eq!(id.as_str(),"urn:a");assert!(bindings::SemanticId::parse("urn:missing").is_none());println!("{}",bindings::PROJECTION_JSON);}\\n\')\n        run("typed-runtime-build", [rustc, "--edition=2024", "typed_runtime.rs", "-o", "typed_runtime"], consumer)\n        typed_runtime = json.loads(run("typed-runtime", [consumer / "typed_runtime"], consumer, {"PATH": "/usr/bin:/bin"}))\n        assert typed_runtime["digest"] == typed_tree["projectionDigest"]\n        assert typed_runtime["entries"][0]["slots"][0]["targets"][0]["id"] == "urn:c"\n        assert typed_runtime["semantics"]["risk"]["totalCost"] == 5\n        typed_inputs = typed_tree["acceptedCapture"]["inputs"]\n        for name, value in [\n            ("graph", typed_inputs["graph"]), ("policy", typed_inputs["policy"]),\n            ("spec", typed_inputs["projectionSpecs"][0]), ("pack", typed_inputs["packs"][0]),\n            ("context", typed_inputs["context"]), ("parameters", {"networkId": "99"}),\n        ]:\n            (consumer / f"typed_{name}.json").write_text(json.dumps(value, indent=2) + "\\n")\n        tree_cli_arguments = [cli, "path-tree", "typed_graph.json", "typed_policy.json", "typed_spec.json", "--as-of", typed_inputs["evaluatedAt"], "--context", "typed_context.json", "--relation-pack", "typed_pack.json", "--format", "typescript", "--export", "nativeTree"]\n        cli_tree = run("typed-tree-cli", tree_cli_arguments, consumer, {"PATH": "/usr/bin:/bin"})\n        assert cli_tree == (consumer / "native_tree.mts").read_text()\n        refused = json.loads(run("typed-tree-options-refusal", [*tree_cli_arguments, "--parameters", "typed_parameters.json", "--output", "native_tree.mts"], consumer, {"PATH": "/usr/bin:/bin"}, accepted=(1,)))\n        assert any(issue["code"] == "PATH_TREE_EMISSION_OPTIONS" for issue in refused["issues"])\n        assert cli_tree == (consumer / "native_tree.mts").read_text()\n        (consumer / "typed_runtime.mts").write_text(TYPED_TREE_RUNTIME.replace("@@NATIVE_UNICODE_PATH@@", json.dumps(typed_tree["unicodePath"])))\n        (consumer / "typed_invalid.mts").write_text(TYPED_TREE_INVALID)\n        tsc = Path(os.environ.get("PATAMAPS_REFERENCE", "/Users/admin/dev/SEEDZ/metamap")) / "node_modules/typescript/lib/tsc.js"\n        assert tsc.is_file()\n        type_arguments = [node_runtime(), tsc, "--strict", "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext"]\n        run("typed-tree-typescript-build", [*type_arguments, "--outDir", "typed_dist", "typed_runtime.mts"], consumer)\n        tree_runtime = json.loads(run("typed-tree-typescript-runtime", [node_runtime(), consumer / "typed_dist/typed_runtime.mjs"], consumer, {"PATH": "/usr/bin:/bin"}))\n        assert tree_runtime["nativePath"] == "/network/99"\n        assert tree_runtime["literalPath"] == "/users/:next/literal"\n        assert tree_runtime["catchAll"] == "/files/a/b"\n        assert all(tree_runtime[k] is True for k in ["prototypeChild", "ownershipPreserved", "unicodeAndBoundsRefused"])\n        invalid_type = run("typed-tree-false-literal-refusal", [*type_arguments, "--noEmit", "typed_invalid.mts"], consumer, accepted=(1, 2))\n        assert "TS2322" in invalid_type and "not assignable" in invalid_type\n        (consumer / "service.rs").write_text(\'pub fn greet(input:&str)->String{format!("Hello, {}!",input)}\\n\')\n        (consumer / "runtime.rs").write_text(\'mod service;mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:example:command:create-user").unwrap();println!("{}",bindings::dispatch(id,"Ada"));}\\n\')\n        no_node = {"PATH": "/usr/bin:/bin"}\n        run("runtime-build", [rustc, "--edition=2024", "runtime.rs", "-o", "runtime"], consumer, env)\n        assert run("runtime", [consumer / "runtime"], consumer, no_node).strip() == "Hello, Ada!"\n        python_env = {**env, "PYTHONPATH": str(source / "sdk/python")}\n        python_engine = json.loads(run("python-sdk", [sys.executable, "-B", "-c", \'from patamaps import Patamaps;import json,sys;print(json.dumps(Patamaps(sys.argv[1]).run_json(["engine"])))\', cli], consumer, python_env))\n        assert python_engine == expected\n        module = consumer / "node_modules/patamaps-native-sdk-draft"\n        copy_tree(source / "sdk/typescript", module)\n        (consumer / "package.json").write_text(\'{"type":"module"}\\n\')\n        (consumer / "sdk.mjs").write_text(\'import{Patamaps}from"patamaps-native-sdk-draft";console.log(JSON.stringify(new Patamaps(process.argv[2]).runJson(["engine"])));\\n\')\n        assert json.loads(run("typescript-sdk", [node_runtime(), consumer / "sdk.mjs", cli], consumer)) == expected\n        receipt.update(status="passed", distribution=distribution, sourceInventoryEntries=len(inventory), engines=expected, nativeConsumption="Hello, Ada!", customEvaluatorBinding=generation["customConstraintEvaluators"][0], memoryHost=memory, memoryConsumerSourceDigest=digest(memory_source.read_bytes()), sourceInspection=source_report, sourceConsumerDigest=digest(source_consumer.read_bytes()), sourceCliReceipt=source_cli["receipt"], typedTree=typed_tree, typescriptTreeRuntime=tree_runtime, typedConsumerSourceDigest=digest(typed_source.read_bytes()), completedAtUtc=datetime.now(timezone.utc).isoformat())\n    except BaseException as error:\n        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")\n        raise\n    finally:\n        save()\n        print(json.dumps({"status":receipt["status"],"receipt":path.relative_to(ROOT).as_posix()}),flush=True)\n\n\nif __name__ == "__main__":\n    main()\n')
    (output / "continuation-driver.py").write_bytes(Path(__file__).read_bytes())
    path = output / "receipt.json"

    def save():
        path.write_text(json.dumps(receipt, indent=2) + "\n")

    def run(label, argv, cwd=ROOT, environment=env, accepted=(0,)):
        result = subprocess.run([str(v) for v in argv], cwd=cwd, env=environment, capture_output=True)
        item = {"label": label, "argv": [str(v) for v in argv], "exitCode": result.returncode, "expectedExitCodes": list(accepted)}
        for stream in ["stdout", "stderr"]:
            raw = getattr(result, stream)
            log = output / f"{label}.{stream}.log"
            log.write_bytes(raw)
            item[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": digest(raw)}
        commands.append(item)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode, "expectedExitCodes": list(accepted)}), flush=True)
        if result.returncode not in accepted:
            raise RuntimeError(f"{label} failed; inspect retained logs in {output}")
        return result.stdout.decode()

    save()
    try:
        package = work / "package"
        # Package creation passed in the linked, supervisor-stopped attempt.
        distribution = json.loads((package / "distribution.json").read_text())
        expected = {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}
        assert distribution["engines"] == expected
        for kind in ["sourceArchive", "nativeArchive"]:
            archive = package / distribution[kind]["path"]
            assert digest(archive.read_bytes()) == distribution[kind]["digest"]
        extracted = work / "source"
        # Reuse retained extraction; the complete original inventory checks below still run.
        source, = extracted.iterdir()
        raw_inventory = (source / "source-inventory.json").read_bytes()
        assert digest(raw_inventory) == distribution["sourceInventoryDigest"]
        inventory = json.loads(raw_inventory)
        assert distribution["acceptanceOutputOutsideSourcePayload"] == 'docs/acceptance/capabilities/installed-2026-10-15T01-50-34.899574Z'
        assert not any(Path(item["path"]).is_relative_to('docs/acceptance/capabilities/installed-2026-10-15T01-50-34.899574Z') for item in inventory)
        assert not any(Path(item["path"]).is_relative_to(output.relative_to(ROOT)) for item in inventory)
        assert {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()} == {item["path"] for item in inventory} | {"source-inventory.json"}
        for item in inventory:
            raw = (source / item["path"]).read_bytes()
            assert len(raw) == item["bytes"] and digest(raw) == item["digest"]
            assert raw == (ROOT / item["path"]).read_bytes(), item["path"]
        assert (source / "vendor/icu_collator/Cargo.toml").is_file()
        assert (source / "docs/TEST_CLASSIFICATION.md").is_file()
        assert identities(source) == identities(ROOT)
        installation = work / "installation"
        run("install", [cargo, "install", "--path", source / "crates/patamaps-cli", "--locked", "--offline", "--debug", "--root", installation], work)
        cli = installation / "bin/patamaps"
        assert json.loads(run("installed-engine", [cli, "engine"], work, {})) == expected

        consumer = work / "consumer"
        consumer.mkdir()
        (consumer / "src").mkdir()
        dependencies = "\n".join(f'{name}={{path={json.dumps(str(source / "crates" / name))}}}' for name in ["patamaps-contracts", "patamaps-core", "patamaps-projection", "patamaps-governance", "patamaps-activator", "patamaps-workspace", "patamaps-inspect"])
        dependencies += '\nserde_json="1"\nbase64="0.22"\ned25519-dalek="2"'
        (consumer / "Cargo.toml").write_text('[workspace]\n[package]\nname="patamaps-independent-native-consumer"\nversion="0.0.0"\nedition="2024"\n[dependencies]\n'+dependencies+'\n')
        # These are consumer-owned fixtures, outside the checkout and package.
        for name in ["graph", "policy", "projection-spec"]:
            (consumer / f"{name}.json").write_bytes((source / f"fixtures/routing/{name}.json").read_bytes())
        for name in ["core", "routing"]:
            (consumer / f"{name}.json").write_bytes((source / f"relation-packs/{name}.json").read_bytes())
        (consumer / "src/main.rs").write_text('''use patamaps_contracts::*;
use patamaps_core::*;
use std::time::Duration;
fn main(){
 let mut graph:GraphDocument=parse(&std::fs::read("graph.json").unwrap()).unwrap();
 let handler=graph.entities.iter_mut().find(|e| e.kind=="routing:handler").unwrap();
 handler.locators=Some(vec![parse(br#"{"uri":"rust:crate::service::greet"}"#).unwrap()]);
 let packs=vec![parse(&std::fs::read("core.json").unwrap()).unwrap(),parse(&std::fs::read("routing.json").unwrap()).unwrap()];
 let checked=CheckedGraph::check(graph,packs).unwrap();
 let mut policy:PolicyDocument=parse(&std::fs::read("policy.json").unwrap()).unwrap();
 policy.constraints.push(Constraint{id:"urn:constraint:installed".into(),kind:"consumer:requires-active".into(),subjects:vec!["urn:example:command:create-user".into()],parameters:None});
 let mut registry=ConstraintRegistry::new();
 registry.register("consumer:requires-active",ContentBinding{id:"urn:evaluator:installed".into(),digest:byte_digest(include_bytes!("main.rs"))},|c:&Constraint,ctx:&ConstraintEvaluationContext<'_>|{ctx.poll()?;Ok(if ctx.active("urn:example:mapping:create-user-handler"){vec![]}else{vec![Issue::error("consumer:requires-active:MISSING","Required active binding absent",&c.subjects[0])]})}).unwrap();
 let controls=WorkControl::new(CancellationToken::default(),Duration::from_secs(60),100000);
 let admitted=admit_with_constraints(&checked,&policy,EvaluationOptions{context:JsonObject::new(),evaluated_at:"2026-10-10T12:00:00Z".into()},&registry,&controls).unwrap();
 let spec:ProjectionSpec=parse(&std::fs::read("projection-spec.json").unwrap()).unwrap();
 let projected=patamaps_projection::project(&admitted,&spec).unwrap();
 std::fs::write("bindings.rs",patamaps_projection::emit_rust(&projected,Some("handler")).unwrap()).unwrap();
 println!("{}",String::from_utf8(canonical_bytes(admitted.record()).unwrap()).unwrap());
}
''')
        generation = json.loads(run("rust-sdk", [cargo, "run", "--offline", "--quiet", "--bin", "patamaps-independent-native-consumer"], consumer))
        assert generation["customConstraintEvaluators"][0]["evaluator"]["digest"] == digest((consumer / "src/main.rs").read_bytes())
        (consumer / "src/bin").mkdir()
        memory_source = source / "scripts/capabilities/consumers/memory.rs"
        assert memory_source.read_bytes() == (ROOT / "scripts/capabilities/consumers/memory.rs").read_bytes()
        (consumer / "src/bin/memory.rs").write_bytes(memory_source.read_bytes())
        memory = json.loads(run("rust-memory-host", [cargo, "run", "--offline", "--quiet", "--bin", "memory"], consumer, {**env, "PATH": str(cargo.parent) + ":/usr/bin:/bin"}))
        assert memory["profile"] == "patamaps-memory-draft-1"
        assert all(memory[k] is True for k in ["bootstrap", "move", "rollback", "retryRechecked", "rejectionPreservesState"])
        source_consumer = source / "scripts/capabilities/consumers/source.rs"
        assert source_consumer.read_bytes() == (ROOT / "scripts/capabilities/consumers/source.rs").read_bytes()
        (consumer / "src/bin/source.rs").write_bytes(source_consumer.read_bytes())
        source_report = json.loads(run("rust-source-inspection", [cargo, "run", "--offline", "--quiet", "--bin", "source"], consumer, {**env, "PATH": str(cargo.parent) + ":/usr/bin:/bin"}))
        assert source_report["profile"] == "patamaps-source-evaluation-draft-1"
        assert all(source_report[k] is True for k in ["offlineVerified", "distinctCandidate", "selectedRetained", "inputsUnchanged"])
        assert (source / "scripts/capabilities/source_reporting.py").read_bytes() == (ROOT / "scripts/capabilities/source_reporting.py").read_bytes()
        source_cli = json.loads(run("installed-source-cli", [sys.executable, "-B", ROOT / "scripts/capabilities/source_reporting.py", "--cli", cli], consumer))
        assert source_cli["status"] == "passed"
        # Exercise the native typed-policy/tree workflow through installed Rust libraries.
        typed_fixtures = consumer / "typed-fixtures"
        typed_fixtures.mkdir()
        for name in ["graph", "pack", "request", "policy", "projection-spec"]:
            (typed_fixtures / f"{name}.json").write_bytes((source / f"fixtures/laws/{name}.json").read_bytes())
        (typed_fixtures / "core.json").write_bytes((source / "relation-packs/core.json").read_bytes())
        typed_source = source / "scripts/capabilities/consumers/typed_tree.rs"
        assert typed_source.read_bytes() == (ROOT / "scripts/capabilities/consumers/typed_tree.rs").read_bytes()
        (consumer / "src/bin/typed_tree.rs").write_bytes(typed_source.read_bytes())
        typed_tree = json.loads(run("rust-typed-tree", [cargo, "run", "--offline", "--quiet", "--bin", "typed_tree"], consumer, {**env, "PATH": str(cargo.parent) + ":/usr/bin:/bin"}))
        assert typed_tree["profile"] == "patamaps-native-typed-consumer-acceptance"
        assert all(typed_tree[k] is True for k in ["typedTreeHydration", "templateUnchanged", "inputBytesUnchanged", "budgetBoundary", "replayTamperRefusal", "unavailableRiskStaysNull"])
        (consumer / "typed_runtime.rs").write_text('#[path="typed_bindings.rs"]mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:a").unwrap();assert_eq!(id.as_str(),"urn:a");assert!(bindings::SemanticId::parse("urn:missing").is_none());println!("{}",bindings::PROJECTION_JSON);}\n')
        run("typed-runtime-build", [rustc, "--edition=2024", "typed_runtime.rs", "-o", "typed_runtime"], consumer)
        typed_runtime = json.loads(run("typed-runtime", [consumer / "typed_runtime"], consumer, {"PATH": "/usr/bin:/bin"}))
        assert typed_runtime["digest"] == typed_tree["projectionDigest"]
        assert typed_runtime["entries"][0]["slots"][0]["targets"][0]["id"] == "urn:c"
        assert typed_runtime["semantics"]["risk"]["totalCost"] == 5
        typed_inputs = typed_tree["acceptedCapture"]["inputs"]
        for name, value in [
            ("graph", typed_inputs["graph"]), ("policy", typed_inputs["policy"]),
            ("spec", typed_inputs["projectionSpecs"][0]), ("pack", typed_inputs["packs"][0]),
            ("context", typed_inputs["context"]), ("parameters", {"networkId": "99"}),
        ]:
            (consumer / f"typed_{name}.json").write_text(json.dumps(value, indent=2) + "\n")
        tree_cli_arguments = [cli, "path-tree", "typed_graph.json", "typed_policy.json", "typed_spec.json", "--as-of", typed_inputs["evaluatedAt"], "--context", "typed_context.json", "--relation-pack", "typed_pack.json", "--format", "typescript", "--export", "nativeTree"]
        cli_tree = run("typed-tree-cli", tree_cli_arguments, consumer, {"PATH": "/usr/bin:/bin"})
        assert cli_tree == (consumer / "native_tree.mts").read_text()
        refused = json.loads(run("typed-tree-options-refusal", [*tree_cli_arguments, "--parameters", "typed_parameters.json", "--output", "native_tree.mts"], consumer, {"PATH": "/usr/bin:/bin"}, accepted=(1,)))
        assert any(issue["code"] == "PATH_TREE_EMISSION_OPTIONS" for issue in refused["issues"])
        assert cli_tree == (consumer / "native_tree.mts").read_text()
        (consumer / "typed_runtime.mts").write_text(TYPED_TREE_RUNTIME.replace("@@NATIVE_UNICODE_PATH@@", json.dumps(typed_tree["unicodePath"])))
        (consumer / "typed_invalid.mts").write_text(TYPED_TREE_INVALID)
        tsc = Path(os.environ.get("PATAMAPS_REFERENCE", "/Users/admin/dev/SEEDZ/metamap")) / "node_modules/typescript/lib/tsc.js"
        assert tsc.is_file()
        type_arguments = [node_runtime(), tsc, "--strict", "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext"]
        run("typed-tree-typescript-build", [*type_arguments, "--outDir", "typed_dist", "typed_runtime.mts"], consumer)
        tree_runtime = json.loads(run("typed-tree-typescript-runtime", [node_runtime(), consumer / "typed_dist/typed_runtime.mjs"], consumer, {"PATH": "/usr/bin:/bin"}))
        assert tree_runtime["nativePath"] == "/network/99"
        assert tree_runtime["literalPath"] == "/users/:next/literal"
        assert tree_runtime["catchAll"] == "/files/a/b"
        assert all(tree_runtime[k] is True for k in ["prototypeChild", "ownershipPreserved", "unicodeAndBoundsRefused"])
        invalid_type = run("typed-tree-false-literal-refusal", [*type_arguments, "--noEmit", "typed_invalid.mts"], consumer, accepted=(1, 2))
        assert "TS2322" in invalid_type and "not assignable" in invalid_type
        (consumer / "service.rs").write_text('pub fn greet(input:&str)->String{format!("Hello, {}!",input)}\n')
        (consumer / "runtime.rs").write_text('mod service;mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:example:command:create-user").unwrap();println!("{}",bindings::dispatch(id,"Ada"));}\n')
        no_node = {"PATH": "/usr/bin:/bin"}
        run("runtime-build", [rustc, "--edition=2024", "runtime.rs", "-o", "runtime"], consumer, env)
        assert run("runtime", [consumer / "runtime"], consumer, no_node).strip() == "Hello, Ada!"
        python_env = {**env, "PYTHONPATH": str(source / "sdk/python")}
        python_engine = json.loads(run("python-sdk", [sys.executable, "-B", "-c", 'from patamaps import Patamaps;import json,sys;print(json.dumps(Patamaps(sys.argv[1]).run_json(["engine"])))', cli], consumer, python_env))
        assert python_engine == expected
        module = consumer / "node_modules/patamaps-native-sdk-draft"
        copy_tree(source / "sdk/typescript", module)
        (consumer / "package.json").write_text('{"type":"module"}\n')
        (consumer / "sdk.mjs").write_text('import{Patamaps}from"patamaps-native-sdk-draft";console.log(JSON.stringify(new Patamaps(process.argv[2]).runJson(["engine"])));\n')
        assert json.loads(run("typescript-sdk", [node_runtime(), consumer / "sdk.mjs", cli], consumer)) == expected
        receipt.update(status="passed", distribution=distribution, sourceInventoryEntries=len(inventory), engines=expected, nativeConsumption="Hello, Ada!", customEvaluatorBinding=generation["customConstraintEvaluators"][0], memoryHost=memory, memoryConsumerSourceDigest=digest(memory_source.read_bytes()), sourceInspection=source_report, sourceConsumerDigest=digest(source_consumer.read_bytes()), sourceCliReceipt=source_cli["receipt"], typedTree=typed_tree, typescriptTreeRuntime=tree_runtime, typedConsumerSourceDigest=digest(typed_source.read_bytes()), completedAtUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status":receipt["status"],"receipt":path.relative_to(ROOT).as_posix()}),flush=True)


if __name__ == "__main__":
    main()
