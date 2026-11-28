#!/usr/bin/env python3
"""Read-only checks for one explicitly approved sealed-native release."""
import argparse, hashlib, json, subprocess
from pathlib import Path

RID = "7dcd23fe-8910-4eb2-8533-d0227fb31f13"
SCOPE = "26e5c36400db030d72abba6d0b02b2062b6d8daf1e2e89a7fd5e4eceba068e2f"
EXPECTED = {
    "request.before.json": "91ab3b6db393fafb61f22d4748a9ecf36ef04159b3e6c078b36fd6c206a168c6",
    "owner.json": "3a9468d9cefc232fbc6ca0f4e503dd053f68cbd6ec985957a82af7f98d485b79",
    "retained-run.json": "9b701bd112432a9148268634c712812e6b2ccbdbda80d87c77469622429f60d5",
}
def need(value, message):
    if not value:
        raise RuntimeError(message)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    return json.loads(p.read_text())
def main():
    a = argparse.ArgumentParser()
    a.add_argument("--proposal", type=Path, required=True)
    a.add_argument("--scheduler-directory", type=Path, required=True)
    a.add_argument("--node", required=True)
    a.add_argument("--buildctl-module", required=True)
    a.add_argument("--docker", required=True)
    o = a.parse_args()
    archive = o.scheduler_directory / "runs" / ("reviewed-sealed-native-" + RID)
    need(digest(o.proposal / "scope.json") == SCOPE, "Scope changed")
    scope = read(o.proposal / "scope.json")
    need(scope["id"] == RID, "Wrong scope")
    for name, wanted in EXPECTED.items():
        need(digest(archive / name) == wanted, "Archived preimage changed: " + name)
    approval = read(o.proposal / "APPROVAL.json")
    need(approval["reservationId"] == RID and approval["userApproved"] is True
         and approval["scopeSha256"] == SCOPE, "Approval mismatch")
    original = read(archive / "request.before.json")
    current = read(o.scheduler_directory / "scheduler" / "requests" / (RID + ".json"))
    need(current["id"] == RID and current["state"] == "finished"
         and current["leaseReleaseCompleted"] is True, "Reservation not released")
    allowed = {"state", "leaseReleaseCompleted", "progress", "reviewedNativeRecovery"}
    changed = {key for key in original.keys() | current.keys()
               if original.get(key) != current.get(key)}
    need(changed <= allowed, "Unexpected reservation fields changed")
    need(current["reviewedNativeRecovery"]["originalOutcomeFailed"] is True,
         "Failure relabeled")
    guard = read(archive / "retained-run.json")
    need(guard["completed"] is False and guard["exitCode"] == 75
         and guard["filesDeleted"] == 0, "Failed guard outcome changed")
    need(not (o.scheduler_directory / "active-run").exists(), "Compatibility lease held")
    recovery = read(o.proposal / "recovery-result.json")
    need(recovery["status"] == "reviewed-sealed-native-reservation-recovered"
         and recovery["reservationId"] == RID and recovery["leaseReleased"] is True,
         "Recovery report mismatch")
    need(recovery["filesDeleted"] == 0 and recovery["servicesStopped"] == 0
         and recovery["policyChanged"] is False
         and recovery["qualificationRetried"] is False, "Recovery scope expanded")
    observations = recovery["observations"]
    need(len(observations) == 3 and len({x["engineId"] for x in observations}) == 1,
         "Incomplete stop review")
    for x in observations:
        need(x["recordedGroupAbsent"] is True, "Recorded group present")
        need(all(x[k] == 0 for k in ["tokenProcessCount", "projectCommandProcessCount",
             "openProjectFileProcessCount", "unknownOpenFileProcessCount",
             "matchingContainerCount"]), "Uncertain owned workload")
    js = ("import {Scheduler} from " + json.dumps(o.buildctl_module) + ";"
          "const s=new Scheduler();console.log(JSON.stringify({"
          "active:s.requests().filter(x=>['running','preparing','needs-review'].includes(x.state)).length,"
          "queued:s.requests().filter(x=>x.state==='queued').length}));")
    counts = json.loads(subprocess.check_output(
        [o.node, "--input-type=module", "-e", js], text=True, timeout=30))
    need(counts["active"] == 0 and counts["queued"] == 0, "Scheduler changed")
    cid = "a0aad891673301454689ad960980e85efa82078e93fbd326b77c149708676d0b"
    state = subprocess.check_output(
        [o.docker, "inspect", "--format", "{{.Id}} {{.State.Status}}",
         "advocates-local-advocates-db-1"], text=True, timeout=30).strip()
    need(state == cid + " running", "Original database not running")
    ready = subprocess.run([o.docker, "exec", cid, "pg_isready"],
                           capture_output=True, text=True, timeout=30)
    need(ready.returncode == 0, "Database not ready")
    print(json.dumps({
        "status": "passed-approved-reservation-recovery-review",
        "reservationId": RID, "reservationState": "finished", "leaseReleased": True,
        "archivedPreimageHashes": EXPECTED, "scopeSha256": SCOPE,
        "requestChangesWithinReviewedFields": True,
        "originalGuardCompleted": False, "originalGuardExitCode": 75,
        "stopObservationCount": 3, "sameRuntime": True,
        "activeReservationCount": counts["active"], "queuedReservationCount": counts["queued"],
        "originalDatabaseRunning": True, "originalDatabaseReady": True,
        "filesDeleted": 0, "servicesStopped": 0, "policyChanged": False,
        "qualificationRetried": False, "watchAcceptance": "not-established",
        "goalComplete": False
    }, indent=2))
if __name__ == "__main__":
    main()
