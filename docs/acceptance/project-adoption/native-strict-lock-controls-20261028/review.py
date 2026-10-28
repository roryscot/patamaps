"""Review strict-lock kernel/guardian evidence without rerunning workloads."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
def need(ok,why):
 if not ok:raise RuntimeError(why)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
BASE_CHECKS=set("""initialTcp4Denied initialTcp6Denied initialUnixDenied initialMachLookupDenied
sessionLeader sessionCannotDetach canReadSelectedFixture ownedWriteAllowed
outsideWriteDenied symlinkWriteDenied externalSignalDenied extraFdClosed stdinIsPipe
forkDenied posixSpawnDenied afterExecTcp4Denied afterExecTcp6Denied afterExecUnixDenied
afterExecMachLookupDenied execPreservedPid""".split())
EXTRA_CHECKS=set("""protectedHardlinkDenied lockHardlinkDenied ownedHardlinkDenied
lockOpenAndFlockAllowed lockParentWriteDenied selfProcessPathAllowed externalProcessPathDenied
afterExecProtectedHardlinkDenied afterExecLockOpenAllowed""".split())
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);args=p.parse_args()
 root=args.root.resolve();work=root/".tools/native-strict-lock-20261028";a=work/"attempt-1"
 sys.path.insert(0,str(root/"scripts"))
 import native_inspection as primitive
 from native_inspection_guard import validate_records,OUTPUT_LIMIT
 read=lambda p:json.loads(p.read_text())
 value=read(a/"receipt.json");need(value["status"]=="passed-strict-lock-controls","qualification did not pass")
 roles=["legacy-kernel","strict-kernel","legacy-guardian","strict-guardian","watch-policy"]
 need(value["commands"]==[dict(role=r,exitCode=0) for r in roles],"command set changed")
 need(read(work/"control-1/exit.json")["exitCode"]==0,"canonical guard failed")
 initial=read(work/"attempt-0/strict-kernel/receipt.json")
 need(initial["status"]=="failed-native-inspection-kernel-qualification","initial failure changed")
 need({k for k,v in initial["checks"].items() if v is not True}=={"externalProcessPathDenied"},"initial failed control changed")
 expected=value["sourceBindings"]
 for name,h in expected.items():
  need(sha(root/name)==h and sha(a/Path(name).name)==h,"source changed:"+name)
 need(hashlib.sha256(primitive.PROFILE.encode()).hexdigest()=="b444e7406ca76f003a51959dd9953b47a275f81d98bcb2c2dcc3ea6a9fc11bb5","legacy profile changed")
 pids=set()
 for mode,count,profile in [("legacy-kernel",20,primitive.PROFILE),("strict-kernel",29,primitive.LOCK_PROFILE)]:
  d=a/mode;v=read(d/"receipt.json");out=read(d/"payload.stdout")
  need(v["status"]=="passed-native-inspection-kernel-qualification" and v["childStopped"] is True and v["payloadExitCode"]==0,"kernel case failed")
  need(set(v["checks"])==BASE_CHECKS|(EXTRA_CHECKS if count==29 else set()) and len(v["checks"])==count and all(x is True for x in v["checks"].values()),"kernel control set changed")
  need(out["checks"]==v["checks"] and out["pid"]==v["requestedProfile"]["pid"],"kernel raw record mismatch")
  need(v["profileSha256"]==v["requestedProfile"]["profileSha256"]==hashlib.sha256(profile.encode()).hexdigest(),"profile changed")
  need(v["unsandboxedBaselinesPassed"]==["tcp4","tcp6","unix","mach"] and len(v["rootRefusals"])==4,"baselines/root refusals changed")
  for label,name in [("helper","scripts/native_inspection.py"),("qualifier","scripts/qualify_native_inspection.py")]:
   need(v["sourceHashesBefore"][label]==sha(d/(label+".executed.py"))==expected[name],"kernel execution source changed")
  fixture=Path(v["retainedFixture"])
  need((fixture/"supervisor/sentinel").read_bytes()==b"unchanged-fixture","protected fixture changed")
  if count==29:
   need(set(v["lockRefusals"])=={"relative","alias","symlink","shared","nonempty","worldreadable","directory","wrongname","overlap","missing","preseeded-workspace"},"lock refusal set changed")
   need(v["driverLockUnchanged"] is True and primitive.owned_driver_lock(fixture/"supervisor/driver.lock",fixture/"job")==v["originalLockIdentity"],"lock changed")
  pids.add(out["pid"])
 for role,count in [("legacy-guardian",10),("strict-guardian",15),("watch-policy",11)]:
  text=(a/(role+".stderr")).read_text()
  need(re.search(r"Ran "+str(count)+r" tests in ",text) and text.rstrip().endswith("OK")
       and len(re.findall(r"^test_.* \.\.\. ok$",text,re.M))==count,"unit control transcript incomplete")
 fixtures=list(a.glob("inspection-guardian-*"));need(len(fixtures)==2,"guardian fixture set changed")
 calls=complete=incomplete=invalidated=direct=0
 for fixture in fixtures:
  for path in fixture.glob("*/jobs/*/control.json"):
   v=read(path);rows=v["records"];d=read(path.parent/"descriptor.json");calls+=1
   pids.add(v["guardianPid"])
   need(v["automaticReservationReleaseQualified"] is False,"release claim changed")
   need((path.parent/"stdout").stat().st_size<=OUTPUT_LIMIT,"output bound exceeded")
   for row in rows:pids.update(row[k] for k in ["guardianPid","parentPid","pid"] if k in row)
   if path.parents[2].name=="test_allowed_lock_write_invalidates_completion_proof":
    need(v["guardianExitCode"]==0 and rows[-1]["bindingsUnchanged"] is False,"lock mutation accepted")
    try:validate_records(rows,d["runId"],v["guardianPid"])
    except ValueError:pass
    else:raise RuntimeError("invalid lock proof admitted")
    invalidated+=1
   elif len(rows)==2:
    need(v["guardianExitCode"]==75 and "timed out" in (path.parent/"stderr").read_text(),"incomplete proof not refused");incomplete+=1
   else:
    validate_records(rows,d["runId"],v["guardianPid"]);complete+=1
    need(v["guardianExitCode"] in [0,7,75],"unexpected guardian outcome")
    if v["guardianExitCode"]==75:need("INSPECTION_DATA_OUTPUT_LIMIT" in (path.parent/"stderr").read_text(),"missing overflow refusal")
  for path in fixture.glob("*/control-records.json"):
   rows=read(path);validate_records(rows,rows[0]["runId"],rows[0]["guardianPid"]);direct+=1
   for row in rows:pids.update(row[k] for k in ["guardianPid","parentPid","pid"] if k in row)
 need((calls,complete,incomplete,invalidated,direct)==(28,25,2,1,6),"guardian lifecycle coverage changed")
 process=read(work/"control-1/process.json");pids.update([process["monitorPid"],process["guardPid"]])
 for pid in sorted(pids):
  ps=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
  need(ps.returncode!=0 or not ps.stdout.strip() or ps.stdout.strip().startswith("Z"),"observed process live:"+str(pid))
 status=json.loads(subprocess.check_output(["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs","status"]))
 req_id=re.search(r"Build reservation queued: ([0-9a-f-]{36})",(work/"control-1/guard.stderr").read_text()).group(1)
 req=next(x for x in status["requests"] if x["id"]==req_id)
 need(req["state"]=="finished" and req["leaseReleaseCompleted"] is True,"reservation not released")
 need(status["mode"]=="exclusive-fallback" and status["parallelActivated"] is False,"mode changed")
 receipt=dict(status="passed-independent-strict-lock-controls",sourceBindings=expected,
  legacyKernelControls=20,strictKernelControls=29,unsafeLockDeclarationsRefused=11,
  legacyGuardianControls=10,strictGuardianControls=15,watchPolicyControls=11,
  retainedAdapterCalls=calls,completeAdapterLifecycles=complete,directCompleteLifecycles=direct,
  incompleteTimeoutLifecycles=incomplete,invalidatedLockMutationLifecycles=invalidated,
  observedProcessesStopped=len(pids),reservationId=req_id,reservationReleased=True,repairsUsed=1,
  initialAttemptPassed=False,strictProfileDigest=hashlib.sha256(primitive.STRICT_PROFILE.encode()).hexdigest(),
  lockedProfileDigest=hashlib.sha256(primitive.LOCK_PROFILE.encode()).hexdigest(),
  automaticReservationReleaseQualified=False,installedSupervisorChanged=False,
  actualOwnerWatchRetried=False,parallelActivated=False,realUnchangedBuildQualified=False,reviewerDigest=sha(__file__))
 (work/"independent-review.json").write_text(json.dumps(receipt,indent=2)+"\n")
 (work/"CONTROL_QUALIFIED.json").write_text(json.dumps(receipt,indent=2)+"\n")
 print(json.dumps(receipt))
if __name__=="__main__":main()
