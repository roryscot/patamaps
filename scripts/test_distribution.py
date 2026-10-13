"""Install the actual bundle in a disposable directory outside this checkout."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("distribution", type=Path)
parser.add_argument("--node", type=Path, required=True)
parser.add_argument("--tsc", type=Path, required=True)
parser.add_argument("--reference", type=Path, required=True)
parser.add_argument("--output", type=Path, help="Retain identified installation and consumer results")
args = parser.parse_args()
receipt = json.loads((args.distribution / "distribution.json").read_text())
tools = Path.home() / ".cargo/bin"
env = {**os.environ, "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0"}

def run(argv, cwd, expected=0, env=env):
    result = subprocess.run([str(a) for a in argv], cwd=cwd, env=env, text=True, capture_output=True)
    assert result.returncode == expected, f"{argv}\n{result.returncode}\n{result.stdout}\n{result.stderr}"
    return result.stdout

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")

with tempfile.TemporaryDirectory(prefix="patamaps-install-") as temporary:
    work = Path(temporary)
    for key in ["sourceArchive", "nativeArchive"]:
        raw = (args.distribution / receipt[key]["path"]).read_bytes()
        assert "sha256:" + hashlib.sha256(raw).hexdigest() == receipt[key]["digest"]
    with tarfile.open(args.distribution / receipt["sourceArchive"]["path"]) as archive:
        archive.extractall(work, filter="data")
    source = next(work.glob("patamaps-draft-*"))
    inventory = json.loads((source / "source-inventory.json").read_text())
    assert "sha256:" + hashlib.sha256((source / "source-inventory.json").read_bytes()).hexdigest() == receipt["sourceInventoryDigest"]
    assert len({entry["path"] for entry in inventory}) == len(inventory)
    assert {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()} == {entry["path"] for entry in inventory} | {"source-inventory.json"}
    for entry in inventory:
        raw = (source / entry["path"]).read_bytes()
        assert len(raw) == entry["bytes"] and "sha256:" + hashlib.sha256(raw).hexdigest() == entry["digest"]
    native = work / "native"
    native.mkdir()
    with tarfile.open(args.distribution / receipt["nativeArchive"]["path"]) as archive:
        archive.extractall(native, filter="data")
    packaged_cli = next(native.glob("*/bin/patamaps"))
    assert "sha256:" + hashlib.sha256(packaged_cli.read_bytes()).hexdigest() == receipt["binaryDigest"]
    assert json.loads(run([packaged_cli, "engine"], work)) == receipt["engines"]
    if "activatorBinaryDigest" in receipt:
        activator = packaged_cli.with_name("patamaps-activator")
        assert "sha256:" + hashlib.sha256(activator.read_bytes()).hexdigest() == receipt["activatorBinaryDigest"]
    installed = work / "installed"
    # Reuse only compiler object cache, never source or an existing installed CLI.
    env["CARGO_TARGET_DIR"] = str(ROOT / "target/package-test")
    run([tools / "cargo", "install", "--path", source / "crates/patamaps-cli", "--locked", "--offline", "--debug", "--root", installed], work)
    cli = installed / "bin/patamaps"
    assert json.loads(run([cli, "engine"], work)) == receipt["engines"]
    consumer = work / "consumer"
    consumer.mkdir()
    (consumer / "src").mkdir()
    (consumer / "Cargo.toml").write_text(f'''[package]\nname="patamaps-sdk-consumer"\nversion="0.0.0"\nedition="2024"\n[dependencies]\npatamaps-contracts={{path={json.dumps(str(source / 'crates/patamaps-contracts'))}}}\npatamaps-core={{path={json.dumps(str(source / 'crates/patamaps-core'))}}}\n''')
    (consumer / "src/main.rs").write_text('''fn main() { let graph: patamaps_contracts::GraphDocument = patamaps_contracts::parse(&std::fs::read("graph.json").unwrap()).unwrap(); let pack = patamaps_contracts::parse(&std::fs::read("pack.json").unwrap()).unwrap(); let core = patamaps_contracts::parse(&std::fs::read("core.json").unwrap()).unwrap(); let checked = patamaps_core::CheckedGraph::check(graph, vec![pack, core]).unwrap(); println!("{}", checked.document().entities.len()); }''')
    for target, path in [("graph.json", "fixtures/routing/graph.json"), ("pack.json", "relation-packs/routing.json"), ("core.json", "relation-packs/core.json")]:
        shutil.copyfile(source / path, consumer / target)
    expected_entities = len(json.loads((consumer / "graph.json").read_text())["entities"])
    assert int(run([tools / "cargo", "run", "--offline", "--quiet"], consumer)) == expected_entities
    config = {"schemaVersion": "0.1.0", "documentType": "workspace-config", "id": "urn:workspace:installed", "namespace": "installed", "revision": "1",
              "sources": [{"id": "urn:source:installed", "adapter": "portable-shard", "path": "graph.json"}], "packs": ["pack.json"], "policy": "policy.json",
              "projections": [{"path": "projection.json", "emissions": [{"path": "bindings.rs", "language": "rust", "bindingSlot": "handler"}, {"path": "bindings.ts", "language": "typescript", "bindingSlot": "handler"}]}],
              "context": {}, "evaluatedAt": "2026-10-10T12:00:00Z"}
    graph = json.loads((consumer / "graph.json").read_text())
    handler = next(e for e in graph["entities"] if e["kind"] == "routing:handler")
    handler["locators"] = [{"uri": "rust:crate::service::greet"}, {"uri": "typescript:./handler.ts#greet"}]
    write(consumer / "graph.json", graph)
    policy = json.loads((source / "fixtures/routing/policy.json").read_text()); policy["graph"] = {"id": config["id"], "revision": "1"}
    write(consumer / "policy.json", policy); write(consumer / "config.json", config)
    shutil.copyfile(source / "fixtures/routing/projection-spec.json", consumer / "projection.json")
    no_node = {**env, "PATH": "/usr/bin:/bin"}
    assert shutil.which("node", path=no_node["PATH"]) is None
    generated = json.loads(run([cli, "generate", "config.json", "--root", consumer], consumer, env=no_node))
    packaged_generated = json.loads(run([packaged_cli, "generate", "config.json", "--root", consumer], consumer, env=no_node))
    assert packaged_generated == generated
    baseline = generated["baseline"]; write(consumer / "baseline.json", baseline); original_baseline = (consumer / "baseline.json").read_bytes()
    for name, content in baseline["outputs"].items(): (consumer / name).write_text(content)
    (consumer / "service.rs").write_text('pub fn greet(input: &str) -> String { format!("Hello, {}!", input) }')
    (consumer / "main.rs").write_text('mod service; mod bindings; fn main() { let id = bindings::SemanticId::parse("urn:example:command:create-user").unwrap(); println!("{}", bindings::dispatch(id, "Ada")); }')
    run([tools / "rustc", "--edition=2024", "main.rs", "-o", "consumer"], consumer, env=no_node)
    assert run([consumer / "consumer"], consumer, env=no_node).strip() == "Hello, Ada!"
    (consumer / "handler.ts").write_text('export function greet(input: string): string { return `Hello, ${input}!`; }')
    (consumer / "package.json").write_text('{"type":"module"}')
    (consumer / "consumer.ts").write_text('import {dispatch} from "./bindings.js"; console.log(dispatch("urn:example:command:create-user", "Ada"));')
    run([args.node, args.tsc, "--strict", "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext", "--outDir", "dist", "consumer.ts", "bindings.ts"], consumer)
    assert run([args.node, "dist/consumer.js"], consumer).strip() == "Hello, Ada!"
    write(consumer / "capture.json", baseline["captures"][0])
    shutil.copytree(source / "sdk/python/patamaps", installed / "python/patamaps")
    python_env = {**no_node, "PYTHONPATH": str(installed / "python")}
    python = shutil.which("python3")
    result = run([python, "-c", "from patamaps import Patamaps; import sys; print(Patamaps(sys.argv[1]).check(sys.argv[2], sys.argv[3], sys.argv[4])['status'])", cli, consumer / "config.json", consumer / "baseline.json", consumer], consumer, env=python_env)
    assert result.strip() == "unchanged"
    shutil.copytree(source / "sdk/typescript", consumer / "node_modules/patamaps-native-sdk-draft")
    (consumer / "sdk.ts").write_text('import {Patamaps} from "patamaps-native-sdk-draft"; const cli = new Patamaps(process.argv[2]!); console.log((cli.replay("capture.json") as {status:string}).status);')
    # Keep SDK test free of @types/node; declare only the fixture argv contract.
    (consumer / "argv.d.ts").write_text('declare const process: {argv: string[]};')
    run([args.node, args.tsc, "--strict", "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext", "--outDir", "dist", "sdk.ts", "argv.d.ts"], consumer)
    assert json.loads(run([cli, "replay", "capture.json"], consumer))["status"] == "verified"
    assert run([args.node, "dist/sdk.js", cli], consumer).strip() == "verified"
    graph["entities"][0]["label"] = "changed installed source"; write(consumer / "graph.json", graph)
    drift = json.loads(run([cli, "check", "config.json", "baseline.json", "--root", consumer], consumer, expected=2))
    assert drift["status"] == "drift" and (consumer / "baseline.json").read_bytes() == original_baseline
    # Exercise the owned discovery package through the installed native host.
    # TypeScript is explicit optional tooling; no MetaMap package is loaded.
    shutil.copytree(source / "adapters", consumer / "adapters")
    shutil.copytree(args.reference.resolve() / "node_modules/typescript", consumer / "node_modules/typescript")
    discovery_code = sorted(str(path.relative_to(consumer)) for path in (consumer / "adapters").rglob("*") if path.is_file() and (path.suffix in {".mjs", ".js"} or path.name == "package.json"))
    discovery_code += ["node_modules/typescript/lib/typescript.js", "node_modules/typescript/package.json"]
    discovery_code += sorted(str(path.relative_to(consumer)) for path in (consumer / "node_modules/patamaps-native-sdk-draft").rglob("*") if path.is_file() and path.suffix in {".mjs", ".js", ".json"})
    (consumer / "src/input.ts").write_text('import {z} from "zod"; export const Name = z.string();')
    config["sources"] = [{"id": "urn:source:framework", "adapter": "process", "invocation": {"executable": str(args.node.resolve()), "arguments": [str(consumer / "adapters/metamap-process.mjs")], "codeInputs": discovery_code, "bounds": {"maximumElapsedMs": 3000, "maximumStdoutBytes": 1048576, "maximumStderrBytes": 65536}}, "inputs": ["src/input.ts"], "config": {"adapter": "typescript-zod", "roots": ["src"]}}]
    # Empty selection remains an explicit valid discovery-only consumer here.
    policy["mappings"] = []; policy["constraints"] = []; write(consumer / "policy.json", policy)
    write(consumer / "projection.json", {"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:projection:discovery","select":{"kinds":["zod-schema"]},"slots":[]})
    config["projections"][0]["emissions"] = []; write(consumer / "config.json", config)
    discovered = json.loads(run([cli, "generate", "config.json", "--root", consumer], consumer))
    assert len(discovered["baseline"]["captures"][0]["inputs"]["graph"]["entities"]) > 0
    assert discovered["baseline"]["discovery"][0]["adapter"] == "process"
    assert discovered["cacheHits"] == 0
    # Run migrated consumers from the extracted source, using the freshly
    # installed CLI. Their caches and generated files stay outside this checkout.
    run([python, source / "scripts/test_binding_matrix.py", "--cli", cli, "--node", args.node, "--output", work / "binding-matrix.json"], source)
    run([python, source / "scripts/test_scientific.py", "--cli", cli, "--node", args.node, "--tsc", args.tsc, "--output", work / "scientific"], source)
    run([python, source / "scripts/test_adapter_bridge.py", "--cli", cli, "--node", args.node, "--reference", args.reference, "--output", work / "adapters.json"], source)
    run([python, source / "scripts/test_lifecycle_pure.py", "--cli", cli, "--output", work / "lifecycle-pure.json"], source)
    verified = {"status":"passed", "distribution":receipt, "sourceInventoryEntries":len(inventory),
                "installedEngine":json.loads(run([cli,"engine"],work)),
                "installCommand":[str(tools/"cargo"),"install","--path","<extracted-source>/crates/patamaps-cli","--locked","--offline","--debug","--root","<disposable-install>"],
                "sdk":"Rust library and installed Python/TypeScript wrappers executed",
                "nativePortable":"Packaged native binary and source-installed CLI generated identical artifacts; Rust consumer ran with Node absent from PATH",
                "drift":"Refused without replacing accepted baseline",
                "bindingMatrix":json.loads((work/"binding-matrix.json").read_text()),
                "scientific":json.loads((work/"scientific/acceptance.json").read_text()),
                "adapters":json.loads((work/"adapters.json").read_text()),
                "lifecyclePure":json.loads((work/"lifecycle-pure.json").read_text()),
                "hostSdkRoot":env.get("SDKROOT"), "activation":"not-evaluated",
                "hostPlatform":platform.platform(),
                "scope":f"Disposable {platform.system()} source/native installation; protected host acceptance is recorded separately"}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);write(args.output,verified)
    print("PASS: clean native/source installation, SDKs, generated consumers, preserved baseline, no-Node portable flow, 22 migrated binding cases, scientific lookup, all five adapters and portable full-lifecycle stages.")
