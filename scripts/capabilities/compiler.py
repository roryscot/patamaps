"""Verify the complete native compiler workflow; retain exact inputs and logs.

This milestone uses substantive native controls and unchanged reference drivers.
It does not evaluate protected host activation, installed packages or JS quirks.
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from identity import identities
from storage_guard import ensure_guarded, node_runtime


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def inventory():
    paths = [ROOT / name for name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"]]
    for name in ["crates", "vendor/icu_collator", "relation-packs", "schemas", "fixtures/laws", "fixtures/routing"]:
        paths.extend(p for p in (ROOT / name).rglob("*") if p.is_file())
    paths.extend([
        ROOT / "scripts/capabilities/compiler.py",
        ROOT / "scripts/capabilities/retained_driver.py",
        ROOT / "scripts/reference/semantic.py",
        ROOT / "scripts/reference/evaluate_semantic.mjs",
        ROOT / "scripts/test_lifecycle_pure.py",
        ROOT / "scripts/test_native.py",
        ROOT / "fixtures/conformance.json",
        ROOT / "fixtures/parity/supplement.json",
    ])
    return [
        {"path": p.relative_to(ROOT).as_posix(), "digest": digest(p.read_bytes())}
        for p in sorted(set(paths))
    ]


def main():
    ensure_guarded()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    output = ROOT / "docs/acceptance/capabilities" / f"compiler-{stamp}"
    output.mkdir(parents=True)
    retained_base = ROOT / ".tools/capabilities"
    retained_base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="compiler-", dir=retained_base))
    reference = Path(os.environ.get("PATAMAPS_REFERENCE", "/Users/admin/dev/SEEDZ/metamap")).resolve()
    node = node_runtime()
    tsc = reference / "node_modules/typescript/lib/tsc.js"
    cargo = Path.home() / ".cargo/bin/cargo"
    cli = ROOT / "target/debug/patamaps"
    env = {
        **os.environ,
        "CARGO_INCREMENTAL": "0",
        "CARGO_PROFILE_DEV_DEBUG": "0",
        "CARGO_PROFILE_TEST_DEBUG": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if platform.system() == "Darwin":
        env["SDKROOT"] = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
    source = inventory()
    commands = []
    receipt = {
        "milestone": "M1",
        "status": "running",
        "scope": "Native built-in compiler and explicit Rust constraint extensions, proofs, uncertainty/risk, replay, inspection/repair and real generated Rust/TypeScript consumers. Custom callbacks remain outside portable capture/replay, as required by the reference. Protected activation, installed packages and platform acceptance remain open.",
        "host": {"platform": platform.platform(), "architecture": platform.machine()},
        "sourceInventory": source,
        "retainedWork": work.relative_to(ROOT).as_posix(),
        "referenceEngine": "399747a4ad05a37cd8db1cedd53048fad2175be4",
        "commands": commands,
        "deleted": [],
        "productionActivation": "not-requested",
        "ownerAcceptance": "not-established",
    }
    path = output / "receipt.json"

    def save():
        path.write_text(json.dumps(receipt, indent=2) + "\n")

    def run(label, command):
        save()
        with (output / f"{label}.stdout.log").open("wb") as stdout, (output / f"{label}.stderr.log").open("wb") as stderr:
            result = subprocess.run([str(v) for v in command], cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        record = {"label": label, "argv": [str(v) for v in command], "exitCode": result.returncode}
        for stream in ["stdout", "stderr"]:
            log = output / f"{label}.{stream}.log"
            record[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": digest(log.read_bytes())}
        commands.append(record)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed; retained logs: {output}")

    def retained(label, driver, *arguments):
        run(label, [sys.executable, "-B", ROOT / "scripts/capabilities/retained_driver.py", "--retain-in", work / label, ROOT / driver, *arguments])

    save()
    try:
        run("build", [cargo, "build", "--locked", "--offline", "-p", "patamaps-cli"])
        run("portable-native", [cargo, "test", "--locked", "--offline", "--workspace", "--exclude", "patamaps-activator"])
        run("portable-activation", [cargo, "test", "--locked", "--offline", "-p", "patamaps-activator", "--test", "memory", "--test", "transport"])
        run("portable-activation-types", [cargo, "test", "--locked", "--offline", "-p", "patamaps-activator", "--doc"])
        retained("reference-semantic", "scripts/reference/semantic.py", reference, "--node", node, "--cli", cli, "--output", output / "reference-semantic.json")
        retained("lifecycle", "scripts/test_lifecycle_pure.py", "--cli", cli, "--output", output / "lifecycle.json")
        retained("native-consumers", "scripts/test_native.py", "--cli", cli, "--tsc", tsc, "--node", node)
        actual = json.loads(subprocess.check_output([cli, "engine"], cwd=ROOT, env=env))
        expected = identities(ROOT)
        assert actual == {
            "schemaVersion": "0.1.0",
            "documentType": "executor-description",
            **expected,
        }, "Binary/source executor identity mismatch"
        receipt["engines"] = actual
        comparison = json.loads((output / "reference-semantic.json").read_text())
        assert comparison["engineRevision"] == receipt["referenceEngine"]
        assert len(comparison["comparisons"]) == 40
        assert all(item["pass"] for item in comparison["comparisons"])
        lifecycle = json.loads((output / "lifecycle.json").read_text())
        assert lifecycle["nativeConsumption"] == "Hello, Ada!"
        assert lifecycle["capture"]["executor"] == actual["compiler"]
        run("reference-integrity", [sys.executable, "-B", ROOT / "scripts/test_source_integrity.py", reference, "--output", output / "reference-integrity.json"])
        run("rustfmt", [cargo, "fmt", "--all", "--", "--check"])
        run("clippy", [cargo, "clippy", "--locked", "--offline", "--workspace", "--all-targets", "--", "-D", "warnings"])
        assert source == inventory(), "Inputs changed during the milestone"
        receipt.update(
            status="passed",
            meaningfulReferenceCases=40,
            nativeConsumption="Hello, Ada!",
            sourceUnchanged=True,
            completedAtUtc=datetime.now(timezone.utc).isoformat(),
        )
    except BaseException as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status": receipt["status"], "receipt": path.relative_to(ROOT).as_posix()}), flush=True)


if __name__ == "__main__":
    main()
