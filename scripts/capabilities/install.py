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


def main():
    ensure_guarded()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    output = ROOT / "docs/acceptance/capabilities" / f"installed-{stamp}"
    output.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="installed-", dir=ROOT / ".tools/capabilities"))
    env = {**os.environ, "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    env["CARGO_TARGET_DIR"] = str(ROOT / "target/package-test")
    if sys.platform == "darwin":
        env["SDKROOT"] = "/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk"
    cargo = Path.home() / ".cargo/bin/cargo"
    rustc = Path.home() / ".cargo/bin/rustc"
    commands = []
    receipt = {"status": "running", "scope": "Development source/native package installation, Rust library customization and generated compiler-free Rust consumer, Python/TypeScript installed wrappers. Protected Linux host and complete scientific/discovery migrations are recorded separately.", "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "deleted": [], "registryPublication": "not-requested", "productionActivation": "not-requested"}
    path = output / "receipt.json"

    def save():
        path.write_text(json.dumps(receipt, indent=2) + "\n")

    def run(label, argv, cwd=ROOT, environment=env):
        result = subprocess.run([str(v) for v in argv], cwd=cwd, env=environment, capture_output=True)
        item = {"label": label, "argv": [str(v) for v in argv], "exitCode": result.returncode}
        for stream in ["stdout", "stderr"]:
            raw = getattr(result, stream)
            log = output / f"{label}.{stream}.log"
            log.write_bytes(raw)
            item[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": digest(raw)}
        commands.append(item)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect retained logs in {output}")
        return result.stdout.decode()

    save()
    try:
        package = work / "package"
        run("package", [sys.executable, "-B", ROOT / "scripts/package.py", "--binary", ROOT / "target/debug/patamaps", "--build-profile", "development", "--output", package, "--acceptance-output", output])
        distribution = json.loads((package / "distribution.json").read_text())
        expected = {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}
        assert distribution["engines"] == expected
        for kind in ["sourceArchive", "nativeArchive"]:
            archive = package / distribution[kind]["path"]
            assert digest(archive.read_bytes()) == distribution[kind]["digest"]
        extracted = work / "source"
        extracted.mkdir()
        with tarfile.open(package / distribution["sourceArchive"]["path"]) as archive:
            archive.extractall(extracted, filter="data")
        source, = extracted.iterdir()
        raw_inventory = (source / "source-inventory.json").read_bytes()
        assert digest(raw_inventory) == distribution["sourceInventoryDigest"]
        inventory = json.loads(raw_inventory)
        assert distribution["acceptanceOutputOutsideSourcePayload"] == output.relative_to(ROOT).as_posix()
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
        dependencies = "\n".join(f'{name}={{path={json.dumps(str(source / "crates" / name))}}}' for name in ["patamaps-contracts", "patamaps-core", "patamaps-projection"])
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
        generation = json.loads(run("rust-sdk", [cargo, "run", "--offline", "--quiet"], consumer))
        assert generation["customConstraintEvaluators"][0]["evaluator"]["digest"] == digest((consumer / "src/main.rs").read_bytes())
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
        receipt.update(status="passed", distribution=distribution, sourceInventoryEntries=len(inventory), engines=expected, nativeConsumption="Hello, Ada!", customEvaluatorBinding=generation["customConstraintEvaluators"][0], completedAtUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status":receipt["status"],"receipt":path.relative_to(ROOT).as_posix()}),flush=True)


if __name__ == "__main__":
    main()
