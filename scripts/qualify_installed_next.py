"""Fresh installed Next native-command qualification; full bundle selection stays separate."""
import argparse,hashlib,json,os,platform,shlex,shutil,subprocess,sys,time
from pathlib import Path
from cross_stack_package import install_archive
from installed_selected import verify_installed_source
from project_watch import stop

ROOT=Path(__file__).resolve().parent.parent

def sha(path):
 with Path(path).open("rb") as stream:return "sha256:"+hashlib.file_digest(stream,"sha256").hexdigest()

def write(path,value):path.write_text(json.dumps(value,indent=2)+"\n")

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ["work","evidence"]:parser.add_argument("--"+name,type=Path,required=True)
 args=parser.parse_args()
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
  assert disk.free>=500000000 and disk.used-baseline_bytes<=4000000000,"Combined installed Next qualification storage boundary"
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
 checkout_cli=ROOT/"target/debug/patamaps"
 checkout_driver=ROOT/"scripts/qualify_chatbot_next.py"
 cli_backup=work/"checkout-cli.unavailable"
 driver_backup=work/"checkout-driver.unavailable"
 try:
  run("checkout-cli-for-package",["cargo","+1.99.0","build","--locked","-p","patamaps-cli","--bin","patamaps"],cwd=ROOT,timeout=600)
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
  env["CARGO_TARGET_DIR"]=str(work/"source-target")
  run("source-locked-fetch",["cargo","+1.99.0","fetch","--locked","--target","x86_64-unknown-linux-gnu"],cwd=source,timeout=300)
  prefix=work/"source-cli-installation";assert not prefix.exists()
  run("fresh-source-cargo-install",["cargo","+1.99.0","install","--path",source/"crates/patamaps-cli","--locked","--offline","--debug","--target","x86_64-unknown-linux-gnu","--root",prefix],cwd=source,timeout=1200)
  source_cli=prefix/"bin/patamaps"
  assert verify_installed_source(source,binding)==source_identity
  checkout_cli.rename(cli_backup);checkout_driver.rename(driver_backup)
  assert not checkout_cli.exists() and not checkout_driver.exists() and not (ROOT/"target/debug/patamaps").exists() and not (ROOT/"target/release/patamaps").exists()
  shared=work/"public-tool-caches";shared.mkdir(mode=0o700)
  for label,compiler in [("source",source_cli),("native",native_cli)]:
   assert not checkout_cli.exists() and not checkout_driver.exists()
   assert json.loads(run(label+"-installed-engine",[compiler,"engine"]))==engine
   case_work,case_out=work/(label+"-owner"),out/label
   run(label+"-installed-next",[sys.executable,"-B",source/"scripts/qualify_chatbot_next.py","--cli",compiler,"--runtime","--rewrites","--installed-inventory-digest",binding,"--shared-cache-root",shared,"--work",case_work,"--evidence",case_out],timeout=1200)
   result=json.loads((case_out/"receipt.json").read_bytes());runtime=json.loads((case_out/"runtime.json").read_bytes());browser=json.loads((case_out/"browser-auth.json").read_bytes())
   assert result["status"]=="passed-pinned-chatbot-source-build-auth" and result["sourceRevision"] is None and result["installedSourceIdentity"]==source_identity and result["installedSourceInventoryUnchanged"]
   assert result["compiler"]["engine"]==engine and result["compiler"]["sha256"]==sha(compiler)
   assert result["generatedOutputObservation"]["publicManifestsUnchanged"] and result["rewritePortReservationClosed"]
   assert runtime["ownedProcessGroupsStopped"] and runtime["ownedListenersStopped"] and runtime["generatedOwnerSecretsAbsentFromEvidence"]
   assert len(browser["controls"])==28 and all(row["passed"] for row in browser["controls"]) and browser["upstreamPageTests"]==4
   record["cases"][label]=dict(status=result["status"],compilerDigest=sha(compiler),engine=engine,sourceInventoryDigest=binding,sourceFiles=source_identity["sourceFiles"],upstreamCommit=result["upstreamCommit"],runtimeGroupsPassed=28,upstreamPageTestsPassed=4,generatedOutputObservation=result["generatedOutputObservation"],sourceWithoutGit=True,checkoutCompilerAndDriverUnavailable=True,allOwnedRuntimesStopped=True)
   assert verify_installed_source(source,binding)==source_identity
   save()
  original=source/"docs/guides/rust-project-quickstart.md";backup=work/"installed-guide.original-retained"
  original.rename(backup);original.write_text("controlled installed source mutation\n")
  marker=work/"forbidden.marker";sentinel=work/"sentinel-compiler.sh";sentinel.write_text("#!/bin/sh\nprintf invoked > "+shlex.quote(str(marker))+"\nexit 91\n");sentinel.chmod(0o700)
  try:
   run("changed-installed-source-before-compiler",[sys.executable,"-B",source/"scripts/qualify_chatbot_next.py","--cli",sentinel,"--runtime","--rewrites","--installed-inventory-digest",binding,"--work",work/"refused-owner","--evidence",out/"refused-owner"],expected=1,timeout=30)
   assert not marker.exists() and "INSTALLED_SOURCE_BYTES_CHANGED" in (out/"logs/changed-installed-source-before-compiler.stderr").read_text()
  finally:
   original.rename(work/"installed-guide.changed-retained");backup.rename(original)
  assert verify_installed_source(source,binding)==source_identity and sha(native_cli)==distribution["binaryDigest"]
  record.update(status="passed-installed-next-native-command-workflows",distribution=distribution,sourceIdentity=source_identity,checkoutCompilerAndDriverUnavailableDuringOwners=True,changedSourceRefusedBeforeCompilerMarker=True,restoredSourceInventoryVerified=True,privateGeneratedOutputsPublished=False,publicCachesShared=True)
 except BaseException as error:
  record.update(status="failed",error=type(error).__name__+": "+str(error));save();raise
 finally:
  if cli_backup.exists():
   assert not checkout_cli.exists();cli_backup.rename(checkout_cli)
  if driver_backup.exists():
   assert not checkout_driver.exists();driver_backup.rename(checkout_driver)
 save();print(json.dumps(dict(status=record["status"],sourceFiles=record["sourceIdentity"]["sourceFiles"],cases=list(record["cases"]))))

if __name__=="__main__":main()
