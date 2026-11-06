"""Read-only preservation audit after the failed actual-owner watch qualification."""
from pathlib import Path
import argparse,datetime,hashlib,json,re,stat,subprocess
def need(v,m):
 if not v:raise RuntimeError(m)
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return "sha256:"+h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--root",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
 a=p.parse_args();root=a.root;base=root/".tools/original-owner-watch-20261028";w=base/"noop-repair2"
 need(not a.output.exists(),"output exists")
 d=read(w/"receipt.json");f=read(w/"frozen.json")
 need(read(w/"controller-exit.json")["exitCode"]==1 and d["status"]=="failed-actual-owner-noop-watch" and d["failure"]=="WATCH_REFUSED","failure changed")
 need(sha(w/"run.py")==f["driverDigest"]=="sha256:81679cffc71a7cd3a5773b81ef1acb2bc9be9d0ae4a002a425c3b62bf75e0f4b","driver changed")
 for name in ["launch.json","controller-process.json"]:
  pid=read(w/name)["pid"]
  x=subprocess.run(["ps","-p",str(pid),"-o","pid="],capture_output=True,text=True)
  need(x.returncode==1 and not x.stdout.strip(),"test controller still live")
 for path,h in f["inputs"].items():need(sha(Path(path))==h,"bound plan/tool changed")
 origin=root/".tools/installed-original-owner-next-20261027/owner-native"
 state=Path(read(origin/"receipt.json")["state"]);selected=read(state/"selected.json");attempt=state/selected["attempt"]
 need(sha(state/"selected.json")==d["selectedPointerDigest"] and sorted(x.name for x in (state/"attempts").iterdir())==d["originalAttempts"] and len(d["originalAttempts"])==1,"selected state changed")
 need(sha(attempt/"artifacts.json")==d["artifactManifestDigest"] and sha(attempt/"candidate/patamaps-native-tooling/trace.jsonl")==d["nativeLedgerDigest"],"artifact/ledger manifest changed")
 count=0
 for name,item in read(attempt/"artifacts.json").items():
  q=attempt/"candidate"/name;s=q.lstat()
  need(stat.S_IMODE(s.st_mode)==item["mode"],"artifact mode")
  if item["kind"]=="file":
   need(stat.S_ISREG(s.st_mode) and s.st_size==item["bytes"] and sha(q)==item["digest"],"artifact bytes");count+=1
  else:need(item["kind"]=="directory" and stat.S_ISDIR(s.st_mode),"artifact directory")
 need(count==2482,"artifact file count")
 fixture=read(root/".tools/installed-original-owner-next-20261027/owner-fixture.json")
 for name,h in fixture["sourceInputs"].items():need(sha(origin/"owner"/name)==h,"owner source changed")
 for name,h in fixture["expectedGenerated"].items():need(sha(Path(fixture["originalOracle"])/name)==h,"original oracle changed")
 source=Path(d["installedSource"]);need(sha(source/"source-inventory.json")==f["sourceInventoryDigest"],"source inventory changed")
 entries=read(source/"source-inventory.json")
 need(len(entries)==1255,"installed source count")
 actual={p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
 need(actual=={x["path"] for x in entries}|{"source-inventory.json"} and not any(p.is_symlink() for p in source.rglob("*")),"source members changed")
 for x in entries:need((source/x["path"]).stat().st_size==x["bytes"] and sha(source/x["path"])==x["digest"],"installed source bytes")
 need(sha(Path(d["installedCompiler"]))==f["cliDigest"],"CLI changed")
 node="/Users/admin/.nvm/versions/node/v22.23.3/bin/node";ctl="/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs"
 status=json.loads(subprocess.check_output([node,ctl,"status"],text=True,timeout=20));requests={r["id"]:r for r in status["requests"]}
 ids=d["reservationIds"];need(len(ids)==2 and [d["nativeProofs"][i]["command"] for i in ids]==["project-build","project-build-verify"],"actual reserved native proof")
 for i in ids:
  x=d["nativeProofs"][i];need(x["ownerVerifiedAncestor"] and x["compatibilityLeaseMatched"] and x["enforcement"]=="native-exclusive" and x["limits"]["diskBytes"]==4000000000,"native resource proof")
 need(requests[ids[0]]["state"]=="finished" and requests[ids[0]]["leaseReleaseCompleted"],"initial no-op reservation not released")
 req=requests[ids[1]];need(req["state"]=="needs-review" and req["ownershipSealed"] and req["ownerAlive"] is False and req["processGroup"]==47194 and req["containerIds"]==[],"retained recovery scope")
 stop=read(w/"native-stop-observations.json")
 need(stop["status"]=="passed-readonly-sealed-native-stop-review" and stop["canonicalConfirmedStopped"] and len(stop["observations"])==3,"stop review missing")
 for x in stop["observations"]:need(x["recordedGroupAbsent"] and all(x[k]==0 for k in ["tokenProcessCount","projectCommandProcessCount","openProjectFileProcessCount","unknownOpenFileProcessCount","matchingContainerCount"]),"stop review uncertainty")
 proposal=base/"sealed-native-recovery-proposal";pre=read(proposal/"preflight-result.json")
 need(pre["status"]=="passed-readonly-recovery-preflight" and pre["leaseReleased"] is False and not (proposal/"APPROVAL.json").exists(),"recovery not pending")
 active=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds/active-run");g=read(active/"retained-run.json")
 need(g["completed"] is False and g["exitCode"]==75 and g["existingContainerUncertainty"] is True and g["newSurvivingContainers"]==[],"guard failure changed")
 drop=g["freeBytesAtStart"]-g["minimumFreeBytesObserved"];need(drop>4000000000,"growth failure not supported")
 stderr=(w/"watch.stderr").read_text();need("disk-growth budget was exceeded" in stderr,"growth reason missing")
 dec=json.JSONDecoder();events=[]
 for match in re.finditer(r"(?m)^\{",(w/"watch.stdout").read_text()):
  try:v,_=dec.raw_decode((w/"watch.stdout").read_text()[match.start():])
  except ValueError:continue
  if isinstance(v,dict):events.append(v)
 need(any(x.get("status")=="unchanged-project-build" and x["inputKey"]==selected["inputKey"] and x["cacheHits"]==0 for x in events),"actual native no-op missing")
 need(any(x.get("reason")=="WATCH_POLICY_VERIFICATION_REFUSED: 75" for x in events),"verification refusal missing")
 for stage in ["noop","noop-repair1"]:
  need(read(base/stage/"controller-exit.json")["exitCode"]==1,"earlier failure missing")
  proof=read(base/stage/"recovery-review.json");need(proof["leaseReleaseCompleted"] and len(proof["observations"])==3,"earlier recovery missing")
 need((base/"parent-death-prepared/NOT_LAUNCHED.json").exists() and not (base/"parent-death-prepared/launch.json").exists(),"parent case launched")
 result=dict(status="passed-failure-preservation-review",reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewerDigest=sha(Path(__file__)),producerRevision=f["producerRevision"],qualificationStatus="failed",attemptsObserved=3,initialObserverFailures=2,lastFailure="verification-policy-exit75-disk-growth-and-conservative-container-uncertainty",nativeNoopCompleted=True,nativeBuildAndVerificationObservedUnderSeparateExclusiveReservations=True,verificationCompleted=False,completedWatchUpdate=False,idleAndSigtermAccepted=False,retainedReservationId=ids[1],recoveryApprovalPending=True,guardRecordDigest=sha(active/"retained-run.json"),minimumFreeSpaceDropBytes=drop,freeSpaceDropAtEndBytes=g["freeBytesAtStart"]-g["freeBytesAtEnd"],growthAttribution="volume-free-space delta; actual writer not established",oldPointerAttemptsAndLedgerUnchanged=True,artifactsRehashed=count,ownerSourceInputsRehashed=len(fixture["sourceInputs"]),oracleOutputsRehashed=len(fixture["expectedGenerated"]),installedSourceFilesRehashed=1255,installedSourceInventoryDigest=f["sourceInventoryDigest"],compilerDigest=f["cliDigest"],parentDeathCaseLaunched=False,repairBudgetExhausted=True,watchQualificationAccepted=False,goalComplete=False,filesDeleted=0,policyChanged=False,parallelActivated=status["parallelActivated"])
 a.output.write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
if __name__=="__main__":main()
