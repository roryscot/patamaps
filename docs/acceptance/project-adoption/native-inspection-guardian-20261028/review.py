"""Independent retained-artifact review for proposed inspection guardian controls."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,re,subprocess,sys
def need(value,why):
 if not value:raise RuntimeError(why)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);args=p.parse_args()
 root=args.root.resolve();work=root/".tools/native-inspection-guardian-20261028";attempt=work/"attempt-1"
 sys.path.insert(0,str(root/"scripts"))
 from native_inspection_guard import validate_records,OUTPUT_LIMIT
 read=lambda p:json.loads(p.read_text())
 initial=read(work/"attempt-0/receipt.json");result=read(attempt/"receipt.json")
 need(initial["status"]=="failed-proposed-inspection-guardian-controls","initial result changed")
 need(read(work/"control/exit.json")["exitCode"]==1,"initial guard result changed")
 need(result["status"]=="passed-proposed-inspection-guardian-controls","repair controls failed")
 need(read(work/"control-1/exit.json")["exitCode"]==0,"repair guard failed")
 need(result["commands"]==[{"test":"test_native_inspection_guard","exitCode":0},
                          {"test":"test_watch_policy_verification","exitCode":0}],"suite set changed")
 expected=result["sourceBindings"]
 for name,h in expected.items():
  need(sha(root/name)==h and sha(attempt/Path(name).name)==h,"source binding changed")
 for name,count in [("test_native_inspection_guard",10),("test_watch_policy_verification",11)]:
  log=(attempt/(name+".stderr")).read_text()
  need(re.search(r"Ran "+str(count)+r" tests? in ",log) and log.rstrip().endswith("OK"),"test transcript incomplete")
  need(len(re.findall(r"^test_.* \.\.\. ok$",log,re.M))==count,"individual controls missing")
 fixtures=list(attempt.glob("inspection-guardian-*"));need(len(fixtures)==1,"fixture set changed")
 fixture=fixtures[0];pids=set();complete=0;incomplete=0;call_count=0
 for path in sorted(fixture.glob("*/jobs/*/control.json")):
  value=read(path);rows=value["records"];call_count+=1
  descriptor=read(path.parent/"descriptor.json")
  need(value["automaticReservationReleaseQualified"] is False,"release claim changed")
  pids.add(value["guardianPid"])
  for row in rows:
   pids.update(row[k] for k in ["guardianPid","parentPid","pid"] if k in row)
  need((path.parent/"stdout").stat().st_size<=OUTPUT_LIMIT,"output ceiling exceeded")
  if value["guardianExitCode"]==0 or value["guardianExitCode"]==7:
   validate_records(rows,descriptor["runId"],value["guardianPid"]);complete+=1
  else:
   need(value["guardianExitCode"]==75,"unexpected guardian refusal")
   err=(path.parent/"stderr").read_text()
   if len(rows)==2:
    need("timed out" in err,"incomplete proof lacked timeout refusal");incomplete+=1
   else:
    validate_records(rows,descriptor["runId"],value["guardianPid"]);complete+=1
    need("INSPECTION_DATA_OUTPUT_LIMIT" in err,"overflow refusal missing")
 need(call_count==13 and incomplete==1,"adapter call coverage changed")
 direct=list(fixture.glob("*/control-records.json"));need(len(direct)==3,"direct lifecycle records missing")
 for path in direct:
  rows=read(path);validate_records(rows,rows[0]["runId"],rows[0]["guardianPid"]);complete+=1
  for row in rows:
   pids.update(row[k] for k in ["guardianPid","parentPid","pid"] if k in row)
 need(complete==15,"complete lifecycle coverage changed")
 process=read(work/"control-1/process.json");pids.update([process["monitorPid"],process["guardPid"]])
 for pid in sorted(pids):
  status=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
  need(status.returncode!=0 or not status.stdout.strip() or status.stdout.strip().startswith("Z"),
       "observed test process remains live:"+str(pid))
 node="/Users/admin/.nvm/versions/node/v22.23.3/bin/node"
 ctl="/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs"
 status=json.loads(subprocess.check_output([node,ctl,"status"]))
 log=(work/"control-1/guard.stderr").read_text()
 request_id=re.search(r"Build reservation queued: ([0-9a-f-]{36})",log).group(1)
 request=next(v for v in status["requests"] if v["id"]==request_id)
 need(request["state"]=="finished" and request["leaseReleaseCompleted"] is True,"reservation not released")
 need(status["parallelActivated"] is False and status["mode"]=="exclusive-fallback","policy changed")
 receipt=dict(status="passed-independent-proposed-guardian-review",sourceBindings=expected,
  guardianControlsPassed=10,legacyWatcherControlsPassed=11,initialAttemptPassed=False,repairsUsed=1,
  retainedAdapterCalls=call_count,completeLifecycles=complete,incompleteTimeoutLifecycles=incomplete,
  observedTestProcessesStopped=len(pids),reservationId=request_id,reservationReleased=True,
  automaticReservationReleaseQualified=False,installedSupervisorChanged=False,parallelActivated=False,
  actualOwnerWatchRetried=False,unchangedBuildLockQualified=False,reviewerDigest=sha(__file__))
 (work/"independent-review.json").write_text(json.dumps(receipt,indent=2)+"\n")
 print(json.dumps(receipt))
if __name__=="__main__":main()
