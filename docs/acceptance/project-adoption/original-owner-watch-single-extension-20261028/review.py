"""Read-only review of the single approved original-owner W0 extension."""
from pathlib import Path
import argparse, datetime, hashlib, json, re, stat, subprocess

DRIVER = "sha256:81679cffc71a7cd3a5773b81ef1acb2bc9be9d0ae4a002a425c3b62bf75e0f4b"
POINTER = "sha256:14b7cca4fb50330d7827c51327899969416aad31a3e70ce1e6d3994169282352"
ARTIFACTS = "sha256:96e70d1cfd993e38051ca24fde1fc384b9e91bd2a362bd331e87cbf4b1c4776d"
LEDGER = "sha256:fbcaa4574fca00367f326c6a699b1899e6684c567ae6171b17e154b256429951"
KEY = "sha256:b1d1c79a5f81832e0d01029e4f446b3ffcdacbbc1b60f9920ec304c877e3ffdc"
ATTEMPT = "1793122875791456000-6699"

def need(value, reason):
    if not value:
        raise RuntimeError(reason)
def read(p):
    return json.loads(p.read_text())
def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(1048576):
            h.update(b)
    return "sha256:" + h.hexdigest()
def events(text):
    result, decoder = [], json.JSONDecoder()
    for match in re.finditer(r"(?m)^\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result
def absent(pid, identity=None):
    x = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart="],
                       text=True, capture_output=True, timeout=5)
    need(x.returncode in [0, 1], "Process inspection unavailable")
    current = x.stdout.strip()
    return not current or (identity is not None and current != identity)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--expect", choices=["passed", "failed"], required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    need(not a.output.exists(), "Output already exists")
    root = a.root
    base = root / ".tools/original-owner-watch-20261028"
    w = base / "noop-retry-proposal"
    d, f, scope = read(w / "receipt.json"), read(w / "frozen.json"), read(w / "scope.json")
    approval = read(w / "APPROVAL.json")
    need(approval["userApproved"] is True and approval["attemptsAuthorized"] == 1
         and approval["automaticRepairsAuthorized"] == 0
         and approval["scopeSha256"] == sha(w / "scope.json")[7:], "Approval mismatch")
    need(sha(w / "run.py") == f["driverDigest"] == DRIVER, "Driver changed")
    for name, key in [("monitor.py", "monitorSha256"), ("frozen.json", "freezeSha256"),
                      ("RETRY_PROPOSAL.md", "proposalSha256")]:
        need(sha(w / name)[7:] == scope[key], "Proposal changed")
    code = read(w / "controller-exit.json")["exitCode"]
    passed = code == 0 and d["status"] == "passed-actual-owner-noop-idle-sigterm-watch"
    need(passed == (a.expect == "passed"), "Unexpected qualification outcome")
    if not passed:
        need(code != 0 and d["status"] == "failed-actual-owner-noop-watch", "Not terminal failure")
    need(absent(read(w / "launch.json")["monitorPid"],
                read(w / "launch.json")["monitorIdentity"]), "Monitor still live")
    need(absent(read(w / "controller-process.json")["pid"]), "Controller still live")
    need(absent(read(w / "watch-process.json")["pid"]), "Watcher still live")

    for path, expected in f["inputs"].items():
        need(sha(Path(path)) == expected, "Owner plan/tool binding changed")
    origin = root / ".tools/installed-original-owner-next-20261027/owner-native"
    state = Path(read(origin / "receipt.json")["state"])
    selected = read(state / "selected.json")
    need(sha(state / "selected.json") == POINTER and selected["inputKey"] == KEY,
         "Original selection changed")
    need(sorted(q.name for q in (state / "attempts").iterdir()) == [ATTEMPT],
         "Original attempts changed")
    attempt = state / selected["attempt"]
    need(sha(attempt / "artifacts.json") == ARTIFACTS and
         sha(attempt / "candidate/patamaps-native-tooling/trace.jsonl") == LEDGER,
         "Artifacts or execution ledger changed")
    count = 0
    for name, item in read(attempt / "artifacts.json").items():
        q = attempt / "candidate" / name
        s = q.lstat()
        need(stat.S_IMODE(s.st_mode) == item["mode"], "Artifact mode changed")
        if item["kind"] == "file":
            need(stat.S_ISREG(s.st_mode) and s.st_size == item["bytes"]
                 and sha(q) == item["digest"], "Artifact bytes changed")
            count += 1
        else:
            need(item["kind"] == "directory" and stat.S_ISDIR(s.st_mode), "Artifact kind changed")
    need(count == 2482, "Artifact count changed")
    fixture = read(root / ".tools/installed-original-owner-next-20261027/owner-fixture.json")
    for name, expected in fixture["sourceInputs"].items():
        need(sha(origin / "owner" / name) == expected, "Owner source changed")
    for name, expected in fixture["expectedGenerated"].items():
        need(sha(Path(fixture["originalOracle"]) / name) == expected, "Original oracle changed")
    package = read(root / ".tools/installed-watch-policy-20261028/receipt.json")
    source = Path(package["installedSource"])
    need(sha(source / "source-inventory.json") == f["sourceInventoryDigest"], "Source inventory changed")
    members = read(source / "source-inventory.json")
    need(len(members) == 1255, "Wrong installed source count")
    actual = set()
    for q in source.rglob("*"):
        need(not q.is_symlink(), "Installed source symlink")
        if q.is_file():
            actual.add(q.relative_to(source).as_posix())
    need(actual == {x["path"] for x in members} | {"source-inventory.json"}, "Source members changed")
    for item in members:
        q = source / item["path"]
        need(q.stat().st_size == item["bytes"] and sha(q) == item["digest"], "Installed source changed")
    need(sha(source / "scripts/project_watch.py") == f["watchDigest"], "Installed helper changed")
    need(sha(Path(package["installedNative"]) / "bin/patamaps") == f["cliDigest"], "Native CLI changed")

    log = (w / "watch.stdout").read_text()
    need(len(log.encode()) <= f["bounds"]["stdoutBytes"], "Watch stdout limit")
    need((w / "watch.stderr").stat().st_size <= f["bounds"]["stderrBytes"], "Watch stderr limit")
    elapsed = (datetime.datetime.fromisoformat(d["finishedAtUtc"]) -
               datetime.datetime.fromisoformat(d["startedAtUtc"])).total_seconds()
    need(0 <= elapsed and (not passed or elapsed <= f["bounds"]["caseSeconds"]),
         "Successful case exceeded its time bound")
    ev = events(log)
    ids = list(dict.fromkeys(re.findall(r"Build reservation queued: ([0-9a-f-]{36});",
                                       (w / "watch.stderr").read_text())))
    need(len(ids) <= 2, "Extra reservation")
    js = ('import {Scheduler,confirmedStopped} from "/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs";'
          'const s=new Scheduler();const ids=' + json.dumps(ids) + ';'
          'console.log(JSON.stringify({parallel:s.status().parallelActivated,'
          'requests:s.requests().filter(r=>ids.includes(r.id)).map(r=>({...r,canonicalStopped:confirmedStopped(r)}))}));')
    current = json.loads(subprocess.check_output(
        ["/Users/admin/.nvm/versions/node/v22.23.3/bin/node", "--input-type=module", "-e", js],
        text=True, timeout=30))
    need(current["parallel"] is False, "Parallel policy changed")
    requests = {x["id"]: x for x in current["requests"]}
    proofs = d.get("nativeProofs", {})
    for rid, proof in proofs.items():
        need(rid in ids and proof["ownerVerifiedAncestor"] and proof["compatibilityLeaseMatched"]
             and proof["enforcement"] == "native-exclusive"
             and proof["limits"] == {"cpu": 16, "memoryBytes": 34359738368, "diskBytes": 4000000000},
             "Reserved native execution proof changed")
    owned_stopped = all(absent(x["nativePid"], x["nativeIdentity"]) and
                        absent(x["ownerPid"], x["ownerIdentity"]) for x in proofs.values())
    released = all(requests[i]["state"] == "finished" and requests[i].get("leaseReleaseCompleted")
                   for i in ids)
    noop = [x for x in ev if x.get("status") == "unchanged-project-build" and
            x.get("inputKey") == KEY and x.get("verification") == "not-repeated" and
            x.get("cacheHits") == 0]
    completed = [x for x in ev if x.get("status") == "completed-project-build-update"]
    if passed:
        need(len(ids) == 2 and list(proofs) == ids and
             [proofs[i]["command"] for i in ids] == ["project-build", "project-build-verify"],
             "Two separate actual native calls missing")
        need(released and owned_stopped and all(requests[i]["canonicalStopped"] for i in ids),
             "Native reservation cleanup incomplete")
        need(len(noop) == 1 and len(completed) == 1, "No-op/update event missing")
        need(d["sigtermExitCode"] == 130 and d["idleObservedSeconds"] >= 6 and
             d["idleOwnLeaseHeld"] is False and d["idleDriverLockOpen"] is False,
             "Idle/SIGTERM acceptance missing")
        need(d["newAttempts"] == 0 and d["appBuildsRun"] == 0
             and d["policyReservationsFinishedAndReleased"] == 2, "Unexpected app work")
        lock = subprocess.run(["/usr/sbin/lsof", "-F", "pc", "--", str(state / "driver.lock")],
                              capture_output=True, text=True, timeout=15)
        need(lock.returncode == 1 and not lock.stdout.strip() and not lock.stderr.strip(),
             "Driver lock still held")
    result = dict(
        status="passed-independent-single-extension-review",
        reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        reviewerDigest=sha(Path(__file__)), producerRevision=f["producerRevision"],
        qualificationStatus="passed-noop-idle-sigterm" if passed else "failed",
        functionalCaseElapsedSeconds=elapsed, elapsedTimeIsBenchmark=False,
        functionalCaseWithinFrozenTimeBound=elapsed <= f["bounds"]["caseSeconds"],
        authorizedAdditionalAttempts=1, automaticRepairsAuthorized=0,
        driverDigest=DRIVER, approvalScopeDigest=approval["scopeSha256"],
        nativeNoopCompleted=len(noop) == 1, completedWatchUpdates=len(completed),
        actualNativeCommandsObserved=[proofs[i]["command"] for i in ids if i in proofs],
        separateExclusiveReservationsObserved=len(proofs), reservationsReleased=bool(ids) and released,
        ownedNativeProcessesStopped=owned_stopped, originalSelectionAndLedgerUnchanged=True,
        artifactsRehashed=count, ownerSourceInputsRehashed=len(fixture["sourceInputs"]),
        originalOracleOutputsRehashed=len(fixture["expectedGenerated"]), installedSourceFilesRehashed=1255,
        idleAndSigtermAccepted=passed, nativeHardCpuMemoryCapsClaimed=False,
        activeParentDeathAccepted=False, wholeW0Accepted=False, W1Accepted=False,
        performanceAccepted=False, fullAdoptionGoalComplete=False, filesDeleted=0, policyChanged=False)
    if not passed:
        reason = d.get("failure", "")
        result["failureClass"] = reason if re.fullmatch(r"[A-Z0-9_: -]{1,120}", reason) else "private-failure-detail-preserved"
        result["retainedReservationCount"] = sum(x["state"] == "needs-review" for x in requests.values())
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
if __name__ == "__main__":
    main()
