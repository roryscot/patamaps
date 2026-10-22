"""Freshly install the published CLI from crates.io and use it in an isolated Rust consumer."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = "patamaps-cli"
VERSION = "0.1.0-alpha.1"


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cargo", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == "Linux" and platform.machine() == "x86_64", "Use the isolated Linux x86_64 runner"
    cargo = args.cargo.resolve(strict=True)
    rustc = cargo.with_name("rustc")
    assert rustc.is_file(), "Rustup rustc proxy must accompany Cargo"
    work = args.work_root.resolve() / "patamaps-published-cli-install"
    output = args.output.resolve()
    assert not work.exists(), "Use a fresh registry-install workspace"
    work.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=False)
    cargo_home = work / "cargo-home"
    assert not cargo_home.exists(), "Registry install must start with an absent Cargo home"
    target = work / "install-target"
    install_root = work / "install-root"
    consumer = work / "consumer"
    consumer.mkdir()
    env = {
        **os.environ,
        "CARGO_HOME": str(cargo_home),
        "CARGO_TARGET_DIR": str(target),
        "CARGO_INCREMENTAL": "0",
        "CARGO_PROFILE_RELEASE_DEBUG": "0",
        "RUSTUP_TOOLCHAIN": "1.99.0",
    }
    env["RUSTUP_HOME"] = os.environ.get("RUSTUP_HOME", str(Path.home() / ".rustup"))
    commands = []
    receipt = {
        "schema": "patamaps.crates-io-fresh-cli-install.v1",
        "status": "running",
        "crate": CRATE,
        "version": VERSION,
        "registry": "crates.io",
        "host": {"platform": platform.platform(), "architecture": platform.machine()},
        "isolation": {"freshCargoHome": True, "pathInstall": False, "cargoHome": str(cargo_home)},
        "commands": commands,
    }
    receipt_path = output / "receipt.json"

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    def run(label, argv, cwd, timeout=1200):
        stdout_path = output / f"{label}.stdout.log"
        stderr_path = output / f"{label}.stderr.log"
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            result = subprocess.run(
                [str(arg) for arg in argv], cwd=cwd, env=env,
                stdout=stdout, stderr=stderr, timeout=timeout,
            )
        entry = {
            "label": label,
            "argv": [str(arg) for arg in argv],
            "cwd": str(cwd),
            "exitCode": result.returncode,
            "stdout": {"path": stdout_path.name, "digest": digest(stdout_path.read_bytes())},
            "stderr": {"path": stderr_path.name, "digest": digest(stderr_path.read_bytes())},
        }
        commands.append(entry)
        save()
        if result.returncode:
            raise RuntimeError(f"{label} failed with exit code {result.returncode}")
        return stdout_path.read_text()

    try:
        run("cargo-version", [cargo, "--version"], work)
        rustc_version = run("rustc-version", [rustc, "--version"], work)
        run("install", [cargo, "install", CRATE, "--version", VERSION, "--locked", "--root", install_root], work, timeout=2400)
        binary = install_root / "bin" / "patamaps"
        assert binary.is_file(), "Published package did not install the documented patamaps binary"
        version_output = run("binary-version", [binary, "--version"], consumer).strip()
        assert VERSION in version_output, f"Installed binary reports unexpected version: {version_output}"
        run("binary-help", [binary, "--help"], consumer)
        engine = json.loads(run("binary-engine", [binary, "engine"], consumer))
        assert isinstance(engine, dict) and engine, "Installed engine command returned no description"

        fixture_paths = {
            "graph.json": ROOT / "fixtures/routing/graph.json",
            "policy.json": ROOT / "fixtures/routing/policy.json",
            "projection-spec.json": ROOT / "fixtures/routing/projection-spec.json",
            "routing.json": ROOT / "relation-packs/routing.json",
        }
        fixture_digests = {}
        for name, source in fixture_paths.items():
            destination = consumer / name
            shutil.copyfile(source, destination)
            fixture_digests[name] = digest(destination.read_bytes())
        run("consumer-validate", [binary, "validate", "graph.json", "--relation-pack", "routing.json"], consumer)
        generated = consumer / "patamaps_generated.rs"
        run(
            "consumer-link",
            [binary, "link", "graph.json", "policy.json", "projection-spec.json",
             "--relation-pack", "routing.json", "--as-of", "2026-10-21T00:00:00Z",
             "--format", "rust", "--output", generated.name],
            consumer,
        )
        assert generated.is_file() and generated.stat().st_size > 0, "Installed CLI did not emit Rust"

        rust_consumer = work / "rust-consumer"
        (rust_consumer / "src").mkdir(parents=True)
        (rust_consumer / "Cargo.toml").write_text(
            '[package]\nname = "patamaps_registry_consumer_smoke"\nversion = "0.1.0"\nedition = "2024"\n\n[workspace]\n'
        )
        shutil.copyfile(generated, rust_consumer / "src/patamaps_generated.rs")
        (rust_consumer / "src/main.rs").write_text(
            '#[allow(dead_code)]\nmod correspondence { include!("patamaps_generated.rs"); }\nfn main() {}\n'
        )
        run("generated-rust-consumer-check", [cargo, "check", "--offline", "--manifest-path", rust_consumer / "Cargo.toml"], work, timeout=300)

        archive_matches = sorted(cargo_home.glob("registry/cache/*/patamaps-cli-" + VERSION + ".crate"))
        assert len(archive_matches) == 1, f"Expected exactly one downloaded CLI crate archive, found {len(archive_matches)}"
        receipt.update({
            "status": "passed",
            "cargoHomeWasInitiallyAbsent": True,
            "rustcVersion": rustc_version.strip(),
            "binaryVersion": version_output,
            "binaryDigest": digest(binary.read_bytes()),
            "engineDescriptionDigest": digest(json.dumps(engine, sort_keys=True, separators=(",", ":")).encode()),
            "fixtureDigests": fixture_digests,
            "generatedRustDigest": digest(generated.read_bytes()),
            "consumer": "cargo check --offline compiled generated Rust from a relocated scratch project",
            "downloadedCrateArchive": digest(archive_matches[0].read_bytes()),
            "downloadedCrateArchiveCount": len(archive_matches),
            "sourceCheckoutUsedAsDependency": False,
            "completedFromCratesIo": True,
        })
    except BaseException as error:
        receipt.update({"status": "failed", "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        save()
        print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}), flush=True)


if __name__ == "__main__":
    main()
