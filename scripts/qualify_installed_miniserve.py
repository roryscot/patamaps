"""Qualify fresh source/native installations against the frozen real Rust application."""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tarfile, time, zipfile
from pathlib import Path
from cross_stack_package import install_archive
from project_watch import stop

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "roryscot/patamaps"
PRODUCER = "73c7c882df86696d9990035d40f233cab19a0398"
RUN = 40050181349
ARTIFACT = 12543262113
ZIP_SHA = "6c662e0d29292a8cc6e49a4cceebc5667ac06089d4f8089e96fcf70ee01633a0"
ZIP_BYTES = 83863862
STATE_SHA = "e0e211746d7c503749d71ef5f3196688a1f4bb114b4c2b77197489e2d3038802"
CLI_SHA = "ef5170acf6d70d24ed80811eca741a78bc32924c886abb605d092dd7e4395e45"
POINTER_SHA = "25e642041ddcfa5fb218e839872e30d009c0cc5daf1445dfae783bb031c6699a"
PRODUCTION_OBJECTS = {
    "crates": "d58da35ab0fb1c013d32c1571598fe32e2b89e6e",
    "vendor": "f943ea9ad49eb56e9386693a565f7b34daf7a536",
    "Cargo.toml": "0914724a67cd43dcde6b2b3cb3603835510ad061",
    "Cargo.lock": "10f546d005f0d9fe3ff094f9987f45d98ab7f0fe",
    "rust-toolchain.toml": "b432996f101609389fcd631582395680520eb494",
    "relation-packs": "005b45e20031dff8bf8f8bad133099c92fa8543f",
    "schemas": "b3f1080db5f7d8682350c40d4e2fa8a65b0a5332",
    "adapters": "3c6de1ff02190e4c37706e70b2b10b875c8c9bc8",
    "sdk": "b2fe60bffae223a5aadc37f23eb72c5f53717da2"
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def install_selected_state(archive, destination, *, profile="runtime"):
    """Import a closed, digest-verified state without changing bound directory modes."""
    profiles = {"runtime": ("selected-state", 2000, 64000000),
                "registry": ("registry-state", 10000, 320 * 1024**2)}
    if profile not in profiles:
        raise ValueError("SELECTED_STATE_IMPORT_PROFILE")
    root, maximum_members, maximum_bytes = profiles[profile]
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) < maximum_members and sum(m.size for m in members) < maximum_bytes
        assert len({Path(m.name).parts for m in members}) == len(members)
        for member in members:
            p = Path(member.name)
            assert not p.is_absolute() and ".." not in p.parts and p.parts[0] == root
            assert (member.isfile() or member.isdir()) and not member.mode & 0o7000
        def preserve_modes(member, path):
            # data_filter intentionally discards directory modes. Those modes
            # are bound inputs here, so retain them after its path/type checks.
            filtered = tarfile.data_filter(member, path)
            return filtered.replace(mode=member.mode)
        tar.extractall(destination, members=members, filter=preserve_modes)
    return destination / root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["work", "evidence"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--application-image", action="store_true")
    args = parser.parse_args()
    assert platform.system() == "Linux" and platform.machine() == "x86_64" and os.environ.get("GITHUB_ACTIONS") == "true", "Use focused Linux CI; Intel native work requires its existing guard"
    work, out = args.work.resolve(), args.evidence.resolve()
    work.mkdir(parents=True, exist_ok=False)
    out.mkdir(parents=True, exist_ok=False)
    (out / "logs").mkdir()
    assert not any((p / "Cargo.toml").exists() for p in work.parents), "Consumer must be outside a Cargo workspace"
    baseline = shutil.disk_usage(ROOT).used
    env = {k: v for k, v in os.environ.items() if k in ["PATH", "HOME", "CARGO_HOME", "RUSTUP_HOME"]}
    env.update(PYTHONDONTWRITEBYTECODE="1", CARGO_INCREMENTAL="0", CARGO_BUILD_JOBS="2", CARGO_PROFILE_DEV_DEBUG="0", CARGO_PROFILE_TEST_DEBUG="0", CARGO_TERM_COLOR="never", RUSTUP_TOOLCHAIN="1.99.0")
    record = dict(status="running", sourceRevision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), producerRevision=PRODUCER, producerRun=RUN, artifactId=ARTIFACT, commands=[], filesDeleted=0, productionActivation=False, registryPublication=False, actualBrowser=False, completeDependencyClosure=False, applicationRecompiled=False)

    def save():
        write(out / "receipt.json", record)

    def capacity():
        disk = shutil.disk_usage(ROOT)
        assert disk.free >= 500000000 and disk.used - baseline <= 4000000000, "CI storage boundary reached"

    def run(label, argv, cwd=None, expected=0, timeout=1200, extra=None, binary=None):
        capacity()
        started = time.monotonic()
        stdout_path = binary or out / "logs" / (label + ".stdout")
        stderr_path = out / "logs" / (label + ".stderr")
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            child = subprocess.Popen([sys.executable, str(ROOT / "scripts/project_watch.py"), "__guard", *map(str, argv)], cwd=cwd or work, env={**env, **(extra or {})}, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                while child.poll() is None:
                    capacity()
                    assert time.monotonic() - started < timeout, (label, "timeout")
                    assert stdout.tell() < (max(67108864, ZIP_BYTES + 1) if binary and label == "download-frozen-artifact" else 67108864) and stderr.tell() < 67108864, (label, "log limit")
                    time.sleep(.5)
                code = child.returncode
            finally:
                stop(child)
        capacity()
        record["commands"].append(dict(label=label, exitCode=code, expectedExitCode=expected, elapsedMs=round((time.monotonic() - started) * 1000)))
        save()
        print(json.dumps(record["commands"][-1]), flush=True)
        if code != expected:
            print(stderr_path.read_text()[-5000:], flush=True)
            if not binary:
                print(stdout_path.read_text()[-3000:], flush=True)
            raise AssertionError((label, code, expected))
        return None if binary else stdout_path.read_text()

    try:
        for name, expected in PRODUCTION_OBJECTS.items():
            actual = run("production-" + name.replace("/", "-").replace(".", "-"), ["git", "rev-parse", "HEAD:" + name], cwd=ROOT).strip()
            assert actual == expected, ("Production source differs from frozen compiler", name, actual)
        record["productionObjects"] = PRODUCTION_OBJECTS
        # Only these GitHub API calls receive the scoped Actions credential.
        token = os.environ["GH_TOKEN"]
        metadata = json.loads(run("artifact-metadata", ["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{ARTIFACT}"], extra={"GH_TOKEN": token}))
        producer_run = json.loads(run("producer-run", ["gh", "api", f"repos/{REPOSITORY}/actions/runs/{RUN}"], extra={"GH_TOKEN": token}))
        assert producer_run["conclusion"] == "success" and producer_run["head_sha"] == PRODUCER
        assert metadata["workflow_run"]["id"] == RUN and not metadata["expired"] and metadata["size_in_bytes"] == ZIP_BYTES
        assert metadata.get("digest") == "sha256:" + ZIP_SHA
        archive = work / "frozen-artifact.zip"
        run("download-frozen-artifact", ["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{ARTIFACT}/zip"], extra={"GH_TOKEN": token}, binary=archive, timeout=180)
        assert sha(archive) == ZIP_SHA
        producer = work / "producer"
        producer.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            assert len(zipped.namelist()) == len(set(zipped.namelist()))
            for name, destination, limit in [("receipt.json", producer / "receipt.json", 2000000), ("artifacts/MINISERVE-LICENSE", producer / "MINISERVE-LICENSE", 100000), ("artifacts/patamaps", producer / "patamaps", 40000000), ("artifacts/selected-state.tar.gz", producer / "selected-state.tar.gz", 10000000)]:
                assert zipped.getinfo(name).file_size <= limit
                destination.write_bytes(zipped.read(name))
        frozen = json.loads((producer / "receipt.json").read_bytes())
        assert frozen["sourceRevision"] == PRODUCER and frozen["restoredSelectedRuntimePassed"]
        registry_state = None
        registry_producer = frozen.get("cargoRegistryContext")
        if registry_producer is not None:
            assert registry_producer["status"] == "passed-native-registry-context-execution"
            with zipfile.ZipFile(archive) as zipped:
                entry = zipped.getinfo("artifacts/registry-selected-state.tar.gz")
                assert entry.file_size <= 320 * 1024**2
                registry_archive = producer / "registry-selected-state.tar.gz"
                registry_archive.write_bytes(zipped.read(entry))
            assert "sha256:" + sha(registry_archive) == registry_producer["retainedStateArchive"]["digest"]
            assert registry_archive.stat().st_size == registry_producer["retainedStateArchive"]["bytes"]
        assert sha(producer / "patamaps") == CLI_SHA and sha(producer / "selected-state.tar.gz") == STATE_SHA
        (producer / "patamaps").chmod(0o755)
        engine = json.loads(run("frozen-engine", [producer / "patamaps", "engine"]))
        assert engine == frozen["relocatedCompiler"]["engine"]
        consumer = work / "consumer"
        consumer.mkdir()
        state = install_selected_state(producer / "selected-state.tar.gz", consumer / "state-installation")
        if registry_producer is not None:
            registry_state = install_selected_state(registry_archive, consumer / "registry-state-installation", profile="registry")
            assert "sha256:" + sha(registry_state / "selected.json") == registry_producer["selectionDigest"]
        pointer = state / "selected.json"
        assert sha(pointer) == POINTER_SHA
        selection = json.loads(pointer.read_bytes())
        candidate = state / selection["attempt"] / "candidate"
        bound_before = {p.relative_to(candidate).as_posix(): sha(p) for p in candidate.rglob("*") if p.is_file()}
        package = out / "package"
        run("package-exact-pair", [sys.executable, "-B", ROOT / "scripts/package.py", "--binary", producer / "patamaps", "--build-profile", "release", "--output", package], cwd=ROOT, timeout=300)
        distribution = json.loads((package / "distribution.json").read_bytes())
        assert distribution["engines"] == engine and distribution["binaryDigest"] == "sha256:" + CLI_SHA
        assert distribution["target"] == "x86_64-unknown-linux-gnu"
        for name in ["sourceArchive", "nativeArchive"]:
            assert "sha256:" + sha(package / distribution[name]["path"]) == distribution[name]["digest"]
        source = install_archive(package / distribution["sourceArchive"]["path"], consumer / "source-installation", work)
        native = install_archive(package / distribution["nativeArchive"]["path"], consumer / "native-installation", work)
        source_inventory = json.loads((source / "source-inventory.json").read_bytes())

        def source_unchanged():
            names = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
            return names == {i["path"] for i in source_inventory} | {"source-inventory.json"} and all((source / i["path"]).stat().st_size == i["bytes"] and "sha256:" + sha(source / i["path"]) == i["digest"] for i in source_inventory) and "sha256:" + sha(source / "source-inventory.json") == distribution["sourceInventoryDigest"]

        assert source_unchanged()
        native_cli = native / "bin/patamaps"
        assert sha(native_cli) == CLI_SHA and os.access(native_cli, os.X_OK)
        env["CARGO_TARGET_DIR"] = str(work / "source-target")
        run("source-locked-fetch", ["cargo", "+1.99.0", "fetch", "--locked", "--target", "x86_64-unknown-linux-gnu"], cwd=source, timeout=300)
        source_prefix = consumer / "cargo-installation"
        assert not source_prefix.exists()
        run("fresh-source-cargo-install", ["cargo", "+1.99.0", "install", "--path", source / "crates/patamaps-cli", "--locked", "--offline", "--debug", "--target", "x86_64-unknown-linux-gnu", "--root", source_prefix], cwd=source, timeout=1200)
        source_cli = source_prefix / "bin/patamaps"
        assert source_unchanged()
        producer.rename(work / "producer.retained-offline")
        assert not producer.exists() and not (ROOT / "target/release/patamaps").exists()
        record["installations"] = {}
        for label, compiler in [("native", native_cli), ("source", source_cli)]:
            command = work / (label + ".command.json")
            runtime = out / ("runtime-" + label)
            write(command, dict(profile="patamaps-project-command-1", workingDirectory=".", environmentReferences={}, invocation=dict(executable="/bin/bash", arguments=["probe.sh", "positive", str(runtime)], codeInputs=["probe.sh"], bounds=dict(maximumElapsedMs=60000, maximumStdoutBytes=65536, maximumStderrBytes=65536))))
            evidence = out / ("consumer-" + label)
            run("installed-" + label, [sys.executable, "-B", source / "scripts/installed_selected.py", "--compiler", compiler, "--state", state, "--command", command, "--output", evidence], extra={"GITHUB_ACTIONS": os.environ["GITHUB_ACTIONS"]}, timeout=240)
            result = json.loads((evidence / "receipt.json").read_bytes())
            assert result["engine"] == engine and result["sourceInventoryUnchanged"]
            controls = (runtime / "passed-controls.txt").read_text().splitlines()
            assert controls == frozen["runtimeControls"] and len(controls) == 8
            record["installations"][label] = dict(compilerDigest="sha256:" + sha(compiler), engine=result["engine"], sourceFiles=result["sourceFiles"], runtimeControls=controls, postExecutionSelectionVerified=result["execution"]["postExecutionSelectionVerified"])
        if registry_state is not None:
            registry_pointer = registry_state / "selected.json"
            registry_selection = json.loads(registry_pointer.read_bytes())
            registry_candidate = registry_state / registry_selection["attempt"] / "candidate"
            registry_before = {p.relative_to(registry_candidate).as_posix(): sha(p) for p in registry_candidate.rglob("*") if p.is_file()}
            registry_runtime = registry_candidate / "bundle/miniserve"
            assert sha(registry_runtime) == frozen["applicationBinary"]["sha256"]
            registry_command = work / "registry-version.command.json"
            write(registry_command, dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences={},
                invocation=dict(executable=str(registry_runtime),arguments=["--version"],codeInputs=[],
                    bounds=dict(maximumElapsedMs=10000,maximumStdoutBytes=65536,maximumStderrBytes=65536))))
            installed_registry = {}
            for label, compiler in [("native",native_cli),("source",source_cli)]:
                verified = json.loads(run(label+"-registry-state",[compiler,"project-build-verify",registry_state]))
                assert verified["status"] == "verified-selected-build-bindings"
                executed = json.loads(run(label+"-registry-runtime",[compiler,"project-exec-selected",registry_state,registry_command]))
                assert executed["status"] == "completed-selected-project-command" and executed["postExecutionSelectionVerified"] and executed["selectionPointerUnchanged"]
                assert "miniserve 0.35.0" in executed["command"]["stdout"]["text"]
                installed_registry[label] = dict(bindingsVerified=True,runtimeVersionPassed=True,selectionUnchanged=executed["selectionPointerUnchanged"])
            member = next(p for p in sorted(registry_before) if p.startswith(".cargo-home/") and p.endswith(".crate"))
            original = registry_candidate / member
            backup = work / "installed-registry-member.retained"
            original.rename(backup);original.write_bytes(b"controlled changed registry member")
            marker_command = work / "registry-marker.command.json"
            write(marker_command,dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences={},
                invocation=dict(executable="/bin/sh",arguments=["-c","printf invoked > bundle/forbidden.marker"],codeInputs=[],
                    bounds=dict(maximumElapsedMs=10000,maximumStdoutBytes=65536,maximumStderrBytes=65536))))
            refused = run("installed-registry-before-effects",[native_cli,"project-exec-selected",registry_state,marker_command],expected=2)
            assert "PROJECT_CONTEXT" in refused+(out/"logs/installed-registry-before-effects.stderr").read_text()
            assert not (registry_candidate/"bundle/forbidden.marker").exists()
            original.rename(work/"installed-registry-member.changed-retained");backup.rename(original)
            restored_registry = json.loads(run("installed-registry-restored",[source_cli,"project-build-verify",registry_state]))
            assert restored_registry["status"] == "verified-selected-build-bindings"
            assert "sha256:"+sha(registry_pointer) == registry_producer["selectionDigest"]
            assert {p.relative_to(registry_candidate).as_posix():sha(p) for p in registry_candidate.rglob("*") if p.is_file()} == registry_before
            record["registryReplay"] = dict(status="passed-source-native-installed-registry-replay",installations=installed_registry,
                registryMemberTamperRefusedBeforeEffects=True,restoredBindingsVerified=True,selectedBytesUnchanged=True,
                archiveDigest=registry_producer["retainedStateArchive"]["digest"],registryContextDigest=registry_producer["snapshotDigest"],
                completeDependencyClosure=False,ownerTestFixturesClosed=False,toolchainClosed=False)
        artifact = candidate / "bundle/public/status.txt"
        backup = work / "status.original.retained"
        artifact.rename(backup)
        artifact.write_text("changed after selection\n")
        refused_command = work / "refused.command.json"
        write(refused_command, dict(profile="patamaps-project-command-1", workingDirectory=".", environmentReferences={}, invocation=dict(executable="/bin/sh", arguments=["-c", "printf invoked > forbidden.marker"], codeInputs=[], bounds=dict(maximumElapsedMs=10000, maximumStdoutBytes=65536, maximumStderrBytes=65536))))
        refusal = run("late-artifact-before-effects", [native_cli, "project-exec-selected", state, refused_command], expected=2)
        refusal_logs = refusal + (out / "logs/late-artifact-before-effects.stderr").read_text()
        assert "PROJECT_BUILD_SELECTED_OUTPUT_CHANGED" in refusal_logs and not (candidate / "forbidden.marker").exists() and sha(pointer) == POINTER_SHA
        artifact.rename(work / "status.changed.retained")
        backup.rename(artifact)
        restored = json.loads(run("restored-selection", [source_cli, "project-build-verify", state]))
        assert restored["status"] == "verified-selected-build-bindings"
        if args.application_image:
            from deployment_miniserve_image import verify
            record["applicationImage"] = verify(source, work, out, candidate, native_cli, work / "producer.retained-offline/MINISERVE-LICENSE", run)
            record["actualBrowser"] = True
        for compiler in [native_cli, source_cli]:
            retained = compiler.with_name("patamaps.unavailable-after-verification")
            compiler.rename(retained)
            assert not compiler.exists()
        runtime = out / "runtime-compilers-unavailable"
        run("runtime-without-test-compilers", ["/bin/bash", "probe.sh", "positive", runtime], cwd=candidate, timeout=90)
        assert (runtime / "passed-controls.txt").read_text().splitlines() == frozen["runtimeControls"]
        assert source_unchanged() and sha(pointer) == POINTER_SHA
        assert {p.relative_to(candidate).as_posix(): sha(p) for p in candidate.rglob("*") if p.is_file()} == bound_before
        record.update(status="passed-installed-external-rust-workflow", distribution=distribution, frozenArtifactDigest="sha256:" + ZIP_SHA, selectedStateDigest="sha256:" + STATE_SHA, sourceFiles=len(source_inventory), installedSourceInventoryUnchanged=True, selectedInputsAndPointerUnchanged=True, lateArtifactRefusedBeforeEffects=True, producerAndTestCompilersUnavailableRuntimePassed=True, nativePackageInstallerExercised=True, freshSourceCargoInstall=True, actualHttp=True, applicationRecompiled=False)
    except BaseException as error:
        record.update(status="failed", error=str(error))
        save()
        raise
    save()
    print(json.dumps(dict(status=record["status"], sourceFiles=record["sourceFiles"], actualHttp=True)))


if __name__ == "__main__":
    main()
