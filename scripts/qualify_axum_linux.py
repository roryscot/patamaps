#!/usr/bin/env python3
"""Qualify pinned, existing Axum sources on Linux; never substitutes metadata for builds."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import time

UPSTREAM = "https://github.com/tokio-rs/axum.git"
REVISION = "fc78d5bcdb276bd6fb53cf2db55e91757eabb469"
MANIFESTS = ["Cargo.toml", "Cargo.lock", "axum/Cargo.toml",
             "axum-core/Cargo.toml", "axum-extra/Cargo.toml", "axum-macros/Cargo.toml"]
PACKAGES = ["axum", "axum-core", "axum-extra", "axum-macros"]


def digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    cli = args.cli.resolve(strict=True)
    work = args.work.resolve()
    evidence = args.evidence.resolve()
    assert not work.exists() and not evidence.exists(), "Use fresh retained paths"
    evidence.mkdir(parents=True)
    receipt = {"status": "failed", "upstream": UPSTREAM, "sourceCommit": REVISION,
               "commands": [], "controls": [], "filesDeleted": 0,
               "applicationAcceptance": False, "linuxTargetCompilationEstablished": False,
               "limitations": ["Public library workspace, not a deployed HTTP application.",
                               "Cargo registry cache is external; this is not hermetic dependency closure.",
                               "No actual Next deployment or image/browser acceptance is established."]}
    owner = work / "source"

    def run(label, command, cwd=None, data=None, expected=0, timeout=900):
        began = time.monotonic()
        with (evidence / (label + ".stdout.log")).open("xb") as out, \
                (evidence / (label + ".stderr.log")).open("xb") as err:
            result = subprocess.run([str(x) for x in command], cwd=cwd, input=data,
                                    stdout=out, stderr=err, timeout=timeout)
        receipt["commands"].append({"label": label, "argv": [str(x) for x in command],
                                    "exitCode": result.returncode,
                                    "seconds": round(time.monotonic() - began, 3)})
        print(json.dumps(receipt["commands"][-1]), flush=True)
        assert result.returncode == expected, (label, result.returncode)
        return (evidence / (label + ".stdout.log")).read_bytes()

    def tracked_inventory():
        names = run("inventory-" + str(len(receipt["commands"])),
                    ["git", "ls-files", "-z"], cwd=owner).split(b"\0")
        return {name.decode(): digest(owner / os.fsdecode(name)) for name in names if name}

    try:
        assert platform.system() == "Linux" and platform.machine() == "x86_64"
        work.mkdir(parents=True)
        # Keep the owner outside Patamaps and reject inherited Cargo configuration.
        repository = Path(__file__).resolve().parent.parent
        assert not owner.is_relative_to(repository)
        for ancestor in owner.parents:
            for name in ["rust-toolchain", "rust-toolchain.toml", ".cargo/config", ".cargo/config.toml"]:
                assert not (ancestor / name).exists(), ("Ambient Cargo configuration", ancestor / name)
        run("source-init", ["git", "init", owner])
        run("source-fetch", ["git", "fetch", "--depth=1", UPSTREAM, REVISION], cwd=owner)
        run("source-checkout", ["git", "checkout", "--detach", "FETCH_HEAD"], cwd=owner)
        assert run("source-head", ["git", "rev-parse", "HEAD"], cwd=owner).decode().strip() == REVISION
        before = tracked_inventory()
        assert before and not run("source-status-before", ["git", "status", "--porcelain=v1"], cwd=owner)
        assert not list(owner.rglob("build.rs")), "Review upstream build scripts before changing the pin"
        cargo = Path(run("cargo-path", ["rustup", "which", "--toolchain", "1.99.0", "cargo"]).decode().strip())
        rustc = cargo.with_name("rustc")
        version = run("rustc-version", [rustc, "-vV"]).decode()
        assert "host: x86_64-unknown-linux-gnu" in version
        receipt.update(compilerDigest=digest(cli), cargoDigest=digest(cargo),
                       rustcDigest=digest(rustc), rustcVersion=version,
                       sourceFiles=len(before), sourceInventoryDigest="sha256:" +
                       hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest())
        cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))).resolve()
        os.environ["RUSTC"] = str(rustc)
        os.environ["CARGO_TARGET_DIR"] = str(work / "target")
        # An explicit preparation phase precedes all offline observation and build phases.
        lock_digest = digest(owner / "Cargo.lock")
        run("fetch-locked-linux", [cargo, "fetch", "--locked", "--target", "x86_64-unknown-linux-gnu"], cwd=owner)
        assert digest(owner / "Cargo.lock") == lock_digest
        inputs = [{"receipt": {"path": name, "digest": digest(owner / name),
                               "byteLength": (owner / name).stat().st_size},
                   "content": (owner / name).read_text()} for name in MANIFESTS]
        config = {"provider": "cargo", "nonsecretInputs": True, "manifest": "Cargo.toml",
                  "workspaceManifest": "Cargo.toml", "lockfile": "Cargo.lock",
                  "cargo": str(cargo), "cargoDigest": digest(cargo),
                  "rustc": str(rustc), "rustcDigest": digest(rustc),
                  "cargoHome": str(cargo_home), "platform": "x86_64-unknown-linux-gnu",
                  "features": ["axum/ws"], "defaultFeatures": True, "view": "resolved",
                  "workspaceMembers": "bounded-segment-globs"}
        request = {"schemaVersion": "0.1.0", "documentType": "adapter-request",
                   "profile": "patamaps-workspace-draft-1", "sourceId": "urn:qualification:actual-axum-linux",
                   "namespace": "actual-axum-linux", "config": config, "inputs": inputs,
                   "invocationDigest": "sha256:" + "0" * 64, "requestDigest": ""}
        request["requestDigest"] = json.loads(run("request-digest", [cli, "json", "digest"],
                                                 data=json.dumps(request).encode()))
        (evidence / "request.json").write_text(json.dumps(request, indent=2) + "\n")
        response = json.loads(run("native-linux-observation", [cli, "discover-native"], cwd=owner,
                                  data=json.dumps(request).encode(), timeout=120))
        assert response["requestDigest"] == request["requestDigest"]
        assert response["inputs"] == [item["receipt"] for item in inputs]
        observation = response["shard"]["metadata"]["observation"]
        assert observation["compilationEstablished"] is False
        assert observation["buildScriptsExecuted"] is False
        metadata = json.loads(observation["metadataBytes"])
        assert observation["metadataDigest"] == "sha256:" + hashlib.sha256(observation["metadataBytes"].encode()).hexdigest()
        packages = [entity["attributes"] for entity in response["shard"]["entities"]
                    if entity["kind"] == "cargo-package"]
        assert sorted(item["name"] for item in packages) == PACKAGES
        assert "ws" in next(item for item in packages if item["name"] == "axum")["featuresResolved"]
        receipt["controls"].append("actual-resolved-linux-metadata-with-explicit-ws")
        members = set(metadata["workspace_members"])
        messages = run("build-actual-workspace", [cargo, "build", "--workspace", "--lib", "--locked", "--offline",
                        "--features", "axum/ws", "--message-format=json"], cwd=owner)
        artifacts = []
        compiled = set()
        for line in messages.splitlines():
            message = json.loads(line)
            if message.get("reason") == "compiler-artifact" and message.get("package_id") in members:
                compiled.add(message["package_id"])
                for name in message["filenames"]:
                    path = Path(name)
                    path.resolve(strict=True).relative_to((work / "target").resolve())
                    artifacts.append({"file": str(path.relative_to(work)), "digest": digest(path),
                                      "bytes": path.stat().st_size, "target": message["target"]["name"]})
        assert compiled == members and artifacts, "Every observed workspace member must compile"
        receipt["artifacts"] = artifacts
        receipt["controls"].append("all-four-actual-workspace-libraries-compiled-on-linux")
        run("test-actual-workspace", [cargo, "test", "--workspace", "--lib", "--locked", "--offline",
                                     "--features", "axum/ws"], cwd=owner)
        receipt["controls"].append("actual-upstream-workspace-library-tests")
        assert before == tracked_inventory(), "Tracked source changed"
        assert not run("source-status-after", ["git", "status", "--porcelain=v1"], cwd=owner)
        assert digest(cli) == receipt["compilerDigest"]
        receipt.update(status="passed-actual-axum-linux-build-scope",
                       sourceInputsUnchanged=True, linuxTargetCompilationEstablished=True,
                       metadataCompilationClaimRemainsFalse=True)
    except BaseException as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"status": receipt["status"], "error": receipt.get("error")}), flush=True)


if __name__ == "__main__":
    main()
