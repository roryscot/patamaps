"""Pinned public Next application source/build observations before runtime acceptance."""
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,time
from pathlib import Path
from qualify_fumadocs_next import acquire_source
from project_watch import stop
ROOT=Path(__file__).resolve().parent.parent
REV="c2f8235e1f3ea903ad8b7f61447c4f74164b5c58"
UPSTREAM="https://github.com/vercel/chatbot.git"


def sha(path):
 with path.open("rb") as f:return "sha256:"+hashlib.file_digest(f,"sha256").hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+"\n")


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ["work","evidence","cli"]:p.add_argument("--"+n,type=Path,required=True)
 p.add_argument("--build-cli",action="store_true");p.add_argument("--runtime",action="store_true");p.add_argument("--rewrites",action="store_true");a=p.parse_args()
 assert not a.rewrites or a.runtime, "Rewrite acceptance requires actual production runtime"
 assert platform.system()=="Linux" and platform.machine()=="x86_64" and os.environ.get("GITHUB_ACTIONS")=="true","Use focused Linux CI; native Intel allocation requires its existing guard"
 work,out,cli=a.work.resolve(),a.evidence.resolve(),a.cli.resolve()
 work.mkdir(parents=True,exist_ok=False);out.mkdir(parents=True,exist_ok=False);(out/"logs").mkdir()
 assert not any((v/"Cargo.toml").exists() for v in work.parents)
 baseline=shutil.disk_usage(ROOT).used
 env={k:v for k,v in os.environ.items() if k in ["PATH","HOME","CARGO_HOME","RUSTUP_HOME"]}
 env.update(CARGO_HOME=env.get("CARGO_HOME",str(Path.home()/".cargo")),RUSTUP_HOME=env.get("RUSTUP_HOME",str(Path.home()/".rustup")))
 for n in ["home","tmp","tools","store"]:(work/n).mkdir()
 env.update(HOME=str(work/"home"),TMPDIR=str(work/"tmp"),CI="true",LANG="C.UTF-8",TZ="UTC",CARGO_INCREMENTAL="0",CARGO_BUILD_JOBS="2",CARGO_PROFILE_DEV_DEBUG="0",CARGO_PROFILE_TEST_DEBUG="0",RUSTUP_TOOLCHAIN="1.99.0",CARGO_TERM_COLOR="never",PYTHONDONTWRITEBYTECODE="1",NEXT_TELEMETRY_DISABLED="1",NODE_OPTIONS="--max-old-space-size=2048",GIT_TERMINAL_PROMPT="0",GIT_CONFIG_GLOBAL="/dev/null",GIT_CONFIG_SYSTEM="/dev/null",npm_config_userconfig="/dev/null",npm_config_globalconfig="/dev/null",CI_PLAYWRIGHT="1")
 for key,name in [("npm_config_userconfig","npm-user.conf"),("npm_config_globalconfig","npm-global.conf")]:
  path=work/"tools"/name;path.write_text("");env[key]=str(path)
 r=dict(status="running",sourceRevision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),upstream=UPSTREAM,upstreamCommit=REV,commands=[],frameworkBuildEstablished=False,runtimeEstablished=False,authenticationAccepted=False,dependencyClosureEstablished=False,applicationAcceptance=False,productionActivation=False,filesDeleted=0,maximumWorkflowGrowthBytes=4000000000)
 def save():write(out/"receipt.json",r)
 def capacity():
  d=shutil.disk_usage(ROOT);assert d.free>=500000000 and d.used-baseline<=4000000000,"CI workflow storage boundary"
 def run(label,argv,cwd=None,data=None,timeout=1200,expected=0):
  capacity();began=time.monotonic();stdout_path=out/"logs"/(label+".stdout");stderr_path=out/"logs"/(label+".stderr");input_path=out/"logs"/(label+".input")
  if data is not None:input_path.write_bytes(data)
  with stdout_path.open("xb") as stdout,stderr_path.open("xb") as stderr:
   incoming=input_path.open("rb") if data is not None else subprocess.DEVNULL
   try:
    child=subprocess.Popen([sys.executable,str(ROOT/"scripts/project_watch.py"),"__guard",*map(str,argv)],cwd=cwd or ROOT,env=env,stdin=incoming,stdout=stdout,stderr=stderr,start_new_session=True)
    try:
     while child.poll() is None:
      capacity();assert time.monotonic()-began<timeout,(label,"deadline");assert stdout.tell()<67108864 and stderr.tell()<67108864,(label,"log bound");time.sleep(.5)
     code=child.returncode
    finally:stop(child)
   finally:
    if data is not None:incoming.close()
  capacity();r["commands"].append(dict(label=label,exitCode=code,expectedExitCode=expected,elapsedMs=round((time.monotonic()-began)*1000)));save();print(json.dumps(r["commands"][-1]),flush=True)
  if code!=expected:
   print(stderr_path.read_text(errors="replace")[-6000:],flush=True);print(stdout_path.read_text(errors="replace")[-3000:],flush=True);raise AssertionError((label,code,expected))
  return stdout_path.read_bytes()
 def native(label,args,**kw):return json.loads(run(label,[cli,*args],**kw))
 try:
  if a.build_cli:run("current-cli-build",["cargo","+1.99.0","build","--locked","-p","patamaps-cli","--bin","patamaps"])
  engine=native("current-engine",["engine"]);sys.path.insert(0,str(ROOT/"scripts/parity"));from identity import identities
  assert engine==dict(schemaVersion="0.1.0",documentType="executor-description",**identities(ROOT));r["compiler"]=dict(sha256=sha(cli),engine=engine)
  owner,selected,omitted,inventory,audit=acquire_source(run,work,out,upstream=UPSTREAM,revision=REV,required_omissions=(".env.example",))
  assert not any(Path(e["path"]).name=="AGENTS.md" for e in selected),"Review new upstream instructions"
  package=json.loads((owner/"package.json").read_bytes());assert package["packageManager"]=="pnpm@10.32.1" and package["dependencies"]["next"]=="16.2.10" and package["scripts"]["build"]=="tsx lib/db/migrate && next build"
  r["sourceFiles"]=len(selected);r["omittedPaths"]=[e["path"] for e in omitted]
  definition=work/"selection.json";write(definition,dict(profile="patamaps-project-context-selection-1",id="urn:qualification:chatbot:source",nonsecretInputs=True,paths=[e["path"] for e in selected],symlinks="internal-closed"))
  snapshot=work/"source-snapshot";capture=native("source-context-capture",["project-context-capture",definition,"--root",owner,"--destination",snapshot])
  staged=work/"staged";stage=native("source-context-stage",["project-context-stage",snapshot,"--destination",staged]);assert stage["digest"]==capture["digest"]
  staged_inventory=inventory
  rewrite_overlay=None
  if a.rewrites:
   from chatbot_rewrite_profile import apply
   staged_inventory,rewrite_overlay=apply(staged,inventory)
   write(out/"rewrite-overlay.json",rewrite_overlay)
   write(out/"derived-source.json",staged_inventory)
   derived_definition=work/"derived-selection.json";write(derived_definition,dict(profile="patamaps-project-context-selection-1",id="urn:qualification:chatbot:derived-rewrites",nonsecretInputs=True,paths=[e["path"] for e in staged_inventory],symlinks="internal-closed"))
   derived_capture=native("derived-context-capture",["project-context-capture",derived_definition,"--root",staged,"--destination",work/"derived-snapshot"])
   r["rewriteQualification"]=dict(**rewrite_overlay,derivedSourceContextDigest=derived_capture["digest"],originalSourceContextDigest=capture["digest"])
  def sha_bytes(base,e):
   data=os.readlink(base/e["path"]).encode() if e["symlink"] else (base/e["path"]).read_bytes()
   return "sha256:"+hashlib.sha256(data).hexdigest()
  def source_unchanged(base,expected=None):
   return all(sha_bytes(base,e)==e["digest"] and (e["symlink"] or (base/e["path"]).stat().st_mode & 0o777 == (0o755 if e["mode"]=="100755" else 0o644)) for e in (inventory if expected is None else expected))
  assert all(sha_bytes(staged,e)==e["digest"] for e in staged_inventory)
  run("pnpm-install-tool",["npm","install","--prefix",work/"tools","pnpm@10.32.1","--ignore-scripts","--no-audit","--no-fund"])
  pnpm=work/"tools/node_modules/pnpm/bin/pnpm.cjs";assert pnpm.is_file()
  r["pnpmTool"]=dict(version=json.loads((work/"tools/node_modules/pnpm/package.json").read_bytes())["version"],entryDigest=sha(pnpm),toolLockDigest=sha(work/"tools/package-lock.json"))
  assert r["pnpmTool"]["version"]=="10.32.1"
  run("owner-frozen-dependencies",[pnpm,"install","--frozen-lockfile","--ignore-scripts","--store-dir",work/"store"],cwd=staged)
  assert source_unchanged(staged,staged_inventory) and source_unchanged(owner)
  texts=[]
  for e in staged_inventory:
   if e["symlink"]:continue
   try:text=(staged/e["path"]).read_bytes().decode("utf8")
   except UnicodeDecodeError:continue
   if "\0" in text:continue
   texts.append(e["path"])
  cfg=dict(path=env["PATH"],home=env["HOME"],tmp=env["TMPDIR"],ci="true",nodeOptions=env["NODE_OPTIONS"],telemetry="1",ownerTestMode="1",npmUser=env["npm_config_userconfig"],npmGlobal=env["npm_config_globalconfig"])
  profile=work/"profile.json";write(profile,dict(profile="patamaps-project-inputs-1",id="urn:qualification:chatbot:inputs",nonsecretInputs=True,inputs=texts,components=[dict(id="web",kind="next-app",root=".",entrypoints=["package.json","next.config.ts","app/layout.tsx","app/(auth)/actions.ts"])],nonsecretConfiguration=cfg,secretReferences=dict(AUTH_SECRET="OWNER_AUTH_SECRET",POSTGRES_URL="OWNER_POSTGRES_URL")))
  source=native("text-source-capture",["project-capture",profile,"--root",staged]);source_path=work/"capture.json";write(source_path,source)
  if a.rewrites:
   marker_command=work/"source-marker.command.json";marker=staged/"rewrite-forbidden.marker"
   write(marker_command,dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences={},invocation=dict(executable="/bin/sh",arguments=["-c","printf invoked > rewrite-forbidden.marker"],codeInputs=[],bounds=dict(maximumElapsedMs=5000,maximumStdoutBytes=1024,maximumStderrBytes=1024))))
   original_config=staged/"next.config.ts";backup=work/"derived-config.retained"
   original_config.rename(backup);original_config.write_bytes(backup.read_bytes()+b"\n// controlled captured configuration mutation\n")
   try:
    run("captured-config-before-effects",[cli,"project-exec",source_path,marker_command,"--root",staged],expected=2)
    assert not marker.exists() and "PROJECT" in (out/"logs/captured-config-before-effects.stderr").read_text()
   finally:
    original_config.rename(work/"changed-config.retained");backup.rename(original_config)
   assert source_unchanged(staged,staged_inventory)
   r["rewriteQualification"]["capturedConfigMutationRefusedBeforeMarker"]=True
  command=work/"build.command.json";write(command,dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences=dict(PATH="path",HOME="home",TMPDIR="tmp",CI="ci",NODE_OPTIONS="nodeOptions",NEXT_TELEMETRY_DISABLED="telemetry",CI_PLAYWRIGHT="ownerTestMode",NPM_CONFIG_USERCONFIG="npmUser",NPM_CONFIG_GLOBALCONFIG="npmGlobal"),invocation=dict(executable=str(pnpm),arguments=["build"],codeInputs=[],bounds=dict(maximumElapsedMs=1200000,maximumStdoutBytes=1048576,maximumStderrBytes=65536))))
  result=native("owner-production-build",["project-exec",source_path,command,"--root",staged],timeout=1250)
  assert result["status"]=="completed-project-command" and result["programSucceeded"] and result["selectedInputsUnchanged"]
  r["frameworkBuildEstablished"]=True;r["ownerMigrationSkippedBecauseNoDatabaseConfigured"]="POSTGRES_URL not defined, skipping migrations" in result["stdout"]["text"]
  assert source_unchanged(staged,staged_inventory) and source_unchanged(owner)
  observations=work/"observations";observations.mkdir()
  files={"routes.json":staged/".next/routes-manifest.json","app-paths.json":staged/".next/server/app-paths-manifest.json","app-routes.json":staged/".next/app-path-routes-manifest.json"}
  for name,path in files.items():shutil.copyfile(path,observations/name)
  version=json.loads((staged/"node_modules/next/package.json").read_bytes())["version"];assert version=="16.2.10"
  projection=dict(profile="patamaps-next-build-config-1",frameworkVersion=version,buildReceiptDigest=sha(out/"logs/owner-production-build.stdout"),routesDigest=sha(observations/"routes.json"),appPathsDigest=sha(observations/"app-paths.json"),appPathRoutesDigest=sha(observations/"app-routes.json"),configuration=dict(basePath="",output="server",trailingSlash=False,environment={"NEXT_PUBLIC_BASE_PATH":""},secretReferences={"AUTH_SECRET":"OWNER_AUTH_SECRET","POSTGRES_URL":"OWNER_POSTGRES_URL"},transpilePackages=[],serverActions=None))
  write(observations/"config.json",projection)
  config=dict(provider="next-build",nonsecretInputs=True,routesManifest="routes.json",appPathsManifest="app-paths.json",appPathRoutesManifest="app-routes.json",configurationProjection="config.json")
  inputs=[dict(receipt=dict(path=p.name,digest=sha(p),byteLength=p.stat().st_size),content=p.read_text()) for p in sorted(observations.iterdir())]
  request=dict(schemaVersion="0.1.0",documentType="adapter-request",profile="patamaps-workspace-draft-1",sourceId="urn:qualification:chatbot:next",namespace="chatbot-next-build",config=config,inputs=inputs,invocationDigest="sha256:"+"0"*64,requestDigest="")
  request["requestDigest"]=json.loads(run("manifest-request-digest",[cli,"json","digest"],data=json.dumps(request).encode()))
  observed=json.loads(run("native-compiled-next-observations",[cli,"discover-native"],data=json.dumps(request).encode(),cwd=observations));write(out/"native-observations.json",observed)
  assert observed["requestDigest"]==request["requestDigest"] and observed["shard"]["metadata"]["observation"]["runtimeEstablished"] is False
  if a.rewrites:
   from chatbot_rewrite_profile import verify_compiled
   baseline=json.loads((ROOT/"docs/acceptance/project-adoption/g3-chatbot-source-20261023/native-observations.json").read_bytes())
   bound=verify_compiled(json.loads(files["routes.json"].read_bytes()),observed,baseline)
   bound["baselineObservationDigest"]=sha(ROOT/"docs/acceptance/project-adoption/g3-chatbot-source-20261023/native-observations.json")
   write(out/"rewrite-compiled.json",bound)
   def refuse_observation(label,changed):
    changed["requestDigest"]=""
    changed["requestDigest"]=json.loads(run(label+"-digest",[cli,"json","digest"],data=json.dumps(changed).encode()))
    run(label,[cli,"discover-native"],data=json.dumps(changed).encode(),cwd=observations,expected=2)
    assert "NATIVE_NEXT_BUILD" in (out/"logs"/(label+".stderr")).read_text()
   missing=json.loads(json.dumps(request));missing["inputs"]=[v for v in missing["inputs"] if v["receipt"]["path"]!="config.json"]
   refuse_observation("rewrite-missing-config-projection",missing)
   changed=json.loads(json.dumps(request));route=next(v for v in changed["inputs"] if v["receipt"]["path"]=="routes.json")
   manifest=json.loads(route["content"]);manifest["rewrites"]["beforeFiles"][0]["destination"]="/register"
   route["content"]=json.dumps(manifest);raw=route["content"].encode();route["receipt"].update(digest="sha256:"+hashlib.sha256(raw).hexdigest(),byteLength=len(raw))
   refuse_observation("rewrite-stale-projection-binding",changed)
   r["rewriteQualification"].update(compiledRulesBound=True,originalRulesPreserved=bound["originalRulesPreserved"],missingProjectionRefused=True,staleProjectionRefusedAfterRequestRehash=True)
  if a.runtime:
   run("owner-pinned-browser-install",[pnpm,"exec","playwright","install","chromium"],cwd=staged,timeout=600)
   browser_bootstrap=json.loads(run("owner-browser-runtime-dependency-preflight",["node","-e",'const {chromium}=require("@playwright/test"); (async()=>{let browser;try{browser=await chromium.launch({headless:true});console.log(JSON.stringify({browserLaunchSucceeded:true,browserVersion:browser.version()}));}finally{if(browser)await browser.close();}})().catch(()=>{console.error("Unprivileged browser launch preflight failed");process.exitCode=1;});'],cwd=staged,timeout=45))
   assert browser_bootstrap["browserLaunchSucceeded"] is True
   r["browserBootstrap"]=dict(**browser_bootstrap,systemPackageInstallationRequested=False)
   from qualify_chatbot_runtime import qualify
   runtime=qualify(staged,work,out,pnpm,env,capacity,rewrite_profile=rewrite_overlay)
   assert runtime["status"]=="passed" and runtime["ownedProcessGroupsStopped"]
   r.update(runtimeEstablished=True,authenticationAccepted=True,ownerRuntimeMigrationExecuted=True,runtimeBoundary="trusted owner; new isolated CI PostgreSQL and HTTPS loopback; no production secrets")
  audit("source-exclusion-final-audit");assert source_unchanged(owner) and source_unchanged(staged,staged_inventory)
  r.update(status="passed-pinned-chatbot-source-build-auth" if a.runtime else "passed-pinned-chatbot-source-build-observations",frameworkVersion=version,sourceContextDigest=capture["digest"],textSourceDigest=source["digest"],sourceTextFiles=len(texts),selectedSourceBytesAndModesUnchanged=True,sourceExclusionAudited=True,dependencyLifecycleScriptsExecuted=False,nativeCompiledObservation=True,ownerTestMode="CI_PLAYWRIGHT=1 selects the owner's model-test mode; no model behavior accepted")
 except BaseException as error:
  r.update(status="failed",error=str(error))
  if "source_unchanged" in locals():
   try:r["selectedSourcesUnchangedAfterFailure"]=source_unchanged(owner) and source_unchanged(staged,staged_inventory)
   except (OSError,ValueError):r["selectedSourcesUnchangedAfterFailure"]=None
  save();raise
 save();print(json.dumps(dict(status=r["status"],frameworkBuildEstablished=True,runtimeEstablished=r["runtimeEstablished"])))


if __name__=="__main__":main()
