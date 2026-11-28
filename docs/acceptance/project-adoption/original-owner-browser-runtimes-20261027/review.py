"""Audit pinned native browser acquisition and scoped ownership controls."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,platform,re,stat,subprocess
EXPECTED={
 "acquisition/acquire.py":"sha256:36a14be218138f7d982efb9200b6d99a13d4efc08f2169d0dd521e74ef3aa4ea",
 "launch/run.py":"sha256:61ffe8ed4440fb312eb7484491b00532c716d4ed8b88e2f7eb335cefbfc30b8b",
 "launch-repair1/run.py":"sha256:f05f0880dcfc118c8bf82050220da680f6febb1a2b49c1e3fa917d5f253d61d4",
 "owned_browser_guard.py":"sha256:f72aa2391eacbdf77f2905707f8715857833c5bbc2a638efbbbc151219163ed8",
 "launch-one.cjs":"sha256:cd58b1074f8f1d382b22ccec12dca61db95e9464fa966ba498122d9a0ac8d6bf",
}
def need(value,message):
 if not value:raise RuntimeError(message)
def read(p):return json.loads(p.read_text())
def sha(p):return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
def absent(pid):
 p=subprocess.run(["/bin/ps","-p",str(pid),"-o","pid="],capture_output=True,text=True,timeout=5)
 return p.returncode==1 and not p.stdout.strip()
def group_absent(group):
 try:os.killpg(group,0);return False
 except ProcessLookupError:return True
def inventory(base):
 result=[]
 for p in sorted(base.rglob("*")):
  info=p.lstat();v={"path":p.relative_to(base).as_posix(),"mode":stat.S_IMODE(info.st_mode)}
  if p.is_symlink():v.update(kind="symlink",target=os.readlink(p))
  elif p.is_dir():v.update(kind="directory")
  elif p.is_file():v.update(kind="file",bytes=info.st_size,digest=sha(p))
  else:raise RuntimeError("unexpected cache special file")
  result.append(v)
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for n in ["base","node","buildctl","output"]:parser.add_argument("--"+n,type=Path,required=True)
 args=parser.parse_args();base=args.base.resolve()
 need(not args.output.exists(),"review output exists")
 a,l,p=base/"acquisition",base/"launch",base/"launch-repair1"
 ac,lc,pc=[read(x/"frozen.json") for x in [a,l,p]]
 ar,lr,pr=[read(x/"receipt.json") for x in [a,l,p]]
 need(ar["status"]=="passed-pinned-browser-runtime-acquisition","acquisition not passed")
 need(lr["status"]=="failed-native-browser-controls" and lr["failure"]=="Crash recovery did not stop surviving owned browser","initial failure changed")
 need(pr["status"]=="passed-native-browser-survivor-and-ownership-repair" and pr["controlsPassed"]==2,"partial repair not passed")
 for rel,digest in EXPECTED.items():
  paths=[base/rel] if "/" in rel else [l/rel,p/rel]
  for path in paths:need(sha(path)==digest,"frozen runner changed")
 need(lc["inputs"]==pc["inputs"]==ac["inputs"] and len(ac["inputs"])==13,"dependency bindings changed")
 for item in ac["inputs"]:need(sha(Path(item["path"]))==item["digest"],"bound source/config/dependency changed")
 need(ac["producerRevision"]=="c90d60e76b2fa2243329b5d14f04739722e340c7" and ac["ownerRevision"]=="c61d51a57120abbbca65d4cb4a432c1cef9343bb","source revisions")
 owner=Path(ac["owner"])
 need(subprocess.check_output(["git","rev-parse","HEAD"],cwd=owner,text=True).strip()==ac["ownerRevision"],"owner revision changed")
 need(subprocess.check_output(["git","status","--porcelain=v1","-z"],cwd=owner)==b"","owner changed")
 need(read(Path(ac["core"])/"package.json")["version"]=="1.56.1","Playwright version")
 need(subprocess.check_output([str(args.node),"--version"],text=True).strip()=="v22.23.3","Node version")
 status=json.loads(subprocess.check_output([str(args.node),str(args.buildctl),"status"],text=True,timeout=15))
 need(status["parallelActivated"] is False and status["legacyLease"] is None and status["transactionBlocked"] is False,"scheduler not finalized")
 requests={r["id"]:r for r in status["requests"]}
 stage_records=[]
 previous_end=None
 for directory,code in [(a,0),(l,1),(p,0)]:
  end=read(directory/"supervisor-exit.json")
  need(end["exitCode"]==code,"stage terminal status")
  start=read(directory/"launch.json")["startedAtUtc"]
  if previous_end:need(datetime.datetime.fromisoformat(start)>=datetime.datetime.fromisoformat(previous_end),"stages overlapped")
  previous_end=end["finishedAtUtc"]
  for n in ["launch.json","supervisor.json"]:need(absent(read(directory/n)["pid"]),"stage owner still present")
  rid=re.search(r"Build reservation queued: ([0-9a-f-]{36});",(directory/"supervisor.stderr").read_text()).group(1)
  request=requests[rid]
  need(request["state"]=="finished" and request["leaseReleaseCompleted"] is True,"reservation not released")
  need(request["enforcement"]=="native-exclusive" and request["limits"]["diskBytes"]==4000000000,"exclusive reservation changed")
  guard_path=Path(re.search(r"^Storage guard record: (.+)$",(directory/"supervisor.stdout").read_text(),re.M).group(1))
  guard=read(guard_path)
  need(guard["exitCode"]==code and guard["filesDeleted"]==0,"guard status/deletion mismatch")
  need(not guard.get("newSurvivingContainers") and not guard.get("existingContainerUncertainty"),"container uncertainty")
  stage_records.append({"phase":directory.name,"exitCode":code,"reservationId":rid,"reservationFinishedAndReleased":True,"privateReceiptDigest":sha(directory/"receipt.json"),"guardRecordDigest":sha(guard_path)})
 need(len({s["reservationId"] for s in stage_records})==3,"follow-up reservation reused")
 need(ar["applicationDependenciesInstalled"]==0 and ar["browsersLaunched"]==0 and ar["apiImportsRun"] is False,"acquisition scope")
 installer=ar["commands"][0]["measurement"]
 need(installer["exitCode"]==0 and installer["measurementStatus"]=="completed" and absent(installer["pid"]),"installer not complete")
 need(installer["argv"][-5:]==["install","--only-shell","chromium","firefox","webkit"],"installer targets changed")
 for stream in ["stdout","stderr"]:need(sha(a/("install."+stream))==installer[stream+"Digest"],"installer log changed")
 before=read(a/"cache-inventory.json");after=read(p/"cache-inventory-after.json")
 need(sha(a/"cache-inventory.json")==ar["cacheInventoryDigest"]==lc["cacheInventoryDigest"]==pc["cacheInventoryDigest"],"acquired inventory changed")
 need(sha(p/"cache-inventory-after.json")==pr["cacheInventoryAfterDigest"],"post inventory changed")
 cache=a/"browsers"
 need(inventory(cache)==after,"current cache differs from reviewed post state")
 old={v["path"]:v for v in before};new={v["path"]:v for v in after}
 need(all(new.get(k)==v for k,v in old.items()),"browser runtime payload mutated")
 additions=set(new)-set(old);allowed={n+"/DEPENDENCIES_VALIDATED" for n in ac["requiredCacheDirectories"]}
 need(additions<=allowed and all(new[k].get("kind")=="file" and new[k].get("bytes")==0 for k in additions),"unexpected cache additions")
 need(len([v for v in before if v["kind"]=="file"])==ar["cacheFiles"]==6782,"cache file count")
 need(ar["cacheAllocatedBytes"]<=ac["bounds"]["maximumCacheAllocatedBytes"]==2000000000,"cache budget")
 need(ar["existingCachesTargeted"] is False and not ar["defaultBrowserCacheExistedBefore"] and not ar["defaultBrowserCacheExistsAfter"],"existing cache scope")
 roots={v["path"].split("/")[0] for v in after if not v["path"].startswith(".")}
 need(roots==set(ac["requiredCacheDirectories"]),"browser revisions")
 versions={};observed_instances=0;accepted=[]
 for directory,receipt,names in [
  (l,lr,["chromium-normal","firefox-normal","webkit-normal","chromium-sigterm","chromium-sigkill"]),
  (p,pr,["chromium-sigkill"]),
 ]:
  entries={v["name"]:v for v in receipt["controls"]}
  for name in names:
   case=directory/name;entry=entries[name];own=read(case/"ownership.json");ready=read(case/"ready.json");guarded=read(case/"guard-result.json")
   case_cfg=read(case/"config.json")
   need(own["ownerToken"]==case_cfg["ownerToken"] and re.fullmatch("[0-9a-f]{32}",case_cfg["ownerToken"]) is not None,"private ownership binding")
   need(own["browserGroup"]==own["browserPid"] and own["serverLoopback"] is True,"browser group/loopback")
   need(absent(own["browserPid"]) and absent(own["nodePid"]) and group_absent(own["browserGroup"]),"browser/owner group survived")
   need(guarded["status"]=="stopped-owned-browser-groups" and guarded["ownershipUncertain"] is False and all(g["stopped"] for g in guarded["groups"]),"guardian cleanup incomplete")
   need(all(ready[k] is True for k in ["domPassed","javascriptPassed","offline"]),"browser readiness")
   need(re.fullmatch("[0-9.]+",ready["version"]) is not None,"unexpected runtime version")
   need(set(case_cfg["env"])=={"PATH","HOME","TMPDIR","LANG","TZ","PLAYWRIGHT_BROWSERS_PATH","PLAYWRIGHT_SKIP_BROWSER_GC","PATAMAPS_BROWSER_OWNER","DEBUG"},"unexpected browser environment inputs")
   need(Path(case_cfg["env"]["HOME"]).is_relative_to(case) and Path(case_cfg["env"]["TMPDIR"]).is_relative_to(case),"browser profile scope")
   need(Path(own["spawnfile"]).is_relative_to(cache),"browser executable scope")
   m=entry["measurement"];expected=0 if name.endswith("-normal") else 130 if name.endswith("-sigterm") else 137
   need(m["exitCode"]==expected and m["measurementStatus"]=="completed" and absent(m["pid"]),"browser command terminal state")
   for stream in ["stdout","stderr"]:need(sha(case/("node."+stream))==m[stream+"Digest"],"browser log changed")
   if name.endswith("-normal"):
    result=read(case/"result.json")
    need(result["status"]=="passed" and result["serverClosed"] and result["browserExitObserved"],"normal close failed")
    versions[entry["engine"]]=ready["version"];accepted.append(name)
   elif name.endswith("-sigterm"):
    result=read(case/"result.json")
    need(result["status"]=="cancelled" and result["serverClosed"] and read(case/"signal.json")["signal"]=="SIGTERM","cancellation")
    accepted.append(name)
   elif directory==l:
    need(guarded["signals"]==[] and all(g["action"]=="already-stopped" for g in guarded["groups"]),"initial auto-exit observation changed")
   else:
    survivor=read(case/"survivor-precondition.json")
    need(survivor["stoppedBeforeOwnerKill"] and "T" in survivor["observedState"] and survivor["browserPid"]==own["browserPid"],"survivor fixture not witnessed")
    need(read(case/"signal.json")["signal"]=="SIGKILL" and read(case/"signal.json")["browserObservedLive"],"owner hard crash not witnessed")
    need(guarded["signals"] and all(g.get("identityProved") is True and g["action"]=="stopped-owned-group" for g in guarded["groups"]),"survivor recovery not proved")
    accepted.append("stopped-browser-survivor-recovery")
   observed_instances+=1
 case=p/"foreign-token-refusal";foreign=next(c for c in pr["controls"] if c["name"]=="foreign-token-refusal")
 need(foreign["fixtureStillAliveAfterRefusal"] and foreign["ownedFixtureReaped"] and absent(foreign["fixturePid"]),"negative fixture proof")
 refused=read(case/"guard-result.json")
 need(refused["status"]=="refused-or-failed-browser-cleanup" and refused["failure"]=="BROWSER_OWNERSHIP_UNPROVEN" and refused["signals"]==[],"wrong token did not refuse before effects")
 accepted.append("foreign-token-refusal")
 need(len(accepted)==6 and set(versions)=={"chromium","firefox","webkit"} and observed_instances==6,"aggregate control scope")
 output={
  "status":"passed-pinned-native-browser-runtime-preparation",
  "observedAtUtc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "producerRevision":ac["producerRevision"],"ownerRevision":ac["ownerRevision"],
  "hostArchitecture":platform.machine(),"macOSVersion":subprocess.check_output(["/usr/bin/sw_vers","-productVersion"],text=True).strip(),
  "playwrightVersion":"1.56.1","nodeVersion":"22.23.3","downloadedRevisions":ac["requiredCacheDirectories"],
  "sourceConfigAndDependencyBindingsRechecked":13,"cacheFilesAtAcquisition":ar["cacheFiles"],
  "cacheAllocatedBytesAtAcquisition":ar["cacheAllocatedBytes"],"cacheInventoryAtAcquisitionDigest":ar["cacheInventoryDigest"],
  "cacheInventoryAfterControlsDigest":pr["cacheInventoryAfterDigest"],"browserPayloadUnchanged":True,
  "emptyHostValidationMarkersAdded":len(additions),"hardNativeCacheQuotaClaimed":False,
  "existingCachesTargeted":False,"browserVersions":versions,"acceptedControls":accepted,
  "controlsPassed":6,"browserInstancesObservedAndReaped":observed_instances,
  "initialSurvivorFixtureFailurePreserved":True,"initialBrowserAlreadyExitedBeforeGuardian":True,
  "harnessRepairs":1,"alreadyPassingControlsReused":4,"stages":stage_records,
  "guardianDigest":EXPECTED["owned_browser_guard.py"],"browserProbeDigest":EXPECTED["launch-one.cjs"],
  "acquisitionDriverDigest":EXPECTED["acquisition/acquire.py"],"initialControllerDigest":EXPECTED["launch/run.py"],
  "repairControllerDigest":EXPECTED["launch-repair1/run.py"],"reviewerDigest":sha(Path(__file__)),
  "apiImportsRun":False,"applicationDependenciesInstalled":0,"ownerBuildsRepeated":0,
  "upstreamBrowserTestCasesRun":0,"originalFiveProjectMatrixChanged":False,
  "realOwnerBrowserAccepted":False,"backendAuthenticationAccepted":False,"installedBrowserWorkflowAccepted":False,
  "fullNativeCrashClosureAccepted":False,"dependencyClosureAccepted":False,
  "deploymentAccepted":False,"performanceAccepted":False,"completeGoalAccepted":False,"parallelActivated":False,
  "previousUserMaterialDeletionRequested":False,"policyChanged":False,
 }
 with args.output.open("x") as out:json.dump(output,out,indent=2,sort_keys=True);out.write("\n")
 print(json.dumps({"status":output["status"],"controlsPassed":6,"engines":versions,"instancesReaped":observed_instances}))
if __name__=="__main__":main()
