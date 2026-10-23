"""Qualify fresh source/native installations against the frozen real Rust application."""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tarfile, time, zipfile
from pathlib import Path
from cross_stack_package import install_archive
from project_watch import stop

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "roryscot/patamaps"
PRODUCER = "36e6525fcc3f7fdb513efa8eb1fff329ffe67034"
RUN = 39884102308
ARTIFACT = 12472158570
ZIP_SHA = "8fe5985620e6f584024499d5936ce2528d256a6145a35c94dd2f0aa866755d39"
STATE_SHA = "ab1b6163d4c8cb8448c20870398866ab97c0087f216f6b6307440dde097505b3"
CLI_SHA = "5e0b1d10bcb0f5f82090df17a0fba8d838c8f28016a949476289de6f3f7a40b6"
POINTER_SHA = "843b67c6e27eb66938318aaee95a7993f43db0b3268bf020ef480e73c89171ed"
PRODUCTION_OBJECTS = {
    "crates": "44a9f21b445219a72bd44d7212b66dccb124d435",
    "vendor": "f943ea9ad49eb56e9386693a565f7b34daf7a536",
    "Cargo.toml": "0914724a67cd43dcde6b2b3cb3603835510ad061",
    "Cargo.lock": "10f546d005f0d9fe3ff094f9987f45d98ab7f0fe",
    "rust-toolchain.toml": "b432996f101609389fcd631582395680520eb494",
    "relation-packs": "005b45e20031dff8bf8f8bad133099c92fa8543f",
    "schemas": "b3f1080db5f7d8682350c40d4e2fa8a65b0a5332",
    "adapters": "3c6de1ff02190e4c37706e70b2b10b875c8c9bc8",
    "sdk": "b2fe60bffae223a5aadc37f23eb72c5f53717da2",
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def install_selected_state(archive, destination):
    """Import a closed, digest-verified state without changing bound directory modes."""
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) < 2000 and sum(m.size for m in members) < 64000000
        assert len({Path(m.name).parts for m in members}) == len(members)
        for member in members:
            p = Path(member.name)
            assert not p.is_absolute() and ".." not in p.parts and p.parts[0] == "selected-state"
            assert (member.isfile() or member.isdir()) and not member.mode & 0o7000
        def preserve_modes(member, path):
            # data_filter intentionally discards directory modes. Those modes
            # are bound inputs here, so retain them after its path/type checks.
            filtered = tarfile.data_filter(member, path)
            return filtered.replace(mode=member.mode)
        tar.extractall(destination, members=members, filter=preserve_modes)
    return destination / "selected-state"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["work", "evidence"]:
        parser.add_argument("--" + name, type=Path, required=True)
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
                    assert stdout.tell() < 67108864 and stderr.tell() < 67108864, (label, "log limit")
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
        assert metadata["workflow_run"]["id"] == RUN and not metadata["expired"] and metadata["size_in_bytes"] == 20152061
        assert metadata.get("digest") == "sha256:" + ZIP_SHA
        archive = work / "frozen-artifact.zip"
        run("download-frozen-artifact", ["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{ARTIFACT}/zip"], extra={"GH_TOKEN": token}, binary=archive, timeout=180)
        assert sha(archive) == ZIP_SHA
        producer = work / "producer"
        producer.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            assert len(zipped.namelist()) == len(set(zipped.namelist()))
            for name, destination, limit in [("receipt.json", producer / "receipt.json", 2000000), ("artifacts/patamaps", producer / "patamaps", 40000000), ("artifacts/selected-state.tar.gz", producer / "selected-state.tar.gz", 10000000)]:
                assert zipped.getinfo(name).file_size <= limit
                destination.write_bytes(zipped.read(name))
        frozen = json.loads((producer / "receipt.json").read_bytes())
        assert frozen["sourceRevision"] == PRODUCER and frozen["restoredSelectedRuntimePassed"]
        assert sha(producer / "patamaps") == CLI_SHA and sha(producer / "selected-state.tar.gz") == STATE_SHA
        (producer / "patamaps").chmod(0o755)
        engine = json.loads(run("frozen-engine", [producer / "patamaps", "engine"]))
        assert engine == frozen["relocatedCompiler"]["engine"]
        consumer = work / "consumer"
        consumer.mkdir()
        state = install_selected_state(producer / "selected-state.tar.gz", consumer / "state-installation")
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
