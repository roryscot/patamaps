"""Independently verify exact packaged helper bytes and six installed controls."""
from pathlib import Path, PurePosixPath
import argparse, datetime, hashlib, json, re, stat, subprocess, tarfile

def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def require(value, message):
    if not value:
        raise RuntimeError(message)

def absent(pid):
    p = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "pid="], capture_output=True, text=True, timeout=5)
    return p.returncode == 1 and not p.stdout.strip()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["work", "repo", "node", "buildctl", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    w, root = args.work.resolve(), args.repo.resolve()
    require(not args.output.exists(), "review output already exists")
    cfg, result = read(w / "frozen.json"), read(w / "receipt.json")
    require(cfg["revision"] == result["sourceRevision"] == "451c0643113174c287a05bda039edfdb3d52681f", "producer revision")
    require(cfg["driverDigest"] == sha(w / "run.py") == "sha256:1051ed089666e7097600d6d93678c7cda2005c3c865265716b382c2c79b66c73", "driver digest")
    require(result["status"] == "passed-packaged-installed-inspector-controls", "qualification incomplete")
    require(read(w / "supervisor-exit.json")["exitCode"] == 0, "guard did not finish successfully")
    require(result["freshSourceCompilerBuilt"] is False and result["ownerBuildRun"] is False, "unexpected compile/build claim")
    require(result["filesDeleted"] == 0 and result["policyChanged"] is False, "deletion/policy mismatch")
    dist = read(w / "package/distribution.json")
    require(dist == result["distribution"], "distribution record mismatch")
    require(dist["buildProfile"] == "development" and dist["target"] == "x86_64-apple-darwin", "package profile")
    require(dist["binaryDigest"] == cfg["binaryDigest"] == "sha256:cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355", "binary digest")
    require(dist["engines"] == result["engine"], "engine mismatch")
    source, native = Path(result["installedSource"]), Path(result["installedNative"])
    require(source.is_relative_to(w) and native.is_relative_to(w), "installation escaped phase")
    require(not (source / ".git").exists(), "installed Git metadata")
    require(sha(source / "source-inventory.json") == dist["sourceInventoryDigest"], "source inventory digest")
    inventory = read(source / "source-inventory.json")
    expected = {item["path"]: item for item in inventory}
    require(len(expected) == len(inventory) == result["sourceMembersMatchedGit"], "source member count")
    require(set(expected) | {"source-inventory.json"} == {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}, "extracted member set")
    require(not any(p.is_symlink() for p in source.rglob("*")), "source symlink")
    require(sum(v["bytes"] for v in inventory) + (source / "source-inventory.json").stat().st_size <= 134217728, "source byte budget")
    require(dist["sourceEvidence"]["bytes"] <= 33554432 and dist["sourceEvidence"]["files"] <= 512, "linked evidence budget")
    source_prefix = source.name
    archive_info = {}
    for kind in ["sourceArchive", "nativeArchive"]:
        archive = w / "package" / dist[kind]["path"]
        require(archive.parent == w / "package" and sha(archive) == dist[kind]["digest"], "archive path/digest")
        with tarfile.open(archive, "r:gz") as tf:
            members = tf.getmembers()
            names = [m.name for m in members]
            require(len(set(names)) == len(names) and all(m.isfile() for m in members), "archive duplicate/special member")
            for member in members:
                name = PurePosixPath(member.name)
                require(not name.is_absolute() and ".." not in name.parts and name.parts[0] == source_prefix, "archive member path")
                relative = PurePosixPath(*name.parts[1:]).as_posix()
                installed = (source if kind == "sourceArchive" else native) / relative
                data = tf.extractfile(member).read()
                require(installed.is_file() and not installed.is_symlink() and installed.read_bytes() == data, "archive/extracted bytes")
                require(stat.S_IMODE(installed.stat().st_mode) == member.mode, "archive/extracted mode")
            if kind == "sourceArchive":
                require({PurePosixPath(n).relative_to(source_prefix).as_posix() for n in names} == set(expected) | {"source-inventory.json"}, "source archive membership")
            else:
                before_archives = {k: v for k, v in dist.items() if k not in ["sourceArchive", "nativeArchive"]}
                require(read(native / "distribution.json") == before_archives, "native embedded metadata")
        archive_info[kind] = {"digest": sha(archive), "bytes": archive.stat().st_size}
    tree = subprocess.check_output(["git", "ls-tree", "-r", cfg["revision"]], cwd=root).splitlines()
    blobs = {}
    for line in tree:
        metadata, name = line.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if kind == b"blob":
            blobs[name.decode()] = oid
    require(all(name in blobs for name in expected), "source member untracked at producer")
    wanted = [blobs[item["path"]] for item in inventory]
    batch = subprocess.run(["git", "cat-file", "--batch"], cwd=root, input=b"\n".join(wanted) + b"\n", capture_output=True, check=True).stdout
    offset = 0
    for item, oid in zip(inventory, wanted):
        end = batch.index(b"\n", offset)
        actual, kind, size = batch[offset:end].split()
        size = int(size); offset = end + 1
        data = batch[offset:offset + size]; offset += size
        require(batch[offset:offset + 1] == b"\n", "Git batch separator")
        offset += 1
        require(actual == oid and kind == b"blob" and len(data) == item["bytes"], "Git blob identity")
        require("sha256:" + hashlib.sha256(data).hexdigest() == item["digest"] == sha(source / item["path"]), "Git/archive/extracted hash")
    require(offset == len(batch), "Git batch trailing data")
    old = read(root / ".tools/installed-original-owner-next-20261027/package-source/receipt.json")
    old_source = Path(old["installedSource"])
    require(sha(old_source / "source-inventory.json") == cfg["previousSourceInventoryDigest"], "previous accepted inventory")
    require(sha(Path(old["nativeCli"])) == cfg["binaryDigest"], "previous accepted CLI")
    def is_code(name):
        return name.startswith(("crates/", "vendor/")) or name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"]
    old_code = {v["path"]: v for v in read(old_source / "source-inventory.json") if is_code(v["path"])}
    new_code = {v["path"]: v for v in inventory if is_code(v["path"])}
    require(old_code == new_code and len(new_code) == result["identicalPreviouslyCompiledRustInputFiles"], "reused compiler input mismatch")
    for name, item in old_code.items():
        require(sha(old_source / name) == item["digest"], "previously compiled input changed")
    helper = source / "scripts/selected_next_http_probe.mjs"
    qualifier = source / "scripts/qualify_selected_next_ready_inspector.py"
    require(sha(helper) == cfg["producerInputs"]["scripts/selected_next_http_probe.mjs"] == "sha256:e0152203e3a9ebaa9499c92fdb633a01a50d57f6910c7d5643d1dbd3dced7bf1", "installed probe mismatch")
    require(sha(qualifier) == cfg["producerInputs"]["scripts/qualify_selected_next_ready_inspector.py"] == "sha256:077895476c8c6a8cb33bcee9430351489e187ce9018a0825f8823cfa09ae1bd1", "installed qualifier mismatch")
    require(sha(native / "bin/patamaps") == cfg["binaryDigest"], "installed binary changed")
    roles = {c["role"]: c["measurement"] for c in result["commands"]}
    require(set(roles) == {"producing-engine", "exact-package", "installed-native-engine", "installed-ready-controls"}, "command roles")
    for role, measurement in roles.items():
        require(measurement["exitCode"] == 0 and measurement["measurementStatus"] == "completed", "command failed")
        require(absent(measurement["pid"]), "command still present")
        for stream in ["stdout", "stderr"]:
            require(sha(w / (role + "." + stream)) == measurement[stream + "Digest"], "command log changed")
    require(json.loads((w / "installed-native-engine.stdout").read_text()) == dist["engines"], "executed installed engine mismatch")
    require(str(native / "bin/patamaps") in roles["installed-native-engine"]["argv"], "wrong installed executable")
    require(str(qualifier) in roles["installed-ready-controls"]["argv"] and str(helper) in roles["installed-ready-controls"]["argv"], "wrong control command")
    expected_cases = {
        "test_default_seven_cases_are_unchanged": None,
        "test_invalid_inspector_refuses_before_server_or_outputs": None,
        "test_inspector_requests_the_live_owned_server": None,
        "test_inspector_failure_stops_owned_server": "OWNER_INSPECTOR_TEST_FAILURE",
        "test_reappeared_producer_refuses_after_inspector": "OWNER_PRODUCER_REAPPEARED",
        "test_sigterm_during_inspector_stops_owned_server": "OWNER_PROBE_CANCELLED",
    }
    cases = {p.name: p for p in (w / "controls").iterdir() if p.is_dir()}
    require(set(cases) == set(expected_cases), "installed case membership")
    servers, http = [], 0
    for name, directory in sorted(cases.items()):
        require(helper.as_uri() in (directory / "run.mjs").read_text(), "control used different helper")
        exit_record = read(directory / "exit.json")
        require(exit_record["timedOut"] is False, "control timed out")
        if "invalid_inspector" in name:
            require(exit_record["exitCode"] == 1 and not (directory / "server-process.json").exists() and not (directory / "http.json").exists(), "invalid inspector effects")
            continue
        process, report = read(directory / "server-process.json"), read(directory / "http.json")
        require(process["closed"] is True and report["serverStopped"] is True and absent(process["pid"]), "server cleanup")
        require([v["status"] for v in report["cases"]] == [200, 200, 403, 404, 200, 200, 404], "seven HTTP outcomes")
        code = expected_cases[name]
        require(exit_record["exitCode"] == (1 if code else 0), "case exit mismatch")
        if code:
            require(report["status"] == "failed" and code in report["failureCodes"], "expected refusal missing")
        else:
            require(report["status"] == "passed-current-owner-edited-runtime-http", "positive control failed")
            require(("readyInspectionCompleted" in report) == ("requests_the_live" in name), "default/hook report mismatch")
        if "requests_the_live" in name:
            require(report["readyInspectionCompleted"] is True and read(directory / "http.json.inspection.json")["ready"] is True, "ready inspector did not complete")
        servers.append(process["pid"]); http += len(report["cases"])
    require(len(servers) == result["ownedServersReapedAndAbsent"] == 5 and http == result["httpCasesPassed"] == 35, "control counts")
    logs = (w / "installed-ready-controls.stderr").read_text()
    require("Ran 6 tests" in logs and "\nOK\n" in logs and "skipped=" not in logs, "unittest pass missing")
    status = json.loads(subprocess.check_output([str(args.node), str(args.buildctl), "status"], text=True, timeout=15))
    require(status["parallelActivated"] is False and status["legacyLease"] is None and status["transactionBlocked"] is False, "scheduler not finalized")
    reservation_id = re.search(r"Build reservation queued: ([0-9a-f-]{36});", (w / "supervisor.stderr").read_text()).group(1)
    reservation = next(r for r in status["requests"] if r["id"] == reservation_id)
    require(reservation["state"] == "finished" and reservation["leaseReleaseCompleted"] is True, "reservation not released")
    require(reservation["limits"]["diskBytes"] == 4_000_000_000 and reservation["enforcement"] == "native-exclusive", "guard policy changed")
    for name in ["launch.json", "supervisor.json"]:
        require(absent(read(w / name)["pid"]), "monitor/supervisor still present")
    guard_path = Path(re.search(r"^Storage guard record: (.+)$", (w / "supervisor.stdout").read_text(), re.M).group(1))
    guard = read(guard_path)
    require(guard["completed"] is True and guard["exitCode"] == 0 and guard["filesDeleted"] == 0, "guard not successful")
    require(not guard.get("newSurvivingContainers") and not guard.get("existingContainerUncertainty"), "container uncertainty")
    output = {
        "status": "passed-exact-packaged-installed-inspector-controls",
        "observedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "packageSourceRevision": cfg["revision"], "engine": dist["engines"],
        "binaryDigest": cfg["binaryDigest"], "buildProfile": "development",
        "binaryReusedFromPreviouslyAcceptedCompiler": True,
        "identicalPreviouslyCompiledRustInputFiles": len(new_code), "freshSourceCompilerBuilt": False,
        "archives": archive_info, "sourceInventoryDigest": dist["sourceInventoryDigest"],
        "sourceMembersMatchedGitArchiveAndExtraction": len(inventory),
        "sourceBytesIncludingInventory": sum(v["bytes"] for v in inventory) + (source / "source-inventory.json").stat().st_size,
        "linkedEvidence": dist["sourceEvidence"], "installedSourceWithoutGit": True,
        "probeDigest": sha(helper), "qualifierDigest": sha(qualifier),
        "controlsPassed": 6, "httpCasesPassed": http, "ownedServersReapedAndPidAbsent": 5,
        "installedNativeEngineExecutedAndMatched": True, "installedSourceInventoryUnchanged": True,
        "oldCliAndSourceInventoryUnchanged": True, "checkoutHelperUnavailableClaimed": False,
        "reservationId": reservation_id, "reservationFinishedAndReleased": True,
        "guardRecordDigest": sha(guard_path), "controllerReceiptDigest": sha(w / "receipt.json"),
        "controllerDigest": sha(w / "run.py"), "reviewerDigest": sha(Path(__file__)),
        "ownerBuildsRepeated": 0, "filesDeleted": 0, "policyChanged": False, "parallelActivated": False,
        "realOwnerBrowserAccepted": False, "backendAuthenticationAccepted": False,
        "installedBrowserWorkflowAccepted": False, "deploymentAccepted": False,
        "performanceAccepted": False, "completeGoalAccepted": False,
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": output["status"], "sourceFiles": len(inventory), "controlsPassed": 6, "httpCasesPassed": http}))

if __name__ == "__main__":
    main()
