"""Review actual retained-owner read-only commands through the proposed guardian."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
def need(ok,why):
 if not ok:raise RuntimeError(why)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--root",required=True,type=Path);args=parser.parse_args()
 root=args.root.resolve();work=root/".tools/native-inspection-guardian-20261028/core-compatibility-repair-1"
 sys.path.insert(0,str(root/"scripts"))
 from native_inspection_guard import validate_records
 read=lambda p:json.loads(p.read_text())
 value=read(work/"receipt.json");need(value["status"]=="passed-real-readonly-guardian-compatibility","compatibility did not pass")
 need(read(work/"control/exit.json")["exitCode"]==0,"canonical guard failed")
 need(value.get("controlledParserEnvironmentRestored") is True,"fixture environment not restored")
 initial=read(work.parent/"core-compatibility/receipt.json")
 need(initial["status"]=="failed-real-readonly-guardian-compatibility" and initial["calls"]==[]
      and initial["failureType"]=="SystemExit" and initial["failure"]=="2","initial fixture refusal changed")
 for name,h in read(work/"source-bindings.json").items():need(sha(root/name)==h,"source binding changed")
 need(value["coordinatorDigest"]==sha(work/"run.py"),"coordinator changed")
 need(value["applicationBuildsRun"]==0 and value["newApplicationAttempts"]==0 and value["actualOwnerWatchRun"] is False,"scope changed")
 package=read(root/".tools/installed-watch-policy-20261028/receipt.json")
 native=Path(package["installedNative"])/"bin/patamaps"
 need(value["nativeCliDigest"]==sha(native)=="cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355","native changed")
 origin=root/".tools/installed-original-owner-next-20261027/owner-native"
 state=Path(read(origin/"receipt.json")["state"])
 selected=read(state/"selected.json")
 expected_key="sha256:b1d1c79a5f81832e0d01029e4f446b3ffcdacbbc1b60f9920ec304c877e3ffdc"
 need(selected["inputKey"]==expected_key,"selected input changed")
 attempt=state/selected["attempt"]
 protected={state/"selected.json":"14b7cca4fb50330d7827c51327899969416aad31a3e70ce1e6d3994169282352",
 attempt/"artifacts.json":"96e70d1cfd993e38051ca24fde1fc384b9e91bd2a362bd331e87cbf4b1c4776d",
 attempt/"candidate/patamaps-native-tooling/trace.jsonl":"fbcaa4574fca00367f326c6a699b1899e6684c567ae6171b17e154b256429951"}
 need({str(p):h for p,h in protected.items()}==value["statePreimages"],"accepted preimages changed")
 for p,h in protected.items():need(sha(p)==h,"protected file changed")
 need(sorted(p.name for p in (state/"attempts").iterdir())==value["originalAttempts"]==["1793122875791456000-6699"],"attempt set changed")
 calls=value["calls"];need(len(calls)==3,"actual call set changed")
 descriptors={read(p/"control.json")["guardianPid"]:p for p in (work/"jobs").iterdir()}
 roles=[];pids=set()
 for call in calls:
  need(call["guardianExitCode"]==0 and call["automaticReservationReleaseQualified"] is False,"guardian failure or release claim")
  path=descriptors[call["guardianPid"]];d=read(path/"descriptor.json")
  rows=call["records"];validate_records(rows,d["runId"],call["guardianPid"])
  need(read(path/"control.json")==call,"raw control record differs")
  need(d["argv"][0]==str(native),"unexpected payload executable")
  need(Path(d["workspace"]) not in state.parents and state not in Path(d["workspace"]).parents and state!=Path(d["workspace"]),"protected state writable")
  for name,h in d["bindings"].items():need(sha(name)==h,"execution binding changed")
  raw=(path/"stdout").read_bytes();err=(path/"stderr").read_bytes()
  need(len(raw)<=1048576 and len(err)<=65536,"output bound changed")
  output=json.loads(raw);role=d["argv"][1];roles.append(role)
  if role=="engine":need(output==package["engine"],"engine mismatch")
  elif role=="project-build-verify":need(output["status"]=="verified-selected-build-bindings" and output["inputKey"]==expected_key,"selected verification mismatch")
  elif role=="project-build-input-key":need(output["status"]=="observed-project-build-inputs" and output["commandsExecuted"] is False and output["inputKey"]==expected_key,"input observation mismatch")
  else:raise RuntimeError("unexpected command")
  for row in rows:pids.update(row[k] for k in ["guardianPid","parentPid","pid"] if k in row)
 need(roles==["engine","project-build-verify","project-build-input-key"],"command order changed")
 verification=json.loads((work/"verification.stdout").read_text())
 need(verification["status"]=="verified-project-watch-selection" and verification["inputKey"]==expected_key,"watcher verification mismatch")
 controls=value["legacyGuardianControls"]
 need([x["control"] for x in controls]==["runner-death","exits","inspection-budget"] and all(x["result"]=="passed" for x in controls),"legacy guardian regressions failed")
 legacy=read(work/"legacy-runner-death/receipt.json")
 for k in ["runner","innerGuard","tool","sleep"]:pids.add(legacy[k])
 process=read(work/"control/process.json");pids.update([process["monitorPid"],process["guardPid"]])
 for pid in sorted(pids):
  ps=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
  need(ps.returncode!=0 or not ps.stdout.strip() or ps.stdout.strip().startswith("Z"),"observed process live:"+str(pid))
 status=json.loads(subprocess.check_output(["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs","status"]))
 request_id=re.search(r"Build reservation queued: ([0-9a-f-]{36})",(work/"control/guard.stderr").read_text()).group(1)
 request=next(x for x in status["requests"] if x["id"]==request_id)
 need(request["state"]=="finished" and request["leaseReleaseCompleted"] is True,"reservation not released")
 need(status["parallelActivated"] is False and status["mode"]=="exclusive-fallback","policy changed")
 receipt=dict(status="passed-independent-real-readonly-guardian-review",nativeCallsPassed=3,commandRoles=roles,
  protectedStateUnchanged=True,originalApplicationAttempts=1,newApplicationAttempts=0,applicationBuildsRun=0,
  legacyGuardianControlSets=controls,observedProcessesStopped=len(pids),reservationId=request_id,reservationReleased=True,
  qualificationFixtureEnvironmentRestored=True,incrementRepairsUsed=2,initialCompatibilityFixturePassed=False,
  nativeCliDigest=sha(native),sourceBindings=read(work/"source-bindings.json"),coordinatorDigest=value["coordinatorDigest"],
  automaticReservationReleaseQualified=False,actualOwnerWatchRetried=False,unchangedBuildLockQualified=False,
  installedSupervisorChanged=False,parallelActivated=False,reviewerDigest=sha(__file__))
 (work/"independent-review.json").write_text(json.dumps(receipt,indent=2)+"\n");print(json.dumps(receipt))
if __name__=="__main__":main()
