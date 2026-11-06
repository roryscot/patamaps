"""Independently inspect the completed original-owner public browser replay.

Read-only qualification audit; does not run builds, browsers, or application code.
Only the explicitly requested fresh output receipt is written.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,stat,subprocess
DRIVER="sha256:bd7ad4b16b3134818a548b1b00e62b0676b487b390499dbb9ed730e48d014853"
INSPECTOR="sha256:71e812f70068f1eb6db696d102ba4f2ae9806e6561da65281f0f6c6ef5a9f457"
HELPER="sha256:e0152203e3a9ebaa9499c92fdb633a01a50d57f6910c7d5643d1dbd3dced7bf1"
SOURCE="sha256:292dffa8e6ec497f62e6bd7c363c854d9d0a836e2f3a141d89dd4809e78ebab7"
CLI="sha256:cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355"
PROJECTS={"chromium","firefox","webkit","Mobile Chrome","Mobile Safari"}
def need(v,message):
 if not v:raise RuntimeError(message)
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return "sha256:"+h.hexdigest()
def digest(b):return "sha256:"+hashlib.sha256(b).hexdigest()
def absent(pid):
 p=subprocess.run(["/bin/ps","-p",str(pid),"-o","pid="],capture_output=True,text=True,timeout=5)
 return p.returncode==1 and not p.stdout.strip()
def group_absent(group):
 try:os.killpg(group,0);return False
 except ProcessLookupError:return True
def check_tree(root,rows):
 expected={v["path"]:v for v in rows} if isinstance(rows,list) else rows
 actual=set()
 def visit(p,name):
  s=p.lstat()
  if name!="." or "." in expected:
   need(name in expected,"unexpected inventory member")
   actual.add(name);row=expected[name]
   need(stat.S_IMODE(s.st_mode)==row["mode"],"inventory mode changed")
   if stat.S_ISLNK(s.st_mode):need(row["kind"]=="symlink" and os.readlink(p)==row["target"],"symlink changed")
   elif stat.S_ISDIR(s.st_mode):need(row["kind"]=="directory","directory changed")
   else:need(stat.S_ISREG(s.st_mode) and row["kind"]=="file" and s.st_size==row["bytes"] and sha(p)==row["digest"],"file bytes changed")
  if stat.S_ISDIR(s.st_mode):
   for child in sorted(p.iterdir()):visit(child,child.name if name=="." else name+"/"+child.name)
 visit(root,".")
 need(actual==set(expected),"inventory members missing")
def artifacts(attempt):
 rows=read(attempt/"artifacts.json")
 for n,row in rows.items():
  p=attempt/"candidate"/n;s=p.lstat()
  need(stat.S_IMODE(s.st_mode)==row["mode"],"artifact mode changed")
  if row["kind"]=="file":need(stat.S_ISREG(s.st_mode) and s.st_size==row["bytes"] and sha(p)==row["digest"],"artifact bytes changed")
  else:need(row["kind"]=="directory" and stat.S_ISDIR(s.st_mode),"artifact directory changed")
 return sum(v["kind"]=="file" for v in rows.values())
def main():
 a=argparse.ArgumentParser(description=__doc__)
 for n in ["root","work","node","buildctl","output"]:a.add_argument("--"+n,type=Path,required=True)
 args=a.parse_args();root=args.root.resolve();w=args.work.resolve()
 need(not args.output.exists(),"output already exists")
 r=read(w/"receipt.json");frozen=read(w/"frozen.json")
 need(r["status"]=="passed-installed-original-owner-five-project-browser","controller incomplete")
 need(read(w/"supervisor-exit.json")["exitCode"]==0,"supervisor not successful")
 need(sha(w/"run.py")==r["driverDigest"]==frozen["driverDigest"]==DRIVER,"controller bytes changed")
 need(sha(w/"inspector.mjs")==INSPECTOR,"inspector changed")
 for row in frozen["inputs"]:need(sha(Path(row["path"]))==row["digest"],"frozen input changed")
 need(r["sourceRevision"]==frozen["producerRevision"]=="a3bfc6cff664c25b4b22b3d9d3718fe26efe8dfa","producer revision")
 for n in ["launch.json","supervisor.json"]:need(absent(read(w/n)["pid"]),"job owner still live")
 status=json.loads(subprocess.check_output([str(args.node),str(args.buildctl),"status"],text=True,timeout=20))
 need(not status["parallelActivated"] and status["legacyLease"] is None and not status["transactionBlocked"],"scheduler uncertain")
 rid=re.search(r"Build reservation queued: ([0-9a-f-]{36});",(w/"supervisor.stderr").read_text()).group(1)
 req=next(x for x in status["requests"] if x["id"]==rid)
 need(req["state"]=="finished" and req["leaseReleaseCompleted"] and req["enforcement"]=="native-exclusive" and req["limits"]["diskBytes"]==4000000000,"reservation not released/changed")
 gp=Path(re.search(r"^Storage guard record: (.+)$",(w/"supervisor.stdout").read_text(),re.M).group(1));guard=read(gp)
 need(guard["exitCode"]==0 and guard["filesDeleted"]==0 and not guard.get("newSurvivingContainers") and not guard.get("existingContainerUncertainty"),"guard failure")
 source=Path(r["installedSource"]);cli=Path(r["installedCompiler"])
 need(sha(cli)==r["compilerDigest"]==CLI,"compiler changed")
 need(sha(source/"source-inventory.json")==r["sourceIdentity"]["sourceInventoryDigest"]==SOURCE,"source inventory changed")
 entries=read(source/"source-inventory.json")
 need(len(entries)==1250,"installed member count")
 expected={e["path"] for e in entries}|{"source-inventory.json"}
 seen=set()
 for p in source.rglob("*"):
  need(not p.is_symlink(),"installed source symlink")
  if not p.is_dir():need(p.is_file(),"source special file");seen.add(p.relative_to(source).as_posix())
 need(seen==expected,"source membership")
 for e in entries:
  p=source/e["path"];need(p.stat().st_size==e["bytes"] and sha(p)==e["digest"],"installed source byte mismatch")
 need(sha(source/"scripts/selected_next_http_probe.mjs")==HELPER==r["runtimeProbeDigest"],"helper changed")
 command=read(w/"command.json");cfg=read(w/"browser-config.json");argv=command["invocation"]["arguments"]
 need(argv[:2]==["--input-type=module","-e"] and len(argv)<=128 and all(len(x.encode())<=4096 for x in argv),"command argv contract")
 n,k=map(int,argv[3:5])
 need("".join(argv[5:5+n])==(source/"scripts/selected_next_http_probe.mjs").read_text(),"embedded helper binding")
 need("".join(argv[5+n:5+n+k])==(w/"inspector.mjs").read_text(),"embedded inspector binding")
 need(json.loads("".join(argv[5+n+k:]))==cfg,"embedded config binding")
 need(command["invocation"]["codeInputs"]==[] and command["invocation"]["bounds"]==dict(maximumElapsedMs=180000,maximumStdoutBytes=16384,maximumStderrBytes=65536),"native bounds changed")
 need(sha(w/"command.json")==r["runtimeCommandDigest"],"command file changed")
 ir=read(w/"installed-runtime/receipt.json");ex=ir["execution"];cmd=ex["command"]
 need(ir["status"]=="passed-installed-selected-application-workflow" and ir["sourceInventoryUnchanged"] and ir["sourceFiles"]==1250,"installed wrapper incomplete")
 need(ir["wrapperTimeoutSeconds"]==dict(inspection=900,execution=1200),"wrapper budgets changed")
 need(all(c["exitCode"]==0 for c in ir["commands"]) and len(ir["commands"])==3,"wrapper command failures")
 need(all(ex[k] for k in ["preExecutionSelectionVerified","postExecutionSelectionVerified","selectionPointerUnchanged"]),"native selected bindings incomplete")
 need(ex["status"]=="completed-selected-project-command" and cmd["status"]=="completed-project-command","execution failed")
 need(cmd["commandDigest"]==digest(json.dumps(command,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()),"canonical command mismatch")
 need(cmd["programSucceeded"] and cmd["exitCode"]==0 and cmd["executableUnchanged"] and cmd["selectedInputsUnchanged"],"command input/tool changed")
 need(cmd["ambientEnvironment"]=="not-inherited" and cmd["environmentResolution"]=="captured-nonsecretConfiguration-only","environment contract changed")
 need(cmd["completeExecutableDependencyClosureEstablished"] is False,"unexpected dependency closure claim")
 final=read(w/"restored-final-bindings.stdout")
 need(final["status"]=="verified-selected-build-bindings","restored native verification missing")
 stage=read(w/"staging-inputs.json");tools=Path(cfg["tools"]);rows=read(w/"tools-inventory.json")
 need(sha(w/"tools-inventory.json")==cfg["toolsManifestDigest"]==r["toolsInventoryDigest"],"tool manifest changed")
 check_tree(tools,rows)
 need(len(stage)==534==sum(x["kind"]=="file" for x in rows.values()),"staged file count")
 for e in stage:
  src=Path(e["source"]);dest=tools/e["target"]
  need(sha(src)==sha(dest)==e["digest"] and dest.stat().st_size==e["bytes"],"staged source differed")
 original=root.parent/"seeder"
 need(subprocess.check_output(["git","rev-parse","HEAD"],cwd=original,text=True).strip()==frozen["ownerRevision"]=="c61d51a57120abbbca65d4cb4a432c1cef9343bb","owner revision changed")
 need(subprocess.check_output(["git","status","--porcelain=v1","-z"],cwd=original)==b"","original owner dirty")
 originals=["packages/web/e2e/flow-walk.spec.ts","packages/web/playwright.config.ts","packages/web/package.json","packages/storybook-view-flow/src/flow-manifest.json"]
 for n in originals:
  need((tools/n).read_bytes()==subprocess.check_output(["git","show",frozen["ownerRevision"]+":"+n],cwd=original),"upstream test input modified")
 need(r["changedRuntimeToolRefusedBeforeHttpEffects"] and "OWNER_BROWSER_INPUT_BYTES" in (w/"changed-browser-tool-refusal.stderr").read_text(),"tamper refusal missing")
 need(sha(Path(cfg["cacheManifest"]))==cfg["cacheManifestDigest"]=="sha256:0604f767dff7106551363078410ceab9ad498933bbe1307663006da53309a52a","browser cache inventory changed")
 check_tree(Path(cfg["cache"]),read(Path(cfg["cacheManifest"])))
 need(sha(args.node)==cfg["nodeDigest"],"Node changed")
 browser=read(w/"inspection/inspection.json");raw=read(w/"inspection/results.json")
 need(browser["status"]=="passed-original-owner-five-project-flow-walk" and browser["projectCounts"]=={p:5 for p in PROJECTS},"browser matrix")
 need(raw["stats"]["expected"]==25 and all(raw["stats"][n]==0 for n in ["skipped","unexpected","flaky"]) and raw["errors"]==[],"browser test outcomes")
 counts={p:0 for p in PROJECTS};spec_ids=set()
 def walk(suite):
  for spec in suite.get("specs",[]):
   need(spec["ok"],"upstream spec failed");spec_ids.add(spec["id"])
   for t in spec["tests"]:
    need(t["projectName"] in counts and t["status"]=="expected" and len(t["results"])==1 and t["results"][0]["status"]=="passed","unexpected browser attempt")
    counts[t["projectName"]]+=1
  for child in suite.get("suites",[]):walk(child)
 for suite in raw["suites"]:walk(suite)
 need(counts=={p:5 for p in PROJECTS},"incomplete upstream cases")
 need(raw["config"]["workers"]==1 and raw["config"]["globalTimeout"]==600000 and len(raw["config"]["projects"])==5,"upstream configuration changed")
 for project in raw["config"]["projects"]:need(project["retries"]==2,"upstream retry config changed")
 need(browser["proxyOriginRefusalPassed"] and browser["proxyClosed"] and browser["ownedGuardianClosed"] and browser["producerUnavailableThroughout"],"browser runtime ownership")
 need(browser["proxy"]["denied"]==1 and browser["proxy"]["forwarded"]>0 and browser["proxy"]["bodyLimitFailures"]==browser["proxy"]["upstreamErrors"]==0,"proxy failures")
 g=read(w/"inspection/guard-result.json")
 need(g["status"]=="stopped-owned-browser-groups" and not g["ownershipUncertain"] and len(g["groups"])==5,"browser cleanup uncertain")
 need(all(x["stopped"] and group_absent(x["group"]) for x in g["groups"]),"browser groups survived")
 http=read(w/"http.json");server=read(w/"server-process.json")
 need(http["status"]=="passed-current-owner-edited-runtime-http" and len(http["cases"])==7 and http["readyInspectionCompleted"] and http["serverStopped"] and server["closed"] and absent(server["pid"]),"HTTP/server incomplete")
 need(r["checkoutPathsRestored"] and r["runtimeProducerPathsRestored"] and r["checkoutPathsUnavailable"]==5,"paths not restored")
 for n,h in r["checkoutPathDigests"].items():need(sha(Path(n))==h,"checkout path changed")
 for n,identity in r["runtimePathIdentities"].items():
  s=Path(n).lstat();need([s.st_dev,s.st_ino,s.st_mode]==identity,"runtime inode changed")
 for moves in ["checkout-moves","runtime-moves"]:
  for x in read(w/moves/"producer-moves.json"):need(os.path.lexists(x["original"]) and not os.path.lexists(x["retained"]),"producer move unresolved")
 need(subprocess.check_output(["git","status","--porcelain=v1","-z"],cwd=root)==b"","checkout dirty before publication")
 state=Path(r["state"]);selection=read(state/"selected.json");attempt=state/selection["attempt"]
 need(sha(state/"selected.json")==r["selectedPointerDigest"] and len(list((state/"attempts").iterdir()))==1,"native selection changed")
 need(sha(attempt/"artifacts.json")==r["artifactManifestDigest"] and artifacts(attempt)==2482,"selected artifact changed")
 need(sha(attempt/"candidate/patamaps-native-tooling/trace.jsonl")==r["nativeLedgerDigest"],"execution ledger changed")
 fixture=read(root/".tools/installed-original-owner-next-20261027/owner-fixture.json")
 old=Path(r["oldState"]);old_selection=read(old/"selected.json")
 need(sha(old/"selected.json")==fixture["originalRetainedPointerDigest"] and len(list((old/"attempts").iterdir()))==4,"old selection changed")
 old_count=artifacts(old/old_selection["attempt"])
 owner=root/".tools/installed-original-owner-next-20261027/owner-native/owner"
 for n,h in fixture["sourceInputs"].items():need(sha(owner/n)==h,"owner source changed")
 for n,h in fixture["expectedGenerated"].items():need(sha(Path(fixture["originalOracle"])/n)==h,"original oracle changed")
 need(all(sha(Path(p))==h for p,h in r["protectedInputs"].items()),"protected inputs changed")
 need(r["ownerBuildReruns"]==0 and r["runtimeToolsUnchanged"] and r["originalStateAndArtifactsUnchanged"],"unexpected rebuild or mutation")
 for label in ["authenticatedBrowserAccepted","deploymentAccepted","performanceAccepted"]:need(r[label] is False,"broader acceptance misclaimed")
 result=dict(status="passed-independent-original-owner-public-browser-review",reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewerDigest=sha(Path(__file__)),producerRevision=frozen["producerRevision"],ownerRevision=frozen["ownerRevision"],controllerDigest=DRIVER,inspectorDigest=INSPECTOR,helperDigest=HELPER,compilerDigest=CLI,sourceInventoryDigest=SOURCE,installedSourceFiles=1250,stagedToolFiles=534,originalBrowserProjects=5,originalTestsPerProject=5,originalBrowserCases=25,skipped=0,flaky=0,failed=0,extraRuntimeInputBinding="command-argv-preflight-and-postcheck",codeInputs=[],nativeSelectedBindings="pre-post-and-restored-final",oldAndSelectedArtifactFilesRehashed=old_count+2482,ownerSourceFilesRehashed=len(fixture["sourceInputs"]),oracleOutputsRehashed=len(fixture["expectedGenerated"]),producerPathsRestored=8,runtimeInodeIdentitiesIndependentlyVerified=3,checkoutInodeIdentitiesCheckedByController=5,ownedBrowserGroupsAbsent=5,httpCases=7,ownedNextServerAbsent=True,proxyOriginRefusalPassed=True,browserCacheUnchanged=True,tamperRefusedBeforeHttpEffects=True,appBuildsRerun=0,newStateAttempts=0,reservationId=rid,reservationFinishedAndReleased=True,parallelActivated=False,guardRecordDigest=sha(gp),privateControllerReceiptDigest=sha(w/"receipt.json"),rawBrowserResultsDigest=sha(w/"inspection/results.json"),authenticatedBrowserAccepted=False,visiblePermissionLabelAccepted=False,watchAccepted=False,deploymentAccepted=False,performanceAccepted=False,completeDependencyClosureEstablished=False,wholeProcessNetworkIsolationEstablished=False,goalComplete=False,filesDeleted=0,policyChanged=False)
 args.output.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result))
if __name__=="__main__":main()
