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
import tarfile
import time

UPSTREAM = "https://github.com/tokio-rs/axum.git"
REVISION = "fc78d5bcdb276bd6fb53cf2db55e91757eabb469"
MANIFESTS = ["Cargo.toml", "Cargo.lock", "axum/Cargo.toml",
             "axum-core/Cargo.toml", "axum-extra/Cargo.toml", "axum-macros/Cargo.toml"]
PACKAGES = ["axum", "axum-core", "axum-extra", "axum-macros"]


def digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def elf_x86_64_header(header):
    """Check the bounded ELF identification and e_machine fields, not whole-file validity."""
    return (len(header) >= 20 and header[:6] == b"\x7fELF\x02\x01"
            and int.from_bytes(header[18:20], "little") == 62)


def inspect_rlib(path, ar):
    """Inspect every regular Rust archive object header; never extract or execute it."""
    path = Path(path)
    assert path.stat().st_size <= 256 * 1024 * 1024, "Archive inspection byte bound"
    with path.open("rb") as source:
        assert source.read(8) == b"!<arch>\n", "Thin or unsupported archive refused"
    listing = subprocess.check_output([str(ar), "t", str(path)], timeout=30)
    assert len(listing) <= 1024 * 1024, "Archive listing byte bound"
    names = listing.decode("ascii").splitlines()
    assert 1 <= len(names) <= 4096 and len(names) == len(set(names)), "Ambiguous archive membership"
    assert names.count("lib.rmeta") == 1, "Expected exactly one Rust metadata member"
    assert names.count("lib.rmeta-link") == 1, "Expected exactly one Rust late-metadata member"
    objects = []
    metadata_headers = []
    for name in names:
        assert name and len(name) <= 1024 and name[0].isalnum()
        assert all(c.isalnum() or c in "._-" for c in name), "Unsupported archive member name"
        assert name in ["lib.rmeta", "lib.rmeta-link"] or name.endswith(".o"), "Unexpected non-object archive member"
        data = subprocess.check_output([str(ar), "p", str(path), name], timeout=30)
        assert len(data) <= 64 * 1024 * 1024, "Archive member byte bound"
        header = data[:64]
        assert elf_x86_64_header(header), "Wrong archive object architecture: " + name
        assert int.from_bytes(header[16:18], "little") == 1, "Archive member is not relocatable"
        item = {"member": name, "bytes": len(data),
                "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
        (metadata_headers if name in ["lib.rmeta", "lib.rmeta-link"] else objects).append(item)
    assert objects, "No compiled object members"
    return {"objects": objects, "metadataMembers": 2, "metadataHeaders": metadata_headers, "format": "ELF64",
            "byteOrder": "little", "machine": 62, "elfType": 1,
            "scope": "All code and both pinned-rustc metadata member headers/digests, not full ELF/link/dependency validity"}


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
        os.environ["CARGO_HOME"] = str(cargo_home)
        os.environ["CARGO_TARGET_DIR"] = str(work / "target")
        receipt["buildPlatform"] = "x86_64-unknown-linux-gnu"
        receipt["buildEnvironment"] = {
            name: os.environ.get(name) for name in [
                "RUSTC", "CARGO_TARGET_DIR", "CARGO_HOME", "CARGO_INCREMENTAL",
                "CARGO_BUILD_JOBS", "CARGO_PROFILE_DEV_DEBUG", "CARGO_PROFILE_TEST_DEBUG",
                "RUST_TEST_THREADS"]
        }
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
                        "--features", "axum/ws", "--target", "x86_64-unknown-linux-gnu",
                        "--message-format=json"], cwd=owner)
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
        shared = [item for item in artifacts if item["file"].endswith(".so")]
        assert len(shared) == 1, "Expected the actual workspace proc-macro shared library"
        shared_path = work / shared[0]["file"]
        with shared_path.open("rb") as source:
            header = source.read(64)
        assert elf_x86_64_header(header), "Wrong or unsupported actual shared-library architecture"
        wrong_arch = bytearray(header)
        wrong_arch[18:20] = (183).to_bytes(2, "little")
        assert not elf_x86_64_header(wrong_arch), "Forged AArch64 header accepted"
        assert not elf_x86_64_header(header[:19]), "Truncated ELF header accepted"
        receipt["sharedLibraryArchitecture"] = {
            "file": shared[0]["file"], "format": "ELF64", "byteOrder": "little",
            "machine": 62, "wrongArchitectureHeaderRefused": True,
            "truncatedHeaderRefused": True,
            "scope": "Actual proc-macro shared-library header; Rust archive member inspection recorded separately"
        }
        receipt["controls"].extend(["actual-shared-library-ELF64-x86_64-header",
                                    "tampered-architecture-header-refusal", "truncated-ELF-header-refusal"])
        ar = Path(shutil.which("ar")).resolve(strict=True)
        ar_digest = digest(ar)
        ar_version = run("archive-inspector-version", [ar, "--version"]).decode()
        assert "GNU ar" in ar_version, "Qualification expects the recorded GNU archive inspector"
        archive_observations = []
        for item in artifacts:
            if item["file"].endswith(".rlib"):
                archive_path = work / item["file"]
                assert digest(archive_path) == item["digest"]
                inspected = inspect_rlib(archive_path, ar)
                assert digest(archive_path) == item["digest"], "Archive changed during inspection"
                archive_observations.append({"file": item["file"], **inspected})
        assert archive_observations, "No actual Rust archives inspected"
        # Exercise the full archive inspector using corrupt copies of actual member bytes.
        sample = work / archive_observations[0]["file"]
        object_name = archive_observations[0]["objects"][0]["member"]
        actual_object = subprocess.check_output([str(ar), "p", str(sample), object_name], timeout=30)
        actual_metadata = subprocess.check_output([str(ar), "p", str(sample), "lib.rmeta"], timeout=30)
        actual_late_metadata = subprocess.check_output([str(ar), "p", str(sample), "lib.rmeta-link"], timeout=30)
        negative_controls = []
        variants = [("wrong-architecture", "Wrong archive object architecture"),
                    ("truncated-header", "Wrong archive object architecture"),
                    ("non-relocatable", "Archive member is not relocatable"),
                    ("duplicate-member", "Ambiguous archive membership"),
                    ("missing-metadata", "Expected exactly one Rust metadata member"),
                    ("late-metadata-wrong-architecture", "Wrong archive object architecture"),
                    ("unknown-member", "Unexpected non-object archive member")]
        for label, expected_error in variants:
            folder = evidence / ("archive-refusal-" + label)
            folder.mkdir()
            data = bytearray(actual_object)
            if label == "wrong-architecture":
                data[18:20] = (183).to_bytes(2, "little")
            elif label == "truncated-header":
                data = data[:19]
            elif label == "non-relocatable":
                data[16:18] = (3).to_bytes(2, "little")
            object_file = folder / "control.o"
            object_file.write_bytes(data)
            metadata_file = folder / "lib.rmeta"
            metadata_file.write_bytes(actual_metadata)
            late_metadata = folder / "lib.rmeta-link"
            late_data = bytearray(actual_late_metadata)
            if label == "late-metadata-wrong-architecture":
                late_data[18:20] = (183).to_bytes(2, "little")
            late_metadata.write_bytes(late_data)
            archive = folder / "control.rlib"
            files = [object_file] if label == "missing-metadata" else [metadata_file, late_metadata, object_file]
            if label == "unknown-member":
                unknown = folder / "unexpected.txt"
                unknown.write_bytes(b"not an allowed archive member")
                files.append(unknown)
            subprocess.run([str(ar), "qc", str(archive), *map(str, files)], check=True, timeout=30)
            if label == "duplicate-member":
                subprocess.run([str(ar), "q", str(archive), str(object_file)], check=True, timeout=30)
            try:
                inspect_rlib(archive, ar)
            except AssertionError as error:
                assert expected_error in str(error), (label, str(error))
            else:
                raise AssertionError("Corrupt archive accepted: " + label)
            negative_controls.append({"case": label, "archiveDigest": digest(archive),
                                      "expectedRefusal": expected_error})
        thin = evidence / "refused-thin.rlib"
        thin.write_bytes(b"!<thin>\n")
        try:
            inspect_rlib(thin, ar)
        except AssertionError as error:
            assert "Thin or unsupported archive refused" in str(error)
        else:
            raise AssertionError("Thin archive accepted")
        negative_controls.append({"case": "thin-archive", "archiveDigest": digest(thin)})
        assert all(digest(work / item["file"]) == item["digest"] for item in artifacts)
        assert digest(ar) == ar_digest
        receipt["rustArchiveArchitecture"] = {
            "inspectorDigest": ar_digest, "inspectorVersion": ar_version,
            "archives": archive_observations, "archiveCount": len(archive_observations),
            "negativeControls": negative_controls,
            "objectCount": sum(len(x["objects"]) for x in archive_observations),
            "fullElfValidation": False, "dependencyClosureEstablished": False}
        receipt["controls"].extend(["all-actual-rlib-object-ELF64-x86_64-relocatable-headers",
                                    "actual-member-corrupt-archive-refusals-eight-cases"])
        receipt["controls"].append("all-four-actual-workspace-libraries-compiled-on-linux")
        run("test-actual-workspace", [cargo, "test", "--workspace", "--lib", "--locked", "--offline",
                                     "--features", "axum/ws", "--target", "x86_64-unknown-linux-gnu"], cwd=owner)
        receipt["controls"].append("actual-upstream-workspace-library-tests")
        assert before == tracked_inventory(), "Tracked source changed"
        assert not run("source-status-after", ["git", "status", "--porcelain=v1"], cwd=owner)
        assert digest(cli) == receipt["compilerDigest"]
        engine_bytes = run("retained-tool-engine", [cli, "engine"])
        engine = json.loads(engine_bytes)
        (evidence / "engine.json").write_bytes(engine_bytes)
        payload = evidence / "qualified-artifacts.tar.gz"
        with tarfile.open(payload, "w:gz") as archive:
            archive.add(cli, arcname="tool/bin/patamaps", recursive=False)
            archive.add(evidence / "engine.json", arcname="tool/engine.json", recursive=False)
            archive.add(owner / "LICENSE", arcname="licenses/axum-LICENSE", recursive=False)
            for item in artifacts:
                archive.add(work / item["file"], arcname="libraries/" + item["file"], recursive=False)
        expected_members = {
            "tool/bin/patamaps": receipt["compilerDigest"],
            "tool/engine.json": digest(evidence / "engine.json"),
            "licenses/axum-LICENSE": digest(owner / "LICENSE"),
            **{"libraries/" + item["file"]: item["digest"] for item in artifacts}
        }
        with tarfile.open(payload, "r:gz") as archive:
            assert sorted(m.name for m in archive.getmembers()) == sorted(expected_members)
            for member, expected in expected_members.items():
                entry = archive.getmember(member)
                assert entry.isfile()
                with archive.extractfile(entry) as source:
                    assert "sha256:" + hashlib.sha256(source.read()).hexdigest() == expected
        assert digest(cli) == receipt["compilerDigest"]
        receipt["retainedPayload"] = {
            "file": payload.name, "digest": digest(payload), "bytes": payload.stat().st_size,
            "compilerMember": "tool/bin/patamaps", "compilerDigest": digest(cli),
            "engine": engine, "libraryFiles": len(artifacts), "allPayloadMembersVerified": True,
            "scope": "Exact qualification tools/libraries; no registry publication or deployment activation"
        }
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
