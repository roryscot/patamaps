"""Review live-ownership controls, retained failures and observed process lifetimes."""
from pathlib import Path
import argparse,ast,hashlib,json,re,subprocess,sys
def need(ok,why):
 if not ok:raise RuntimeError(why)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);args=p.parse_args()
 root=args.root.resolve();work=root/".tools/native-live-ownership-20261028"
 initial=work/"attempt-0";latest=work/"live-supplement"
 read=lambda p:json.loads(p.read_text())
 first=read(initial/"receipt.json");last=read(latest/"receipt.json")
 need(first["status"]=="passed-live-ownership-controls" and last["status"]=="passed-live-survivor-supplement","controls did not pass")
 need(read(work/"control/exit.json")["exitCode"]==0 and read(work/"control-supplement/exit.json")["exitCode"]==0,"canonical guard failed")
 expected=last["sourceBindings"];before=first["sourceBindings"]
 changed={n for n in expected if expected[n]!=before[n]}
 need(changed=={"scripts/test_live_native_inspection.py"},"production changed between controls")
 for n,h in expected.items():need(sha(root/n)==sha(latest/Path(n).name)==h,"current/supplement source changed")
 for n,h in before.items():need(sha(initial/Path(n).name)==h,"initial execution source changed")
 def methods(path):
  tree=ast.parse(path.read_text());c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="LiveOwnership")
  return {n.name:ast.dump(n,include_attributes=False) for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
 old,new=methods(initial/"test_live_native_inspection.py"),methods(latest/"test_live_native_inspection.py")
 need(set(new)-set(old)=={"test_pending_launch_with_unregistered_survivor_stays_uncertain"} and all(new[k]==v for k,v in old.items()),"existing live controls changed")
 for base,role,count in [(initial,"live",14),(initial,"legacy",10),(initial,"strict",15),(initial,"watch",11),(latest,"live",15)]:
  text=(base/(role+".stderr")).read_text()
  need(re.search(r"Ran "+str(count)+r" tests in ",text) and text.rstrip().endswith("OK")
       and len(re.findall(r"^test_.* \.\.\. ok$",text,re.M))==count,"suite transcript incomplete")
 sys.path.insert(0,str(root/"scripts"))
 import native_inspection_guard as lib
 pids=set();identities={}
 def collect(value):
  if isinstance(value,dict):
   for key,item in value.items():
    if key in {"pid","guardianPid","parentPid","controllerPid","monitorPid","guardPid"} and type(item) is int and item>1:pids.add(item)
    if key in {"nativeIdentity","guardianIdentity","identity"} and isinstance(item,dict) and "startMicroseconds" in item:
     identities[item["pid"]]=item
    collect(item)
  elif isinstance(value,list):
   for item in value:collect(item)
 live_roots=list(latest.glob("live-ownership-*"));need(len(live_roots)==1,"live fixture set changed")
 fixture=live_roots[0]
 for case in fixture.iterdir():
  result=case/"result.json"
  if result.exists():collect(read(result))
  for path in case.glob("jobs/*/live.json"):collect(read(path))
  for path in case.glob("jobs/*/control.json"):
   item=read(path);need(item["automaticReservationReleaseQualified"] is False,"release claim changed")
   collect(item)
  for raw in case.glob("jobs/*/control.raw"):need(raw.stat().st_size<=3*lib.MAX_RECORD_BYTES,"control data bound exceeded")
 observed_names=["test_records_visible_before_worker_exit","test_early_stdout_close_does_not_finish_ownership",
  "test_guardian_sigkill_stops_registered_native","test_outer_pipe_is_live_and_not_inherited",
  "test_outer_socketpair_is_live_and_not_inherited","test_observer_loss_after_registration_refuses"]
 for name in observed_names:
  v=read(fixture/name/"observed-live.json");collect(v)
  need(v["phase"]=="payload-started" and v["registrationKnown"] is True and v["acceptedRecordCount"]==2,"live registration missing")
  n,g=v["nativeIdentity"],v["guardianIdentity"]
  need(n["parentPid"]==g["pid"] and n["pgid"]==n["pid"] and g["parentPid"]==v["controllerPid"],"kernel relationship mismatch")
  need(all(type(x["startSeconds"]) is int and x["startSeconds"]>0 and type(x["startMicroseconds"]) is int and 0<=x["startMicroseconds"]<1000000 for x in [n,g]),"kernel start identity missing")
 killed=read(fixture/"test_guardian_sigkill_stops_registered_native/result.json")
 need(killed["ok"] is False and killed["calls"][0]["guardianExitCode"]==-9 and killed["calls"][0]["cleanup"]["confirmed"] is True and killed["calls"][0]["controlComplete"] is False,"guardian crash promoted or leaked")
 pending=read(fixture/"test_pending_launch_sigkill_stays_unsealed/result.json")
 need(pending["ok"] is False and pending["calls"][0]["cleanup"]["confirmed"] is False,"unsealed launch promoted")
 survivor=read(fixture/"test_pending_launch_with_unregistered_survivor_stays_uncertain/unregistered-survivor.json")
 collect(survivor);survived=read(fixture/"test_pending_launch_with_unregistered_survivor_stays_uncertain/result.json")
 need(survivor["workerSurvivedRefusal"] is True and survivor["unconfirmedOwnershipPreserved"] is True
      and survived["ok"] is False and survived["calls"][0]["cleanup"]["confirmed"] is False,"unregistered survivor falsely confirmed")
 mismatch=read(fixture/"test_kernel_identity_mismatch_never_signals/identity-refusal.json");collect(mismatch)
 need(mismatch["refused"] is True and mismatch["forged"]["startMicroseconds"]!=mismatch["identity"]["startMicroseconds"],"identity refusal absent")
 for transport in ["pipe","socketpair"]:
  case=fixture/("test_outer_"+transport+"_is_live_and_not_inherited")
  frames=read(case/"observer.json");result=read(case/"result.json")
  need([v["event"] for v in frames]==["guardian-launch-pending","guardian-started","guardian-record","guardian-record","guardian-record","inspection-finished"]
       and [v["sequence"] for v in frames]==list(range(6)),"observer ordering changed")
  need(result["ok"] is True and json.loads(result["stdout"])["extraDescriptorsClosed"] is True,"observer inherited by native")
  collect(frames)
 broken=list((fixture/"test_broken_observer_refuses_before_spawn/jobs").glob("*/control.json"))
 need(len(broken)==1 and read(broken[0])["guardianPid"] is None and read(broken[0])["controlComplete"] is False,"broken observer launched work")
 for base in [initial,latest]:
  for path in base.glob("**/control.json"):collect(read(path))
  for path in base.glob("**/live.json"):collect(read(path))
  for path in base.glob("**/control-records.json"):collect(read(path))
  for path in base.glob("**/observed-live.json"):collect(read(path))
 for c in ["control","control-supplement"]:collect(read(work/c/"process.json"))
 for pid in sorted(pids):
  if pid in identities:
   need(not lib.same_process(identities[pid],lib.process_identity(pid)),"owned identity still alive:"+str(pid))
  else:
   ps=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
   need(ps.returncode!=0 or not ps.stdout.strip() or ps.stdout.strip().startswith("Z"),"observed process still alive:"+str(pid))
 provenance=read(work/"supervisor-provenance.json")
 need(sha(provenance["installedGuard"])==provenance["installedGuardSha256"],"installed guard changed")
 status=json.loads(subprocess.check_output(["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs","status"]))
 requests=[]
 for c in ["control","control-supplement"]:
  req_id=re.search(r"Build reservation queued: ([0-9a-f-]{36})",(work/c/"guard.stderr").read_text()).group(1)
  req=next(x for x in status["requests"] if x["id"]==req_id)
  need(req["state"]=="finished" and req["leaseReleaseCompleted"] is True,"reservation not released")
  requests.append(req_id)
 need(status["mode"]=="exclusive-fallback" and status["parallelActivated"] is False,"global mode changed")
 receipt=dict(status="passed-independent-live-ownership-controls",sourceBindings=expected,
  liveControls=15,legacyGuardianControls=10,strictGuardianControls=15,watchPolicyControls=11,
  initialControlsPassed=50,latestTotalControls=51,productionRepairsUsed=0,qualificationRepairsUsed=1,
  liveBeforeExitSnapshots=6,guardianCrashRegisteredCleanupPassed=True,
  unregisteredSurvivorRemainedUnconfirmed=True,unregisteredFixtureStoppedByHarness=True,
  observerPipeAndSocketPairPassed=True,observedProcessInstancesStopped=len(pids),
  reservationIds=requests,reservationsReleased=True,installedGuardDigest=provenance["installedGuardSha256"],
  automaticReservationReleaseQualified=False,installedSupervisorChanged=False,
  runtimeRegistryQualified=False,actualOwnerWatchRetried=False,parallelActivated=False,reviewerDigest=sha(__file__))
 (work/"independent-review.json").write_text(json.dumps(receipt,indent=2)+"\n")
 (work/"CONTROL_QUALIFIED.json").write_text(json.dumps(receipt,indent=2)+"\n")
 print(json.dumps(receipt))
if __name__=="__main__":main()
