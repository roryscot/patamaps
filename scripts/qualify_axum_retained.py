"""Existing Axum qualification through native retained contracts; not a second build engine."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile


def digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def qualify_retained(cli, source, tracked, config, artifacts, work, evidence, run, inspect_rlib, ar):
    root = work / "retained-workflow"
    root.mkdir()
    owner = root / "owner"
    owner.mkdir()
    report = {"status": "failed", "platform": "x86_64-unknown-linux-gnu",
              "applicationAcceptance": False, "dependencyClosureEstablished": False,
              "osDenialOfAllHostPaths": False, "filesDeleted": 0}
    moves = []
    try:
        names = sorted(n for n in tracked if n in ["Cargo.toml", "Cargo.lock", "README.md", "LICENSE"]
                       or n.split("/")[0] in ["axum", "axum-core", "axum-extra", "axum-macros"])
        assert len(names) == 335, "Pinned source selection changed; review before changing acceptance"
        links = [n for n in names if (source / n).is_symlink()]
        assert len(links) == 5
        for name in names:
            src, dst = source / name, owner / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                src.resolve(strict=True).relative_to(source.resolve())
                dst.symlink_to(os.readlink(src))
            else:
                src.read_text(encoding="utf8")
                shutil.copy2(src, dst)
            assert digest(dst) == tracked[name]
        provider, cargo, rustc = [root / n for n in ["configured-provider", "configured-cargo", "configured-rustc"]]
        shutil.copy2(cli, provider)
        cargo.symlink_to(config["cargo"])
        rustc.symlink_to(config["rustc"])
        assert digest(provider) == digest(cli)
        assert digest(cargo) == config["cargoDigest"] and digest(rustc) == config["rustcDigest"]
        cargo_config = {**config, "cargo": str(cargo), "rustc": str(rustc)}
        identity = "urn:qualification:axum:linux-retained"
        projection = {"schemaVersion": "0.1.0", "documentType": "projection-spec",
                      "id": identity + ":packages", "select": {"kinds": ["cargo-package"]}, "slots": []}
        policy = {"schemaVersion": "0.1.0", "documentType": "policy", "id": identity + ":policy",
                  "graph": {"id": identity, "revision": "1"}, "mappings": [], "constraints": [], "evidence": []}
        workspace = {"schemaVersion": "0.1.0", "documentType": "workspace-config", "id": identity,
                     "namespace": "actual-axum-linux-retained", "revision": "1", "packs": [],
                     "sources": [{"adapter": "process", "id": identity + ":cargo",
                                  "invocation": {"executable": str(provider), "arguments": ["discover-native"],
                                                 "codeInputs": [], "bounds": {"maximumElapsedMs": 60000,
                                                 "maximumStdoutBytes": 16777216, "maximumStderrBytes": 65536}},
                                  "inputs": ["Cargo.toml", "Cargo.lock", "axum/Cargo.toml",
                                             "axum-core/Cargo.toml", "axum-extra/Cargo.toml", "axum-macros/Cargo.toml"],
                                  "config": cargo_config}],
                     "policy": "policy.json", "projections": [{"path": "package-projection.json",
                     "emissions": [{"path": "generated/cargo-packages.json", "language": "json"}]}],
                     "context": {"purpose": "Pinned actual Linux Cargo observations; no inferred business semantics"},
                     "evaluatedAt": "2026-10-20T00:00:00Z"}

        def write(path, value):
            with path.open("x") as target:
                json.dump(value, target, indent=2)
                target.write("\n")

        for name, value in [("workspace.json", workspace), ("policy.json", policy),
                            ("package-projection.json", projection)]:
            write(owner / name, value)
        for name in ["home", "tmp"]:
            (root / name).mkdir()
        inputs = sorted([n for n in names if n not in links]
                        + ["workspace.json", "policy.json", "package-projection.json"])
        assert len(inputs) == 333
        settings = {"path": str(Path(config["cargo"]).parent) + ":/usr/bin:/bin",
                    "cargoHome": config["cargoHome"], "rustc": str(rustc), "offline": "true",
                    "target": "target", "jobs": "2", "debug": "0", "incremental": "0",
                    "testThreads": "1", "home": str(root / "home"), "tmp": str(root / "tmp")}
        refs = dict(PATH="path", CARGO_HOME="cargoHome", RUSTC="rustc", CARGO_NET_OFFLINE="offline",
                    CARGO_TARGET_DIR="target", CARGO_BUILD_JOBS="jobs", CARGO_PROFILE_DEV_DEBUG="debug",
                    CARGO_PROFILE_TEST_DEBUG="debug", CARGO_INCREMENTAL="incremental",
                    RUST_TEST_THREADS="testThreads", HOME="home", TMPDIR="tmp")
        project = {"profile": "patamaps-project-inputs-1", "id": identity + ":inputs",
                   "nonsecretInputs": True, "inputs": inputs,
                   "components": [{"id": name, "kind": "cargo-package", "root": name,
                                   "entrypoints": [name + "/Cargo.toml", name + "/src/lib.rs"]}
                                  for name in ["axum", "axum-core", "axum-extra", "axum-macros"]],
                   "nonsecretConfiguration": settings, "secretReferences": {}}
        project["components"].append({"id": "observation", "kind": "configuration", "root": ".",
                                      "entrypoints": ["workspace.json", "policy.json", "package-projection.json"]})

        def command(executable, arguments):
            return {"profile": "patamaps-project-command-1", "workingDirectory": ".",
                    "environmentReferences": refs, "invocation": {"executable": str(executable),
                    "arguments": arguments, "codeInputs": [], "bounds": {"maximumElapsedMs": 900000,
                    "maximumStdoutBytes": 1048576, "maximumStderrBytes": 65536}}}

        required = {"libaxum.rlib", "libaxum_core.rlib", "libaxum_extra.rlib", "libaxum_macros.so"}
        library_paths = [a["file"] for a in artifacts if Path(a["file"]).name in required]
        assert len(library_paths) == 4 and {Path(p).name for p in library_paths} == required
        assert all(p.startswith("target/") for p in library_paths)
        common = ["--workspace", "--lib", "--locked", "--offline", "--features", "axum/ws",
                  "--target", "x86_64-unknown-linux-gnu"]
        plan = {"profile": "patamaps-project-build-1", "project": project, "workspace": workspace,
                "buildSteps": [command(cargo, ["build", *common])],
                "verificationSteps": [command(cargo, ["test", *common]), command(rustc, ["-vV"])],
                "outputs": [{"path": p, "kind": "file"} for p in library_paths]
                           + [{"path": "generated/cargo-packages.json", "kind": "file"}]}
        write(root / "plan.json", plan)
        write(root / "context-selection.json", {"profile": "patamaps-project-context-selection-1",
              "id": identity + ":context", "nonsecretInputs": True, "paths": names, "symlinks": "internal-closed"})
        capture = json.loads(run("retained-context-capture", [cli, "project-context-capture",
                            root / "context-selection.json", "--root", owner, "--destination", root / "snapshot"]))
        write(root / "binding.json", {"profile": "patamaps-project-build-context-1",
              "snapshot": str(root / "snapshot"), "digest": capture["digest"],
              "overlays": {}, "writablePaths": ["target"]})
        json.loads(run("retained-context-verify", [cli, "project-context-verify", root / "snapshot"]))
        state = root / "state"
        argv = [cli, "project-build", root / "plan.json", "--source", owner,
                "--state", state, "--context", root / "binding.json"]
        selected = json.loads(run("retained-native-build", argv, timeout=1200))
        assert selected["status"] == "selected-project-build" and selected["verification"] == "commands-executed"
        pointer = (state / "selected.json").read_bytes()
        attempt = state / selected["attempt"]
        candidate = attempt / "candidate"
        commands = []
        for name in ["build-000.json", "verify-001.json", "verify-002.json"]:
            data = json.loads((attempt / name).read_text())
            assert data["status"] == "completed-project-command" and data["programSucceeded"] is True
            assert data["exitCode"] == 0 and data["selectedInputsUnchanged"] is True and data["executableUnchanged"] is True
            commands.append({"record": name, "digest": digest(attempt / name),
                             "elapsedMs": data["elapsedMs"], "executableDigest": data["executableDigestAfter"]})
        tests = json.loads((attempt / "verify-001.json").read_text())["stdout"]["text"]
        summaries = re.findall(r"test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored", tests)
        assert len(summaries) == 4 and sum(int(p) for p, _, _ in summaries) == 459, summaries
        assert all(f == "0" and i == "0" for _, f, i in summaries)
        version = json.loads((attempt / "verify-002.json").read_text())["stdout"]["text"]
        assert "host: x86_64-unknown-linux-gnu" in version
        inventory = json.loads((candidate / "generated/cargo-packages.json").read_text())
        assert sorted(e["subject"]["attributes"]["name"] for e in inventory["entries"]) == ["axum", "axum-core", "axum-extra", "axum-macros"]
        output_digests = {o["path"]: digest(candidate / o["path"]) for o in plan["outputs"]}
        archives = {p: inspect_rlib(candidate / p, ar) for p in library_paths if p.endswith(".rlib")}
        header = (candidate / next(p for p in library_paths if p.endswith(".so"))).read_bytes()[:64]
        assert len(header) == 64 and header[:6] == b"\x7fELF\x02\x01" and int.from_bytes(header[18:20], "little") == 62
        bindings = json.loads((attempt / "tool-bindings.json").read_text())
        assert all(str(p) in bindings for p in [provider, cargo, rustc])
        # Move only this qualification's copies/links; real system tools and original upstream stay in place.
        for path in [owner, root / "snapshot", provider, cargo, rustc]:
            unavailable = path.with_name(path.name + ".unavailable")
            assert not unavailable.exists()
            path.rename(unavailable)
            moves.append((path, unavailable))
        assert all(not path.exists() for path, _ in moves)
        replay_env = {**os.environ, "PATH": str(root / "unavailable-tools")}
        replay = json.loads(run("retained-source-tools-unavailable-replay",
                            [cli, "project-build-verify", state], env=replay_env))
        assert replay["status"] == "verified-selected-build-bindings" and replay["toolExecution"] == "not-performed"
        assert replay["sourceRediscovery"] == "not-performed"
        # The negative control must fail for the bound output, not an arbitrary command error.
        sample = candidate / next(p for p in library_paths if p.endswith(".rlib"))
        original = sample.read_bytes()
        try:
            sample.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            assert digest(sample) != output_digests[str(sample.relative_to(candidate))]
            run("retained-corrupt-output-refusal", [cli, "project-build-verify", state], expected=2, env=replay_env)
            assert "PROJECT_BUILD_SELECTED_OUTPUT_CHANGED" in (evidence / "retained-corrupt-output-refusal.stderr.log").read_text()
        finally:
            sample.write_bytes(original)
        assert (state / "selected.json").read_bytes() == pointer

        # Retain only replay inputs and selected outputs, never the unselected compiler cache.
        payload = evidence / "retained-workflow.tar.gz"
        members = {}
        def add(archive, path, name):
            assert name not in members
            if path.is_symlink():
                members[name] = {"kind": "symlink", "target": os.readlink(path)}
            elif path.is_file():
                members[name] = {"kind": "file", "digest": digest(path), "bytes": path.stat().st_size}
            else:
                assert path.is_dir()
                members[name] = {"kind": "directory"}
            assert len(members) <= 8192
            assert sum(x.get("bytes", 0) for x in members.values()) <= 128 * 1024 * 1024
            archive.add(path, arcname=name, recursive=False)

        with tarfile.open(payload, "x:gz", dereference=False) as archive:
            add(archive, cli, "tool/bin/patamaps")
            add(archive, source / "LICENSE", "licenses/axum-LICENSE")
            for directory, dirs, files in os.walk(state, followlinks=False):
                directory = Path(directory)
                dirs.sort()
                add(archive, directory, "state/" + directory.relative_to(state).as_posix())
                # Writable target contains build caches; selected files are added explicitly below.
                if directory == candidate:
                    dirs[:] = [d for d in dirs if d != "target"]
                for name in sorted(files):
                    path = directory / name
                    add(archive, path, "state/" + path.relative_to(state).as_posix())
            for name in sorted(library_paths):
                path = candidate / name
                for parent in reversed(list(path.parents)):
                    if parent == candidate or not parent.is_relative_to(candidate):
                        continue
                    member = "state/" + parent.relative_to(state).as_posix()
                    if member not in members:
                        add(archive, parent, member)
                add(archive, path, "state/" + path.relative_to(state).as_posix())
        restored = root / "restored"
        restored.mkdir()
        with tarfile.open(payload, "r:gz") as archive:
            actual = archive.getmembers()
            assert len(actual) == len(members) and {m.name.rstrip("/.") for m in actual} == {n.rstrip("/.") for n in members}
            assert all(not m.islnk() and (m.isfile() or m.isdir() or m.issym()) for m in actual)
            for member in actual:
                assert not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                entry = members[member.name]
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        assert "sha256:" + hashlib.sha256(stream.read()).hexdigest() == entry["digest"]
                elif member.issym():
                    assert member.linkname == entry["target"]
            archive.extractall(restored, filter="data")
            # data_filter intentionally drops directory modes; restore reviewed nonprivileged recorded bits.
            for member in reversed(actual):
                if not member.issym():
                    assert member.mode & ~0o777 == 0
                    (restored / member.name).chmod(member.mode)
        assert all(not path.exists() for path, _ in moves)
        restored_replay = json.loads(run("retained-minimal-archive-replay",
                                       [restored / "tool/bin/patamaps", "project-build-verify", restored / "state"],
                                       env=replay_env))
        assert restored_replay["status"] == "verified-selected-build-bindings"
        for path, unavailable in reversed(moves):
            unavailable.rename(path)
        moves = []
        attempts_before = sorted(p.name for p in (state / "attempts").iterdir())
        noop = json.loads(run("retained-native-noop", argv))
        assert noop["status"] == "unchanged-project-build" and noop["verification"] == "not-repeated"
        assert noop["cacheHits"] == 0 and (state / "selected.json").read_bytes() == pointer
        assert sorted(p.name for p in (state / "attempts").iterdir()) == attempts_before
        assert all(digest(candidate / name) == value for name, value in output_digests.items())
        report.update(status="passed-actual-axum-linux-retained-workflow", selected=selected,
                      sourcePaths=len(names), selectedTextInputs=len(inputs), preservedSymlinks=links,
                      contextDigest=capture["digest"], nativeCommands=commands,
                      tests={"passed": 459, "failed": 0, "ignored": 0, "perHarness": [int(p) for p, _, _ in summaries]},
                      artifactDigests=output_digests, rustArchiveInspection=archives, sharedLibraryElfMachine=62,
                      sourceSnapshotAndConfiguredToolsUnavailableReplay=True, corruptSelectedOutputRefused=True,
                      originalSelectionPreserved=True, noOpVerificationNotRepeated=True, cacheHits=0,
                      minimalArchive={"file": payload.name, "digest": digest(payload), "bytes": payload.stat().st_size,
                                      "members": members, "maximumBytes": 128 * 1024 * 1024,
                                      "maximumMembers": 8192, "allMembersVerified": True,
                                      "freshRestorationReplayPassed": True, "unselectedBuildCacheIncluded": False},
                      limitations=["External registry cache, linker and toolchain dependencies remain outside the source context.",
                                   "Replay checks bindings, not renewed builds, authorization or application behavior.",
                                   "No HTTP deployment, authentication or performance acceptance."])
        return report
    except BaseException as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        for path, unavailable in reversed(moves):
            unavailable.rename(path)
        (evidence / "retained-workflow.json").write_text(json.dumps(report, indent=2) + "\n")
