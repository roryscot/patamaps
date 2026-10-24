"""Fresh installed Next qualification; opt-in immutable retained runtime replay."""
import argparse,hashlib,json,os,platform,shlex,shutil,subprocess,sys,time
from pathlib import Path
from cross_stack_package import install_archive
from installed_selected import verify_installed_source
from project_watch import stop

ROOT=Path(__file__).resolve().parent.parent

def sha(path):
 with Path(path).open("rb") as stream:return "sha256:"+hashlib.file_digest(stream,"sha256").hexdigest()

def write(path,value):path.write_text(json.dumps(value,indent=2)+"\n")

def retained_case_result(result,runtime,probe,owned):
 """Admit a complete installed case only after its real child runtime and cleanup."""
 assert result["generatedOutputObservation"]["changedFiles"]==0, "INSTALLED_RETAINED_PRODUCER_CHANGED"
 assert result["generatedOutputObservation"]["before"]==result["generatedOutputObservation"]["after"], "INSTALLED_RETAINED_PRODUCER_CHANGED"
 assert result["retainedPortHandoffVerified"] is True, "INSTALLED_RETAINED_PORT"
 assert result["retainedSelectedExecution"]==dict(status="completed-selected-project-command",postExecutionSelectionVerified=True,selectionPointerUnchanged=True), "INSTALLED_RETAINED_SELECTION"
 for key in ["closedTreeSelected","realMemberAndLinkRefusalsBeforeEffects","standaloneTreeUnchanged","producerSourceAndToolsUnavailable","retainedRuntimeAccepted"]:
  assert probe[key] is True, "INSTALLED_RETAINED_OUTPUT_OR_SOURCE"
 assert probe["runtimeMutationObservation"]["changedEntries"]==0, "INSTALLED_RETAINED_GENERATION_CHANGED"
 actual=runtime["retainedRuntime"]
 assert actual["status"]=="passed-private-retained-next-runtime", "INSTALLED_RETAINED_RUNTIME"
 for key in ["imageBytesModesAndLinkTargetsVerified","readonlyWriteRefused","cacheWritePassed","cacheQuotaFailurePassed","producerUnavailableThroughoutBrowser","selectedGenerationUnchanged","renamedProducerPathsRestored","allOwnedContainersStopped"]:
  assert actual[key] is True, "INSTALLED_RETAINED_ENFORCEMENT_OR_CLEANUP"
 assert len(owned["containers"])==2 and {c["role"] for c in owned["containers"]}=={"probe","app"} and all(c["confirmedStopped"] is True for c in owned["containers"]), "INSTALLED_RETAINED_OWNED_CONTAINERS"
 return dict(retainedRuntimeAccepted=True,selectedGenerationUnchanged=True,producerUnavailableDuringRequests=True,producerRestored=True,allOwnedContainersStopped=True)

