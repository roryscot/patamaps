#!/usr/bin/env python3
"""Exercise locally packaged Rust library crates in fresh consumer workspaces.

The command creates new work under --work and never publishes or deletes files.
"""
import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("patamaps-contracts", "patamaps-core")
CARGO = ("cargo", "+1.99.0")


def run(name, argv, cwd, env, report):
    print(f"checking {name}", flush=True)
    subprocess.run([*CARGO, *argv], cwd=cwd, env=env, check=True)
    report["completed"].append(name)


def unpack(archive, destination, expected_root):
    seen = set()
    total = 0
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if len(members) > 4096:
            raise ValueError("package member limit exceeded")
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or not name.parts or ".." in name.parts
                    or name.parts[0] != expected_root
                    or not (member.isfile() or member.isdir())
                    or name.as_posix() in seen):
                raise ValueError("unsafe or duplicate package member")
            seen.add(name.as_posix())
            total += member.size
            if total > 50_000_000:
                raise ValueError("package size limit exceeded")
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as src, target.open("xb") as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    args = parser.parse_args()
    work = args.work.absolute()
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, CARGO_INCREMENTAL="0", CARGO_PROFILE_DEV_DEBUG="0",
               CARGO_PROFILE_TEST_DEBUG="0", CARGO_TARGET_DIR=str(work / "target"))
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    report = {"status": "running", "version": version, "published": False,
              "completed": [], "archives": []}
    try:
        run("package", ["package", "--locked", "--no-verify",
                        "-p", PACKAGES[0], "-p", PACKAGES[1],
                        "--target-dir", str(work / "package-target")], ROOT, env, report)
        unpacked = work / "unpacked"
        unpacked.mkdir()
        for name in PACKAGES:
            package_root = f"{name}-{version}"
            archive = work / "package-target/package" / f"{package_root}.crate"
            raw = archive.read_bytes()
            report["archives"].append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(),
                                       "bytes": len(raw)})
            unpack(archive, unpacked, package_root)

        core = unpacked / f"patamaps-core-{version}"
        contracts = unpacked / f"patamaps-contracts-{version}"
        example = (ROOT / "examples/rust-library-consumer/src/main.rs").read_bytes()
        for flavor in ("native", "default"):
            consumer = work / f"consumer-{flavor}"
            (consumer / "src").mkdir(parents=True)
            (consumer / "src/main.rs").write_bytes(example)
            feature = ", default-features = false" if flavor == "native" else ""
            manifest = (
                f'[package]\nname = "packaged-consumer-{flavor}"\n'
                'version = "0.0.0"\nedition = "2024"\npublish = false\n\n'
                '[workspace]\n\n[dependencies]\n'
                f'patamaps-core = {{ path = {json.dumps(str(core))}{feature} }}\n\n'
                '[patch.crates-io]\n'
                f'patamaps-contracts = {{ path = {json.dumps(str(contracts))} }}\n'
            )
            (consumer / "Cargo.toml").write_text(manifest)
            run(f"{flavor}-lock", ["generate-lockfile"], consumer, env, report)
            run(f"{flavor}-consumer", ["run", "--locked", "--jobs", "2"], consumer, env, report)

        workspace = (
            '[workspace]\nresolver = "3"\n'
            f'members = [{json.dumps(core.name)}, {json.dumps(contracts.name)}]\n\n'
            '[patch.crates-io]\n'
            f'patamaps-contracts = {{ path = {json.dumps(contracts.name)} }}\n'
        )
        (unpacked / "Cargo.toml").write_text(workspace)
        run("packaged-lock", ["generate-lockfile"], unpacked, env, report)
        run("packaged-core-tests", ["test", "--locked", "-p", "patamaps-core",
                                    "--test", "in_memory_library", "--test", "registry",
                                    "--test", "legacy_pack", "--jobs", "2"], unpacked, env, report)
        run("packaged-contracts-tests", ["test", "--locked", "-p", "patamaps-contracts",
                                         "--tests", "--jobs", "2"], unpacked, env, report)
        report["status"] = "passed"
    finally:
        (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
