"""Execute Linux native/UID/crash acceptance on an isolated root test host.

Production trust/bootstrap/activation are not performed. Keep all fixtures and
logs, including failed runs. This runner is for CI Linux hosts, not macOS VMs.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from identity import identities


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cargo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--architecture", choices=["x86_64", "aarch64"], required=True)
    args = parser.parse_args()
    assert platform.system() == "Linux" and os.geteuid() == 0, "Use an isolated Linux root test host"
    assert platform.machine() == args.architecture, "Verify the actual required architecture"
    # Rustup proxies select their command from argv[0]; resolving cargo's
    # symlink to rustup changes "cargo build" into a different command.
    cargo = args.cargo.absolute()
    assert cargo.is_file()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixtures = args.fixtures.absolute()
    assert not fixtures.exists(), "Use a fresh fixture root; preserve earlier runs"
    fixtures.mkdir(mode=0o755)
    env = {**os.environ, "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0", "PATAMAPS_TEST_FIXTURE_ROOT": str(fixtures), "TMPDIR": str(fixtures)}
    env.pop("SDKROOT", None)
    inputs = [ROOT / name for name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"]]
    for directory in ["crates", "vendor", "fixtures", "relation-packs", "schemas"]:
        inputs.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    inventory = [{"path": p.relative_to(ROOT).as_posix(), "digest": digest(p.read_bytes())} for p in sorted(set(inputs))]
    commands = []
    report = {"status": "running", "host": {"platform": platform.platform(), "architecture": platform.machine(), "effectiveUid": os.geteuid()}, "sourceRevision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "sourceInventory": inventory, "fixtures": str(fixtures), "commands": commands, "scope": "Actual native Linux root/independent-UID, concurrent stale-base, five-phase SIGKILL and governed consumer move/rollback tests with debug and release production binaries. All fixture material is retained; no production host configuration is used.", "deleted": [], "productionActivation": "not-requested"}
    path = output / "receipt.json"

    def save():
        path.write_text(json.dumps(report, indent=2) + "\n")

    def run(label, argv, extra=None):
        with (output / f"{label}.stdout.log").open("wb") as stdout, (output / f"{label}.stderr.log").open("wb") as stderr:
            result = subprocess.run([str(v) for v in argv], cwd=ROOT, env={**env, **(extra or {})}, stdout=stdout, stderr=stderr)
        item = {"label": label, "argv": [str(v) for v in argv], "exitCode": result.returncode}
        for stream in ["stdout", "stderr"]:
            log = output / f"{label}.{stream}.log"
            item[stream] = {"path": log.name, "digest": digest(log.read_bytes())}
        commands.append(item)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed; preserve and inspect {output}")

    save()
    try:
        run("build-debug", [cargo, "build", "--workspace", "--locked"])
        run("rustfmt", [cargo, "fmt", "--all", "--", "--check"])
        run("clippy", [cargo, "clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"])
        binaries = {"PATAMAPS_TEST_COMPILER_BINARY": str(ROOT / "target/debug/patamaps"), "PATAMAPS_TEST_ACTIVATOR_BINARY": str(ROOT / "target/debug/patamaps-activator")}
        run("native-debug", [cargo, "test", "--workspace", "--locked", "--", "--test-threads=1"], binaries)
        run("build-release", [cargo, "build", "--release", "--locked", "-p", "patamaps-cli", "-p", "patamaps-activator"])
        binaries = {"PATAMAPS_TEST_COMPILER_BINARY": str(ROOT / "target/release/patamaps"), "PATAMAPS_TEST_ACTIVATOR_BINARY": str(ROOT / "target/release/patamaps-activator")}
        run("release-host", [cargo, "test", "--locked", "-p", "patamaps-activator", "--lib", "--", "--test-threads=1"], binaries)
        expected = {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}
        for profile in ["debug", "release"]:
            cli = ROOT / f"target/{profile}/patamaps"
            actual = json.loads(subprocess.check_output([cli, "engine"], cwd=ROOT))
            assert actual == expected
        for item in inventory:
            assert digest((ROOT / item["path"]).read_bytes()) == item["digest"], item["path"]
        report.update(status="passed", engines=expected, sourceUnchanged=True, binaries={f"{profile}/{binary}": digest((ROOT / f"target/{profile}/{binary}").read_bytes()) for profile in ["debug", "release"] for binary in ["patamaps", "patamaps-activator"]}, completedAtUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status": report["status"], "receipt": str(path)}), flush=True)


if __name__ == "__main__":
    main()
