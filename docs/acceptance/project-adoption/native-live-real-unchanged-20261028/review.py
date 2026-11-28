"""Review real unchanged project-build under the exact lock grant."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
def need(ok,why):
 if not ok:raise RuntimeError(why)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--root",required=True,type=Path);args=parser.parse_args()
 root=args.root.resolve();base=root/".tools/native-live-ownership-20261028";work=base/"real-unchanged"
 sys.path.insert(0,str(root/"scripts"))
 import native_inspection as primitive
 from native_inspection_guard import validate_records
 read=lambda p:json.loads(p.read_text())
 value=read(work/"receipt.json")
 need(value["status"]=="passed-real-unchanged-locked-inspection","actual unchanged build did not pass")
 need(read(work/"control/exit.json")["exitCode"]==0,"canonical guard failed")
 gate=read(base/"CONTROL_QUALIFIED.json")
 kernel_gate=read(root/".tools/native-strict-lock-20261028/CONTROL_QUALIFIED.json")
 need(gate["sourceBindings"]["scripts/native_inspection.py"]==kernel_gate["sourceBindings"]["scripts/native_inspection.py"],"kernel primitive changed")
 need(gate["status"]=="passed-independent-live-ownership-controls","kernel/guardian gate failed")
 for name,h in gate["sourceBindings"].items():need(sha(root/name)==h,"qualified source changed")
 need(value["sourceBindings"]==gate["sourceBindings"] and value["coordinatorDigest"]==sha(work/"run.py"),"execution source changed")
 native=Path(read(root/".tools/installed-watch-policy-20261028/receipt.json")["installedNative"])/"bin/patamaps"
 need(sha(native)==value["nativeCliDigest"]=="cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355","CLI changed")
 package=read(root/".tools/installed-watch-policy-20261028/receipt.json")
 origin=root/".tools/installed-original-owner-next-20261027/owner-native"
 state=Path(read(origin/"receipt.json")["state"])
 selected=read(state/"selected.json");attempt=state/selected["attempt"]
 expected_key="sha256:b1d1c79a5f81832e0d01029e4f446b3ffcdacbbc1b60f9920ec304c877e3ffdc"
 need(selected["inputKey"]==expected_key,"selected key changed")
 protected={state/"selected.json":"14b7cca4fb50330d7827c51327899969416aad31a3e70ce1e6d3994169282352",
 attempt/"artifacts.json":"96e70d1cfd993e38051ca24fde1fc384b9e91bd2a362bd331e87cbf4b1c4776d",
 attempt/"candidate/patamaps-native-tooling/trace.jsonl":"fbcaa4574fca00367f326c6a699b1899e6684c567ae6171b17e154b256429951"}
 need(value["statePreimages"]=={str(p):h for p,h in protected.items()},"accepted preimages changed")
 for p,h in protected.items():need(sha(p)==h,"protected state changed")
 need(sorted(p.name for p in (state/"attempts").iterdir())==value["originalAttempts"]==["1793122875791456000-6699"],"attempt set changed")
 need(value["protectedStateUnchanged"] is True and value["driverLockUnchanged"] is True,"preservation gate missing")
 need(value["nativeUnchangedBuildInvocations"]==1 and value["applicationCommandsExecuted"]==0 and value["newApplicationAttempts"]==0 and value["actualOwnerWatchRun"] is False,"scope changed")
 need(primitive.owned_driver_lock(state/"driver.lock",work/"locked-jobs")==value["lockIdentity"],"lock identity changed")
 need(sha(state/"driver.lock")==value["lockSha256"]==hashlib.sha256(b"").hexdigest(),"lock data changed")
 need(value["lockedProfileDigest"]==kernel_gate["lockedProfileDigest"]==hashlib.sha256(primitive.LOCK_PROFILE.encode()).hexdigest(),"lock profile changed")
 need(len(value["readOnlyCalls"])==2 and len(value["lockedCalls"])==1,"actual call set changed")
 pids=set();roles=[]
 for name,calls in [("read-only-jobs",value["readOnlyCalls"]),("locked-jobs",value["lockedCalls"])]:
  paths={read(p/"control.json")["guardianPid"]:p for p in (work/name).iterdir()}
  for call in calls:
   need(call["guardianExitCode"]==0 and call["automaticReservationReleaseQualified"] is False,"guardian result/claim changed")
   path=paths[call["guardianPid"]];d=read(path/"descriptor.json")
   need(read(path/"control.json")==call and d["version"]==2,"raw descriptor/lifecycle changed")
   validate_records(call["records"],d["runId"],call["guardianPid"])
   need(call["controlComplete"] is True and call["cleanup"]["confirmed"] is True,"collector completion missing")
   journal=[json.loads(line) for line in (path/"lifecycle.jsonl").read_text().splitlines()]
   need(journal==call["records"],"live journal differs from terminal receipt")
   live=read(path/"live.json")
   need(live["phase"]=="complete" and live["registrationKnown"] is True and live["cleanup"]["confirmed"] is True,"live terminal state invalid")
   need(d["argv"][0]==str(native),"payload executable changed")
   need(Path(d["workspace"]) not in state.parents and state not in Path(d["workspace"]).parents and Path(d["workspace"])!=state,"protected state writable")
   for p,h in d["bindings"].items():need(sha(p)==h,"payload/controller binding changed")
   item=d["inspection"]
   if name=="locked-jobs":
    need(item=={"kind":primitive.LOCK_KIND,"driverLock":str(state/"driver.lock"),"lockIdentity":value["lockIdentity"]},"exact lock grant changed")
   else:need(item=={"kind":primitive.STRICT_KIND,"driverLock":None,"lockIdentity":None},"read-only grant changed")
   raw=(path/"stdout").read_bytes();err=(path/"stderr").read_bytes()
   need(len(raw)<=1048576 and len(err)<=65536,"output budget changed")
   output=json.loads(raw);role=d["argv"][1];roles.append(role)
   if role=="engine":need(output==package["engine"],"engine mismatch")
   elif role=="project-build-input-key":need(output["status"]=="observed-project-build-inputs" and output["commandsExecuted"] is False and output["inputKey"]==expected_key,"input observation mismatch")
   elif role=="project-build":
    need("--force" not in d["argv"] and output=={"status":"unchanged-project-build","inputKey":expected_key,"verification":"not-repeated","cacheHits":0,"activation":"not-performed"},"unchanged build not established")
   else:raise RuntimeError("unexpected command")
   for row in call["records"]:pids.update(row[k] for k in ["guardianPid","parentPid","pid"] if k in row)
 need(roles==["engine","project-build-input-key","project-build"],"command order changed")
 observed=read(work/"observed-live.json")
 need(observed["snapshot"]["phase"]=="payload-started" and observed["snapshot"]["registrationKnown"] is True
      and observed["snapshot"]["acceptedRecordCount"]==2
      and observed["currentKernelIdentity"]==observed["snapshot"]["nativeIdentity"],"real live identity not observed")
 observed_path=Path(observed["descriptor"])
 need(sha(observed_path)==observed["descriptorDigest"] and read(observed_path)["argv"][1] in ["project-build-input-key","project-build"],"observed descriptor mismatch")
 process=read(work/"control/process.json");pids.update([process["monitorPid"],process["guardPid"]])
 for pid in sorted(pids):
  ps=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
  need(ps.returncode!=0 or not ps.stdout.strip() or ps.stdout.strip().startswith("Z"),"observed process live:"+str(pid))
 status=json.loads(subprocess.check_output(["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs","status"]))
 req_id=re.search(r"Build reservation queued: ([0-9a-f-]{36})",(work/"control/guard.stderr").read_text()).group(1)
 req=next(x for x in status["requests"] if x["id"]==req_id)
 need(req["state"]=="finished" and req["leaseReleaseCompleted"] is True,"reservation not released")
 need(status["mode"]=="exclusive-fallback" and status["parallelActivated"] is False,"execution policy changed")
 receipt=dict(status="passed-independent-real-live-unchanged-review",nativeCliDigest=sha(native),
  sourceBindings=gate["sourceBindings"],sourceProducerCommit=gate["sourceProducerCommit"],
  liveLifecycleObserved=True,liveJournalMatchesTerminal=True,nativeCallsPassed=3,nativeUnchangedBuildInvocations=1,applicationCommandsExecuted=0,
  originalApplicationAttempts=1,newApplicationAttempts=0,protectedStateUnchanged=True,driverLockUnchanged=True,
  lockedProfileDigest=kernel_gate["lockedProfileDigest"],observedProcessesStopped=len(pids),reservationId=req_id,
  reservationReleased=True,realUnchangedBuildQualified=True,automaticReservationReleaseQualified=False,
  installedSupervisorChanged=False,actualOwnerWatchRetried=False,parallelActivated=False,
  coordinatorDigest=sha(work/"run.py"),reviewerDigest=sha(__file__))
 (work/"independent-review.json").write_text(json.dumps(receipt,indent=2)+"\n");print(json.dumps(receipt))
if __name__=="__main__":main()
