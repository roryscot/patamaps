"""Review exact approved cleanup and actual native preparation; publish compact facts."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess

ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
CLEANUP=ROOT/".tools/approved-publication-deps-cleanup-20261026"
REVIEW=ROOT/".tools/retention-review-20261024-publication-deps"
PREP=ROOT/".tools/axum-guarded-preparation-20261026"
OUT=ROOT/"docs/acceptance/project-adoption/intel-native-resume-20261026"
def read(p):return json.loads(p.read_bytes())
def sha(p):return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
cleanup=read(CLEANUP/"receipt.json")
assert cleanup["status"]=="passed-exact-approved-cleanup"
assert cleanup["filesDeleted"]==cleanup["approvedFiles"]==cleanup["approvedPathsConfirmedAbsent"]==3491
assert cleanup["approvedAllocatedBytes"]==4592123904
for key in ["directoriesDeleted","unlistedEntriesDeleted"]:
 assert cleanup[key]==0,key
assert cleanup["sourceGitStateUnchanged"] is True and cleanup["policyChanged"] is False
assert cleanup["unlistedEntriesPreserved"]==845 and cleanup["parentDirectoriesPreserved"]==5
inventory=REVIEW/"inventory.jsonl"
assert sha(inventory)=="sha256:"+cleanup["inventorySha256"]
rows=[json.loads(line) for line in inventory.read_bytes().splitlines()]
journal=[json.loads(line) for line in (CLEANUP/"unlink-journal.jsonl").read_bytes().splitlines()]
assert len(rows)==len(journal)==3491
approved={r["path"]:r for r in rows}
assert len({r["path"] for r in journal})==3491
for item in journal:
 original=approved[item["path"]]
 assert item["deleted"] is True and item["inode"]==original["inode"] and item["device"]==original["device"]
 assert not os.path.lexists(item["path"])
parents={Path(row["path"]).parent for row in rows}
excluded=read(REVIEW/"excluded-paths.json")
assert len(excluded)==845 and {str(p) for parent in parents for p in parent.iterdir()}==set(excluded)
for parent in parents:assert parent.is_dir() and parent.resolve()==parent
archives=read(REVIEW/"summary.json")["preservedFrozenCrateArchives"]
for item in archives:
 path=Path(item["path"]);assert path.stat().st_size==item["bytes"] and sha(path)=="sha256:"+item["sha256"]
maintenance=read(CLEANUP/"maintenance-finalization.json")
assert maintenance["ownLegacyLeaseArchived"] and maintenance["ownTransactionArchived"] and maintenance["policyChanged"] is False
supervisor=read(PREP/"supervisor-result.json");functional=read(PREP/"functional-preparation.json")
final=read(PREP/"finalization.json");prepared=read(PREP/"actual-axum/preparation.json")
assert supervisor["exitCode"]==0 and supervisor["functionalPreparationReceiptExists"]
assert functional["status"]=="passed-guarded-functional-preparation" and functional["benchmarkRun"] is False
assert len(functional["commands"])==2 and {x["label"] for x in functional["commands"]}=={"current-cli-build","real-axum-preparation"}
assert all(x["measurement"]["exitCode"]==0 for x in functional["commands"])
assert prepared["status"]=="prepared-real-axum-measurements" and prepared["nativeBenchmarkRun"] is False
assert prepared["originalSelectedTextInputs"]==333 and prepared["measuredTextInputs"]==337 and prepared["sourceFiles"]==335
assert sha(Path(prepared["cli"]))==prepared["cliDigest"]
for name,digest in prepared["coordinatorDigests"].items():assert sha(ROOT/"scripts"/name)==digest
for name,digest in prepared["supervisorDigests"].items():assert sha(Path(name))==digest
for name,digest in prepared["protectedInputs"].items():assert sha(Path(name))==digest
owner=PREP/"actual-axum/owner"
assert all(sha(owner/name)==digest for name,digest in prepared["ownerInputs"].items())
assert not (PREP/"actual-axum/cargo-target").exists() and not (PREP/"actual-axum/state").exists()
proof=prepared["preparationReservation"]
for key in ["ownerAlive","ownerIdentityVerified","ownerIsAncestor","exclusive"]:assert proof[key] is True,key
assert proof["phase"]=="functional" and proof["state"]=="running" and proof["enforcement"]=="native-exclusive"
assert proof["otherActiveReservations"]==0 and proof["resourceLimits"]["diskBytes"]==4000000000
assert final["supervisorExitCode"]==0 and final["activeOrUncertainReservations"]==0
assert not final["legacyLeasePresent"] and not final["transactionBlocked"]
engine=json.loads(subprocess.check_output([prepared["cli"],"engine"],cwd=ROOT,text=True))
assert engine==prepared["engine"]
quiet=read(PREP/"quiet-window-preflight.json")
assert len(quiet["runningContainers"])==1 and quiet["benchmarkStarted"] is False and quiet["containersStopped"] is False
OUT.mkdir(exist_ok=False)
for name,data in [("approved-cleanup.json",cleanup),("maintenance-finalization.json",maintenance),
                  ("functional-preparation.json",functional),("supervisor-result.json",supervisor),
                  ("native-finalization.json",final)]:
 (OUT/name).write_text(json.dumps(data,indent=2)+"\n")
begin=datetime.datetime.fromisoformat(read(PREP/"launch.json")["startedAtUtc"])
end=datetime.datetime.fromisoformat(supervisor["finishedAtUtc"])
summary=dict(status="passed-independent-cleanup-and-functional-preparation-review",
 observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 sourceRevision=prepared["sourceRevision"],approvedInventoryDigest=sha(inventory),
 deletionJournalDigest=sha(CLEANUP/"unlink-journal.jsonl"),deletedPathsIndependentlyConfirmed=3491,
 deletionJournalMatchesApprovedPathsAndIdentities=True,unlistedPathSetIndependentlyVerified=845,
 unlistedIdentityPreservationCheckedDuringCleanup=True,preservedCrateArchivesIndependentlyRehashed=10,
 cleanupScriptDigest=sha(CLEANUP/"cleanup.py"),cleanupWrapperDigest=sha(CLEANUP/"cleanup.mjs"),
 preparationDigest=sha(PREP/"actual-axum/preparation.json"),cliDigest=prepared["cliDigest"],
 engine=engine,originalAxumSourceCommit=prepared["sourceCommit"],snapshotDigest=prepared["snapshotDigest"],
 sourceFiles=335,originalSelectedTextInputs=333,preparedSelectedTextInputs=337,
 ownerInputMembershipDigest="sha256:"+hashlib.sha256(json.dumps(prepared["ownerInputs"],sort_keys=True,separators=(",",":")).encode()).hexdigest(),
 planDigest=prepared["planDigest"],bindingDigest=prepared["bindingDigest"],
 coordinatorDigests=prepared["coordinatorDigests"],supervisorDigests=prepared["supervisorDigests"],
 functionalReservation=dict(id=proof["id"],phase=proof["phase"],exclusive=True,enforcement=proof["enforcement"],
   nativeResourceCapsEnforced=proof["nativeResourceCapsEnforced"],diskReservationBytes=proof["resourceLimits"]["diskBytes"],
   ownerIdentityVerified=True,ownerIsAncestor=True,otherActiveReservations=0),
 functionalReservationReleased=True,coldCargoTargetAbsent=True,measuredBuildStateAbsent=True,
 protectedOriginalRecordsVerified=True,preparedOwnerBindingsVerified=True,currentEngineVerified=True,
 outerSupervisorIntervalSeconds=(end-begin).total_seconds(),
 sumMeasuredFunctionalCommandSeconds=sum(x["measurement"]["wallNanoseconds"]/1e9 for x in functional["commands"]),
 timingScope="Functional preparation observations; guard/wait/finalization overhead is outside child timers and is not isolated or a performance acceptance.",
 runningUnrelatedContainersAtPreflight=1,containerIdentitiesPublished=False,
 benchmarkStarted=False,library459TestRun=False,performanceAccepted=False,fullG4Accepted=False,
 completeGoalAccepted=False,policyChanged=False,additionalFilesDeleted=False)
(OUT/"independent-verification.json").write_text(json.dumps(summary,indent=2)+"\n")
(OUT/"review-source.py").write_bytes(Path(__file__).read_bytes())
print(json.dumps(summary,indent=2))