def dynamic_case_result(result,runtime,browser):
 """Keep installed acceptance bound to the original dynamic profile."""
 from chatbot_dynamic_profile import DYNAMIC_CONTROLS,SOURCE_BLOBS
 from qualify_chatbot_runtime import EXPECTED_CONTROLS
 assert result["sourceFiles"]==180 and result["sourceTextFiles"]==174, "INSTALLED_DYNAMIC_OWNER_SOURCE"
 assert result["dynamicSourceBindings"]["gitBlobs"]==SOURCE_BLOBS and result["dynamicSourceBindings"]["sourceFiles"]==9 and result["dynamicSourceBindings"]["sourceMutated"] is False, "INSTALLED_DYNAMIC_SOURCE_BINDINGS"
 assert "rewriteQualification" not in result and "standaloneProbe" not in result and "retainedSelectedExecution" not in result, "INSTALLED_DYNAMIC_ORIGINAL_PROFILE"
 qualification=result["dynamicRouteQualification"]
 for key in ["buildBindingsVerified","runtimeAccepted","sourceBytesUnchanged","privateEvidenceBarrierPassed","ownedRuntimesStopped"]:
  assert qualification[key] is True, "INSTALLED_DYNAMIC_QUALIFICATION"
 for key in ["sourceMutationRequested","qualificationConfigurationOverlay","credentialsCaptured","rawRuntimeLogsUploaded","externalModelAccepted"]:
  assert runtime[key] is False, "INSTALLED_DYNAMIC_RUNTIME_SCOPE"
 for controls in [browser["controls"],runtime["browserControls"]]:
  assert len(controls)==29 and {c["name"] for c in controls}==EXPECTED_CONTROLS|DYNAMIC_CONTROLS and all(c["passed"] is True for c in controls), "INSTALLED_DYNAMIC_EXACT_CONTROLS"
 assert browser["upstreamPageTests"]==runtime["upstreamPageTests"]==4, "INSTALLED_DYNAMIC_UPSTREAM_TESTS"
 assert browser["ownedBrowserStopped"] is True and browser["ownedHttpsProxyStopped"] is True, "INSTALLED_DYNAMIC_BROWSER_CLEANUP"
 witness=runtime["dynamicRouteWitness"]
 assert witness==browser["dynamicRouteWitness"], "INSTALLED_DYNAMIC_WITNESS_BINDING"
 for key in ["fixturesUnchanged","ownerPathAndQueryIdMatched","ownerPrivateMessageRendered","distinctSecondIdRendered","crossUserPublicReadonly","guestPublicReadonly","unseenIdEmptyAndNotPersisted"]:
  assert witness[key] is True, "INSTALLED_DYNAMIC_WITNESS"
 for key,status in [("crossUserPrivateStatus",403),("guestPrivateStatus",403),("missingQueryStatus",400),("extraPageSegmentStatus",404),("streamGetStatus",204),("streamPostStatus",405),("extraStreamSegmentStatus",404)]:
  assert witness[key]==status, "INSTALLED_DYNAMIC_REFUSAL_STATUS"
 assert witness["generationPostAttempts"]==0 and witness["rawFixtureValuesPublished"] is False, "INSTALLED_DYNAMIC_GENERATION_OR_DISCLOSURE"
 return dict(dynamicRouteQualification=qualification,dynamicRouteWitness=witness,originalOwnerConfigurationPreserved=True)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ["work","evidence"]:parser.add_argument("--"+name,type=Path,required=True)
 parser.add_argument("--retained-runtime",action="store_true",help="Repeat complete immutable selected runtime with both fresh installations")
 parser.add_argument("--dynamic-routes",action="store_true",help="Repeat the original-config29-group dynamic profile with both fresh installations")
 args=parser.parse_args()
 assert not (args.dynamic_routes and args.retained_runtime),"INSTALLED_DYNAMIC_PROFILE_COMBINATION"
 shared_compilation=args.retained_runtime or args.dynamic_routes
 assert platform.system()=="Linux" and platform.machine()=="x86_64" and os.environ.get("GITHUB_ACTIONS")=="true","Use focused Linux CI; Intel heavy work needs its existing supervisor"
 work,out=args.work.resolve(),args.evidence.resolve()
 work.mkdir(parents=True,exist_ok=False);out.mkdir(parents=True,exist_ok=False);(out/"logs").mkdir()
 assert not any((p/"Cargo.toml").exists() for p in work.parents)
 baseline_bytes=shutil.disk_usage(ROOT).used;started=time.monotonic()
 env={k:v for k,v in os.environ.items() if k in ["PATH","HOME","CARGO_HOME","RUSTUP_HOME"]}
 env.update(GITHUB_ACTIONS="true",PYTHONDONTWRITEBYTECODE="1",CARGO_INCREMENTAL="0",CARGO_BUILD_JOBS="2",CARGO_PROFILE_DEV_DEBUG="0",CARGO_PROFILE_TEST_DEBUG="0",CARGO_TERM_COLOR="never",RUSTUP_TOOLCHAIN="1.99.0")
 record=dict(status="running",sourceRevision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),commands=[],cases={},filesDeleted=0,productionActivation=False,registryPublication=False,completeDependencyClosure=False,fullRetainedNextBundleAccepted=False,performanceAccepted=False,maximumQualificationGrowthBytes=4000000000)
 def save():write(out/"receipt.json",record)
 def capacity():
  disk=shutil.disk_usage(ROOT)
  growth=disk.used-baseline_bytes
  record["storageObservation"]=dict(currentGrowthBytes=growth,peakGrowthBytes=max(growth,record.get("storageObservation",{}).get("peakGrowthBytes",0)),freeBytes=disk.free)
  if disk.free<500000000 or growth>4000000000:
   save()
   raise AssertionError("Combined installed Next qualification storage boundary")
  assert time.monotonic()-started<2400,"Combined installed Next deadline"
 def run(label,argv,cwd=None,expected=0,timeout=1200):
  capacity();begin=time.monotonic()
  stdout_path,stderr_path=out/"logs"/(label+".stdout"),out/"logs"/(label+".stderr")
  with stdout_path.open("xb") as stdout,stderr_path.open("xb") as stderr:
   child=subprocess.Popen([sys.executable,"-B",str(ROOT/"scripts/project_watch.py"),"__guard",*map(str,argv)],cwd=cwd or work,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   try:
    while child.poll() is None:
     capacity();assert time.monotonic()-begin<timeout,(label,"deadline")
     assert stdout.tell()<8388608 and stderr.tell()<8388608,(label,"log bound")
     time.sleep(.5)
    code=child.returncode
   finally:stop(child)
  capacity();record["commands"].append(dict(label=label,exitCode=code,expectedExitCode=expected,elapsedMs=round((time.monotonic()-begin)*1000)));save();print(json.dumps(record["commands"][-1]),flush=True)
  if code!=expected:
   print(stderr_path.read_text(errors="replace")[-5000:],flush=True)
   raise AssertionError((label,code,expected))
  return stdout_path.read_text()
 checkout_cli=ROOT/("target/x86_64-unknown-linux-gnu/debug/patamaps" if shared_compilation else "target/debug/patamaps")
 checkout_driver=ROOT/"scripts/qualify_chatbot_next.py"
 checkout_driver_digest=sha(checkout_driver)
 runtime_options=["--dynamic-routes"] if args.dynamic_routes else ["--rewrites",*(["--standalone-probe","--retained-runtime"] if args.retained_runtime else [])]
 cli_backup=work/"checkout-cli.unavailable"
 driver_backup=work/"checkout-driver.unavailable"
 source_build_output=work/"fresh-source-build-output.retained"
 try:
  target_options=["--target","x86_64-unknown-linux-gnu"] if shared_compilation else []
  run("checkout-cli-for-package",["cargo","+1.99.0","build","--locked","-p","patamaps-cli","--bin","patamaps",*target_options],cwd=ROOT,timeout=600)
  engine=json.loads(run("package-engine",[checkout_cli,"engine"]))
  package=out/"package"
  run("package-exact-current-pair",[sys.executable,"-B",ROOT/"scripts/package.py","--binary",checkout_cli,"--build-profile","development","--output",package],cwd=ROOT,timeout=300)
  distribution=json.loads((package/"distribution.json").read_bytes())
  assert distribution["engines"]==engine and distribution["binaryDigest"]==sha(checkout_cli) and distribution["buildProfile"]=="development"
  for name in ["sourceArchive","nativeArchive"]:
   assert sha(package/distribution[name]["path"])==distribution[name]["digest"]
  source=install_archive(package/distribution["sourceArchive"]["path"],work/"source-installation",work)
  native=install_archive(package/distribution["nativeArchive"]["path"],work/"native-installation",work)
  binding=distribution["sourceInventoryDigest"]
  source_identity=verify_installed_source(source,binding)
  assert not (source/".git").exists()
  native_cli=native/"bin/patamaps";assert sha(native_cli)==distribution["binaryDigest"] and os.access(native_cli,os.X_OK)
  if shared_compilation:
   checkout_cli.rename(cli_backup)
   assert not checkout_cli.exists() and sha(cli_backup)==distribution["binaryDigest"]
   record["checkoutCompilerUnavailableBeforeFreshSourceBuild"]=True
  env["CARGO_TARGET_DIR"]=str(ROOT/"target" if shared_compilation else work/"source-target")
  run("source-locked-fetch",["cargo","+1.99.0","fetch","--locked","--target","x86_64-unknown-linux-gnu"],cwd=source,timeout=300)
  prefix=work/"source-cli-installation";assert not prefix.exists()
  run("fresh-source-cargo-install",["cargo","+1.99.0","install","--path",source/"crates/patamaps-cli","--locked","--offline","--debug","--target","x86_64-unknown-linux-gnu","--root",prefix],cwd=source,timeout=1200)
  if shared_compilation:
   compile_log=(out/"logs/fresh-source-cargo-install.stderr").read_text()
   required=["patamaps-cli","patamaps-workspace"]
   for name in required:
    assert any("Compiling "+name+" v" in line and "("+str(source/"crates"/name)+")" in line for line in compile_log.splitlines()), "INSTALLED_SOURCE_COMPILATION_REQUIRED"
   record["sourceCompilerBuiltFromInstalledSource"]=True
   record["sharedCargoDependencyArtifacts"]=True
   record["freshSourcePackagesConfirmed"]=required
  source_cli=prefix/"bin/patamaps"
  assert verify_installed_source(source,binding)==source_identity
  if shared_compilation:
   assert sha(checkout_cli)==sha(source_cli), "INSTALLED_SOURCE_BUILD_OUTPUT"
   checkout_cli.rename(source_build_output)
  else:
   checkout_cli.rename(cli_backup)
  checkout_driver.rename(driver_backup)
  assert not checkout_cli.exists() and not checkout_driver.exists() and not (ROOT/"target/debug/patamaps").exists() and not (ROOT/"target/release/patamaps").exists()
  shared=work/"public-tool-caches";shared.mkdir(mode=0o700)
  for label,compiler in [("source",source_cli),("native",native_cli)]:
   assert not checkout_cli.exists() and not checkout_driver.exists()
   assert json.loads(run(label+"-installed-engine",[compiler,"engine"]))==engine
   case_work,case_out=work/(label+"-owner"),out/label
   run(label+"-installed-next",[sys.executable,"-B",source/"scripts/qualify_chatbot_next.py","--cli",compiler,"--runtime",*runtime_options,"--installed-inventory-digest",binding,"--shared-cache-root",shared,"--work",case_work,"--evidence",case_out],timeout=1200)
   result=json.loads((case_out/"receipt.json").read_bytes());runtime=json.loads((case_out/"runtime.json").read_bytes());browser=json.loads((case_out/"browser-auth.json").read_bytes())
   assert result["status"]=="passed-pinned-chatbot-source-build-auth" and result["sourceRevision"] is None and result["installedSourceIdentity"]==source_identity and result["installedSourceInventoryUnchanged"]
   assert result["compiler"]["engine"]==engine and result["compiler"]["sha256"]==sha(compiler)
   assert result["generatedOutputObservation"]["publicManifestsUnchanged"]
   if not args.dynamic_routes:assert result["rewritePortReservationClosed"]
   assert runtime["ownedProcessGroupsStopped"] and runtime["ownedListenersStopped"] and runtime["generatedOwnerSecretsAbsentFromEvidence"]
   assert runtime["databaseTransportVerified"]=="authenticated IPv4 loopback TCP" and runtime["databaseUnixSocketsDisabled"] is True
   groups=29 if args.dynamic_routes else 28
   assert len(browser["controls"])==groups and all(row["passed"] for row in browser["controls"]) and browser["upstreamPageTests"]==4
   record["cases"][label]=dict(status=result["status"],compilerDigest=sha(compiler),engine=engine,sourceInventoryDigest=binding,sourceFiles=source_identity["sourceFiles"],upstreamCommit=result["upstreamCommit"],runtimeGroupsPassed=groups,upstreamPageTestsPassed=4,generatedOutputObservation=result["generatedOutputObservation"],sourceWithoutGit=True,checkoutCompilerAndDriverUnavailable=True,allOwnedRuntimesStopped=True)
   if args.dynamic_routes:
    record["cases"][label].update(dynamic_case_result(result,runtime,browser))
   if args.retained_runtime:
    probe=json.loads((case_out/"standalone-probe.json").read_bytes())
    owned=json.loads((case_out/"retained-owned.json").read_bytes())
    record["cases"][label].update(retained_case_result(result,runtime,probe,owned))
   assert verify_installed_source(source,binding)==source_identity
   save()
  original=source/"docs/guides/rust-project-quickstart.md";backup=work/"installed-guide.original-retained"
  original.rename(backup);original.write_text("controlled installed source mutation\n")
  marker=work/"forbidden.marker";sentinel=work/"sentinel-compiler.sh";sentinel.write_text("#!/bin/sh\nprintf invoked > "+shlex.quote(str(marker))+"\nexit 91\n");sentinel.chmod(0o700)
  try:
   run("changed-installed-source-before-compiler",[sys.executable,"-B",source/"scripts/qualify_chatbot_next.py","--cli",sentinel,"--runtime",*runtime_options,"--installed-inventory-digest",binding,"--work",work/"refused-owner","--evidence",out/"refused-owner"],expected=1,timeout=30)
   assert not marker.exists() and "INSTALLED_SOURCE_BYTES_CHANGED" in (out/"logs/changed-installed-source-before-compiler.stderr").read_text()
   assert not (work/"refused-owner").exists() and not (out/"refused-owner").exists(),"INSTALLED_SOURCE_REFUSAL_EFFECTS"
  finally:
   original.rename(work/"installed-guide.changed-retained");backup.rename(original)
  assert verify_installed_source(source,binding)==source_identity and sha(native_cli)==distribution["binaryDigest"]
  record.update(status="passed-installed-next-dynamic-workflows" if args.dynamic_routes else ("passed-installed-next-retained-runtime-workflows" if args.retained_runtime else "passed-installed-next-native-command-workflows"),installedDynamicProfileAccepted=args.dynamic_routes,fullRetainedNextBundleAccepted=args.retained_runtime,distribution=distribution,sourceIdentity=source_identity,checkoutCompilerAndDriverUnavailableDuringOwners=True,changedSourceRefusedBeforeCompilerMarker=True,restoredSourceInventoryVerified=True,privateGeneratedOutputsPublished=False,publicCachesShared=True)
 except BaseException as error:
  record.update(status="failed",error=type(error).__name__+": "+str(error));save();raise
 finally:
  if cli_backup.exists():
   if checkout_cli.exists():
    assert shared_compilation and not source_build_output.exists()
    checkout_cli.rename(source_build_output)
   cli_backup.rename(checkout_cli)
   assert sha(checkout_cli)==distribution["binaryDigest"], "CHECKOUT_COMPILER_RESTORATION"
   record["checkoutCompilerBytesRestored"]=True
  if driver_backup.exists():
   assert not checkout_driver.exists();driver_backup.rename(checkout_driver)
   assert sha(checkout_driver)==checkout_driver_digest,"CHECKOUT_DRIVER_RESTORATION"
   record["checkoutDriverBytesRestored"]=True
 save();print(json.dumps(dict(status=record["status"],sourceFiles=record["sourceIdentity"]["sourceFiles"],cases=list(record["cases"]))))

if __name__=="__main__":main()
