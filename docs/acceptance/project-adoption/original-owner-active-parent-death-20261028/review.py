"""Read-only failure/preservation review for the approved active-parent-death case."""
from pathlib import Path
import argparse, datetime, hashlib, json, re, stat, subprocess

DRIVER = "sha256:cc7e9194638053a7f8398b49c3e4a8e1aaf0aa7e01baa46c91852161d5902f70"
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
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    need(not a.output.exists(), "Output already exists")
    root = a.root
    base = root / ".tools/original-owner-watch-20261028"
    w = base / "parent-death-prepared"
    proposal = base / "parent-death-recovery-proposal"
    d, f, approval = read(w / "receipt.json"), read(w / "frozen.json"), read(w / "APPROVAL.json")
    need(approval["userApproved"] is True and approval["attemptsAuthorized"] == 1,
         "Exact case approval missing")
    need(sha(w / "frozen.json")[7:] == approval["freezeSha256"], "Freeze changed")
    need(sha(w / "run.py") == f["driverDigest"] == DRIVER, "Driver changed")
    need(read(w / "controller-exit.json")["exitCode"] == 1 and
         d["status"] == "failed-actual-owner-active-parent-death" and
         d["failure"] == "ACTIVE_PARENT_DEATH_CLEANUP_DEADLINE", "Failure changed")
    need(f["bounds"]["cleanupSeconds"] == 60, "Cleanup bound changed")
    launch = read(w / "launch.json")
    need(absent(launch["monitorPid"], launch["monitorIdentity"]) and
         absent(read(w / "controller-process.json")["pid"]), "Controller still live")
    proof = d["nativeProof"]
    owned = proof["ownedProcessIdentities"]
    need(proof["ownershipSealed"] and proof["compatibilityLeaseMatched"] and
         proof["limits"] == {"cpu":16,"memoryBytes":34359738368,"diskBytes":4000000000},
         "Active native precondition proof missing")
    need(owned[str(d["testParentPid"])] == d["testParentIdentity"] and
         owned[str(proof["nativePid"])] == proof["nativeIdentity"] and
         owned[str(proof["ownerPid"])] == proof["ownerIdentity"] and
         str(d["watchPid"]) in owned, "Owned ancestry proof incomplete")
    need(all(absent(int(pid), identity) for pid, identity in owned.items()),
         "Observed owned process survived")
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

    event_rows = events((w / "watch.stdout").read_text())
    need(any(x.get("status") == "cancelled-project-watch" for x in event_rows),
         "Watch cancellation event missing")
    need(not any(x.get("status") == "completed-project-build-update" for x in event_rows),
         "Cancelled update claimed complete")
    request_ids = list(dict.fromkeys(re.findall(r"Build reservation queued: ([0-9a-f-]{36});",
                                               (w / "watch.stderr").read_text())))
    need(request_ids == [proof["reservationId"]], "Cancelled case reacquired")
    js = ('import {Scheduler,confirmedStopped} from "/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs";'
          'const s=new Scheduler();const r=s.requests().find(r=>r.id==='+
          json.dumps(proof["reservationId"])+');'
          'console.log(JSON.stringify({request:r,stopped:confirmedStopped(r),'
          'parallel:s.status().parallelActivated}));')
    current = json.loads(subprocess.check_output(
        ["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","--input-type=module","-e",js],
        text=True,timeout=30))
    req = current["request"]
    need(current["stopped"] and current["parallel"] is False and
         req["state"] == "needs-review" and req["leaseReleaseCompleted"] is False and
         req["ownershipSealed"] is True and req["containerIds"] == [] and
         req["owner"]["pid"] == proof["ownerPid"] and
         req["processGroup"] == proof["processGroup"], "Retained reservation scope changed")
    control = Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds/active-run")
    g = read(control / "retained-run.json")
    need(g["completed"] is False and g["exitCode"] == 75 and
         g["filesDeleted"] == 0 and g["existingContainerUncertainty"] is True and
         g["newSurvivingContainers"] == [], "Guard failure changed")
    need(g["containersAtStart"] == g["containersAtEnd"], "Container set changed")
    pre = read(proposal / "preflight-result.json")
    need(pre["status"] == "passed-readonly-recovery-preflight" and
         pre["reservationId"] == req["id"] and pre["leaseReleased"] is False and
         len(pre["observations"]) == 3, "Stopped-workload review missing")
    need(len({x["engineId"] for x in pre["observations"]}) == 1, "Runtime changed")
    for x in pre["observations"]:
        need(x["recordedGroupAbsent"] and all(x[k] == 0 for k in
             ["tokenProcessCount","projectCommandProcessCount","openProjectFileProcessCount",
              "unknownOpenFileProcessCount","matchingContainerCount"]), "Uncertain ownership")
    need(not (proposal / "APPROVAL.json").exists() and
         not (proposal / "recovery-result.json").exists(), "Recovery already authorized/applied")
    need(sha(control / "retained-run.json")[7:] == read(proposal / "scope.json")["guardSha256"],
         "Guard differs from recovery scope")
    docker = "/Applications/Docker.app/Contents/Resources/bin/docker"
    database = subprocess.check_output([docker,"inspect","--format",
                "{{.Id}} {{.State.Status}} {{.State.StartedAt}}","advocates-local-advocates-db-1"],
                text=True,timeout=20).strip()
    need(database == read(w / "database-before.json")["metadata"], "Original database restarted/changed")
    need(subprocess.run([docker,"exec","advocates-local-advocates-db-1","pg_isready"],
         capture_output=True,text=True,timeout=20).returncode == 0, "Database not ready")
    previous = read(root / "docs/acceptance/project-adoption/original-owner-watch-single-extension-20261028/receipt.json")
    need(previous["qualificationStatus"] == "passed-noop-idle-sigterm", "Earlier pass missing")
    result = dict(status="passed-independent-parent-death-failure-preservation-review",
        reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        reviewerDigest=sha(Path(__file__)),producerRevision=f["producerRevision"],
        qualificationStatus="failed",failureClass=d["failure"],
        cleanupBoundSeconds=60,leaseReleasedWithinBound=False,
        activeNativePreconditionVerified=True,onlyTestParentSignal="SIGKILL",
        observedOwnedProcessCount=len(owned),allObservedOwnedProcessesStopped=True,
        watchCancellationEventRecorded=True,completedWatchUpdates=0,
        watchExitCodeDirectlyObserved=False,testParentExitCodeDirectlyRecorded=False,
        parentSignalConfirmedByBoundDriverControlFlow=True,
        retainedReservationId=req["id"],canonicalConfirmedStopped=True,
        stopInventoryCount=3,stopInventoriesClear=True,stableContainerSet=True,
        originalDatabaseRunningAndReady=True,originalDatabaseStartUnchanged=True,
        guardCompleted=False,guardExitCode=75,existingContainerUncertainty=True,
        newSurvivingContainers=0,
        endAvailableSpaceDropBytes=g["freeBytesAtStart"]-g["freeBytesAtEnd"],
        diskGrowthFailureReported="disk-growth budget was exceeded" in (w/"watch.stderr").read_text(),
        originalSelectionAndLedgerUnchanged=True,artifactsRehashed=count,
        ownerSourceInputsRehashed=len(fixture["sourceInputs"]),
        originalOracleOutputsRehashed=len(fixture["expectedGenerated"]),
        installedSourceFilesRehashed=1255,previousNoopIdleSigtermPassPreserved=True,
        recoveryApprovalRecorded=False,recoveryApplied=False,
        activeParentDeathAccepted=False,wholeW0Accepted=False,W1Accepted=False,
        fullAdoptionGoalComplete=False,filesDeleted=0,servicesStopped=0,policyChanged=False)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__ == "__main__":
    main()
