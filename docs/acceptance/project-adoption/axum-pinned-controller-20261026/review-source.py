"""Review real retained-controller independence; no performance acceptance."""
from pathlib import Path
import datetime,hashlib,json,subprocess

ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
WORK=ROOT/".tools/axum-pinned-preparation-retry-20261026"
OUT=ROOT/"docs/acceptance/project-adoption/axum-pinned-controller-20261026"
def read(p):return json.loads(p.read_bytes())
def sha(p):return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()

report=read(WORK/"functional-preparation.json")
prepared=read(WORK/"actual-axum/preparation.json")
assert report["status"]=="passed-guarded-functional-preparation" and report["benchmarkRun"] is False
for key in ["pinnedControllerIndependent","sharedCompilerRestored","coldTargetAbsent","measuredStateAbsent"]:assert report[key] is True,key
commands={item["label"]:item["measurement"] for item in report["commands"]}
expected={"existing-measurement-controls","current-cli-build","real-axum-preparation","pinned-engine-shared-cli-unavailable","pinned-input-key-shared-cli-unavailable"}
assert set(commands)==expected and all(item["exitCode"]==0 for item in commands.values())
tests=(WORK/"existing-measurement-controls.stderr").read_text()
assert "Ran 13 tests" in tests and tests.rstrip().endswith("OK")
pinned=Path(prepared["cli"]);shared=ROOT/"target/debug/patamaps"
assert pinned==WORK/"actual-axum/tools/configured-provider"
assert sha(pinned)==sha(shared)==prepared["cliDigest"]==report["sharedCliBefore"]["digest"]
assert shared.stat().st_mode & 0o777==report["sharedCliBefore"]["mode"]
assert not (WORK/"temporarily-held-shared-cli").exists()
assert prepared["nativeBenchmarkRun"] is False
assert not (WORK/"actual-axum/cargo-target").exists() and not (WORK/"actual-axum/state").exists()
for name,digest in prepared["coordinatorDigests"].items():assert sha(ROOT/"scripts"/name)==digest
for name,digest in prepared["supervisorDigests"].items():assert sha(Path(name))==digest
for name,digest in prepared["protectedInputs"].items():assert sha(Path(name))==digest
for name,digest in prepared["ownerInputs"].items():assert sha(WORK/"actual-axum/owner"/name)==digest
assert sha(WORK/"actual-axum/plan.json")==prepared["planDigest"]
assert sha(WORK/"actual-axum/binding.json")==prepared["bindingDigest"]
assert json.loads(subprocess.check_output([pinned,"engine"],text=True))==prepared["engine"]
assert prepared["originalSelectedTextInputs"]==333 and prepared["measuredTextInputs"]==337
proof=prepared["preparationReservation"]
assert proof["phase"]=="functional" and proof["resourceLimits"]["diskBytes"]==4000000000
assert proof["otherActiveReservations"]==0 and proof["enforcement"]=="native-exclusive"
status=json.loads(subprocess.check_output(["/Users/admin/Documents/Codex/storage-safeguards/buildctl","status"],text=True))
own=next(x for x in status["requests"] if x["id"]==proof["id"])
assert own["state"]=="finished" and own["ownerAlive"] is False
assert own.get("leaseReleaseCompleted") is True,own
assert not status["legacyLease"] and status["transactionBlocked"] is False
assert not any(x["state"] in ["queued","running","needs-review"] for x in status["requests"])
summary=dict(status="passed-independent-retained-controller-review",observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 sourceRevision=prepared["sourceRevision"],cliDigest=prepared["cliDigest"],engine=prepared["engine"],
 controllerIsRetainedConfiguredProvider=True,sharedCompilerUnavailableDuringTwoSuccessfulCommands=True,
 sharedCompilerBytesAndModeRestored=True,existingMeasurementControlsPassed=13,
 commands=[dict(label=label,exitCode=m["exitCode"],wallNanoseconds=m["wallNanoseconds"]) for label,m in commands.items()],
 preparationDigest=sha(WORK/"actual-axum/preparation.json"),runnerDigest=sha(WORK/"prepare.py"),
 coordinatorDigests=prepared["coordinatorDigests"],supervisorDigests=prepared["supervisorDigests"],
 ownerInputsRehashed=337,originalSelectedTextInputs=333,sourceFiles=prepared["sourceFiles"],
 planDigest=prepared["planDigest"],bindingDigest=prepared["bindingDigest"],
 protectedOriginalRecordsRehashed=True,coldCargoTargetAbsent=True,measuredStateAbsent=True,
 reservationId=proof["id"],reservationFinished=True,nativeExclusive=True,diskReservationBytes=4000000000,
 filesDeleted=0,policyChanged=False,benchmarkRun=False,performanceAccepted=False,fullG4Accepted=False,completeGoalAccepted=False)
OUT.mkdir(exist_ok=False)
(OUT/"review.json").write_text(json.dumps(summary,indent=2)+"\n")
(OUT/"review-source.py").write_bytes(Path(__file__).read_bytes())
print(json.dumps(summary,indent=2))
