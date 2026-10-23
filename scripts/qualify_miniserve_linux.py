"""Pinned external Rust application qualification, using existing native contracts."""
import argparse,hashlib,json,os,platform,re,shutil,socket,subprocess,sys,tarfile,time
from pathlib import Path
from project_watch import stop
ROOT=Path(__file__).resolve().parent.parent
REV="2cd9c495ef25f2fcef505615f603e9de8f981915"
ARM_SHA="732b1d5b30a3903580cee9ca24b2ff04ba2a5c78fa1ba6579dc5154fc431b40a"
PUBLIC_TEST_FIXTURES={"tests/data/auth1.txt":"3744d61850e90a0da0b6477b548bca8c4f1e278d","tests/data/cert.pem":"c907ef259f08d6f9833e17e6839554924d5161e2","tests/data/cert_ec.pem":"42d4a086b7f93a7b4b61cd5bbbe36d5f402c79c7","tests/data/cert_rsa.pem":"54482008bde8184e0600600c10c2c287a1077946","tests/data/generate_tls_certs.sh":"facd0336564412d77cec8fb5d74d5adb80b670ca","tests/data/key_ec.pem":"484e5d8135c75c61e326ba3e00722d7f3e194160","tests/data/key_pkcs1.pem":"695ff0919c9ba5b0ba6ae293396e9fdccd59ec7f","tests/data/key_pkcs8.pem":"695ff0919c9ba5b0ba6ae293396e9fdccd59ec7f"}
def select_captured_source(names,blobs):
 external={n for n in names if n.startswith("tests/data/")}
 if external!=set(PUBLIC_TEST_FIXTURES):raise ValueError("REVIEW_PUBLIC_TEST_FIXTURE_SET")
 if any(blobs.get(n)!=h for n,h in PUBLIC_TEST_FIXTURES.items()):raise ValueError("REVIEW_PUBLIC_TEST_FIXTURE_BLOB")
 selected=[n for n in names if n not in external]
 if any(Path(n).name==".env" or Path(n).name.startswith(".env.") or Path(n).suffix in [".pem",".key",".p12"] for n in selected):raise ValueError("FORBIDDEN_SOURCE_INPUT")
 return selected
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+"\n")
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ["cli","work","evidence"]:p.add_argument("--"+n,type=Path,required=True)
 p.add_argument("--build-cli",action="store_true");a=p.parse_args()
 assert platform.system()=="Linux" and platform.machine()=="x86_64" and os.environ.get("GITHUB_ACTIONS")=="true","Use dedicated Linux CI; Intel requires its supervisor"
 work=a.work.resolve();out=a.evidence.resolve();assert not work.exists() and not out.exists()
 work.mkdir(parents=True);out.mkdir(parents=True);(out/"logs").mkdir();(out/"artifacts").mkdir()
 assert not any((x/"Cargo.toml").exists() for x in work.parents)
 baseline=shutil.disk_usage(ROOT).used
 r=dict(status="running",sourceRevision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),upstream="https://github.com/svenstaro/miniserve.git",upstreamCommit=REV,commands=[],filesDeleted=0,productionActivation=False,registryPublication=False,completeDependencyClosure=False,nativePackageInstallerExercised=False)
 env={k:v for k,v in os.environ.items() if k in ["PATH","HOME","CARGO_HOME","RUSTUP_HOME"]}
 env.update(PYTHONDONTWRITEBYTECODE="1",CARGO_INCREMENTAL="0",CARGO_BUILD_JOBS="2",RUST_TEST_THREADS="1",CARGO_PROFILE_DEV_DEBUG="0",CARGO_PROFILE_TEST_DEBUG="0",CARGO_TERM_COLOR="never")
 def save():write(out/"receipt.json",r)
 def capacity():
  d=shutil.disk_usage(ROOT);assert d.free>=500000000 and d.used-baseline<=4000000000,"CI storage boundary reached"
 def run(label,argv,cwd=None,expected=0,timeout=1200):
  capacity();start=time.monotonic()
  with (out/"logs"/(label+".stdout")).open("xb") as stdout,(out/"logs"/(label+".stderr")).open("xb") as stderr:
   child=subprocess.Popen([sys.executable,str(ROOT/"scripts/project_watch.py"),"__guard",*map(str,argv)],cwd=cwd,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   try:
    while child.poll() is None:
     capacity();assert time.monotonic()-start<timeout,(label,"timeout")
     assert stdout.tell()<67108864 and stderr.tell()<67108864,"log limit";time.sleep(.5)
    code=child.returncode
   finally:stop(child)
  r["commands"].append(dict(label=label,argv=list(map(str,argv)),exitCode=code,expectedExitCode=expected,elapsedMs=round((time.monotonic()-start)*1000)));save();print(json.dumps(r["commands"][-1]),flush=True)
  if code!=expected:
   print((out/"logs"/(label+".stderr")).read_text()[-5000:]);print((out/"logs"/(label+".stdout")).read_text()[-2000:]);raise AssertionError((label,code,expected))
  return (out/"logs"/(label+".stdout")).read_text()
 def native(label,argv,expected=0):return json.loads(run(label,[cli,*argv],expected=expected))
 def command(exe,args,refs=None,inputs=None,maximum=60000):
  return dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences=refs or {},invocation=dict(executable=str(exe),arguments=list(map(str,args)),codeInputs=inputs or [],bounds=dict(maximumElapsedMs=maximum,maximumStdoutBytes=65536,maximumStderrBytes=65536)))
 try:
  if a.build_cli:run("build-native-compiler",["cargo","+1.99.0","build","--locked","--release","-p","patamaps-cli","--bin","patamaps"],cwd=ROOT)
  installed=work/"relocated-native/bin";installed.mkdir(parents=True);cli=installed/"patamaps";shutil.copy2(a.cli.resolve(strict=True),cli)
  assert sha(cli)==sha(a.cli);r["relocatedCompiler"]=dict(sha256=sha(cli),freshDirectory=True,engine=native("relocated-engine",["engine"]))
  shutil.copy2(cli,out/"artifacts/patamaps");shutil.copyfile(ROOT/"LICENSE",out/"artifacts/PATAMAPS-LICENSE")
  source=work/"upstream";run("source-init",["git","init",source]);run("source-fetch",["git","fetch","--depth=1",r["upstream"],REV],cwd=source);run("source-checkout",["git","checkout","--detach","FETCH_HEAD"],cwd=source)
  assert run("source-head",["git","rev-parse","HEAD"],cwd=source).strip()==REV
  names=sorted(n for n in run("source-members",["git","ls-files","-z"],cwd=source).split("\0") if n)
  assert not any(Path(n).name=="AGENTS.md" for n in names),"Review upstream instructions"
  index=run("source-fixture-index",["git","ls-files","--stage","-z"],cwd=source)
  blobs={row.split("\t",1)[1]:row.split("\t",1)[0].split()[1] for row in index.split("\0") if row}
  names=select_captured_source(names,blobs)
  r["uncapturedPublicTestFixtures"]={n:dict(gitBlob=h,source="pinned public Git clone",captured=False,published=False) for n,h in PUBLIC_TEST_FIXTURES.items()}
  before={n:sha(source/n) for n in names};r["upstreamInventory"]=before
  cargo=Path(run("cargo-path",["rustup","which","--toolchain","1.99.0","cargo"]).strip());rustc=cargo.with_name("rustc")
  r["rustcVersion"]=run("rustc-version",[rustc,"-vV"]);assert "host: x86_64-unknown-linux-gnu" in r["rustcVersion"]
  run("locked-dependencies",[cargo,"fetch","--locked","--target","x86_64-unknown-linux-gnu"],cwd=source)
  assert {n:sha(source/n) for n in names}==before
  selection=work/"source-selection.json";write(selection,dict(profile="patamaps-project-context-selection-1",id="urn:qualification:miniserve:source",nonsecretInputs=True,paths=names,symlinks="internal-closed"))
  snapshot=work/"source-snapshot";native("source-context",["project-context-capture",selection,"--root",source,"--destination",snapshot])
  staged=work/"source-staged";native("source-stage",["project-context-stage",snapshot,"--destination",staged])
  selected=[n for n in names if (n.endswith(".rs") or n.endswith(".toml") or n in ["Cargo.lock","LICENSE"]) and not (staged/n).is_symlink()]
  cfg=dict(path=str(cargo.parent)+":/usr/bin:/bin",cargoHome=env.get("CARGO_HOME",str(Path.home()/".cargo")),rustc=str(rustc),home=str(work/"home"),tmp=str(work/"tmp"),jobs="2",offline="true",debug="0",incremental="0",threads="1",targetDir=str(staged/"target"))
  for n in ["home","tmp"]:(work/n).mkdir()
  profilepath=work/"source-profile.json";write(profilepath,dict(profile="patamaps-project-inputs-1",id="urn:qualification:miniserve:build-source",nonsecretInputs=True,inputs=selected,components=[dict(id="application",kind="rust",root=".",entrypoints=["Cargo.toml"])],nonsecretConfiguration=cfg,secretReferences={}))
  capture=native("source-capture",["project-capture",profilepath,"--root",staged]);capturepath=work/"source-capture.json";write(capturepath,capture)
  refs=dict(PATH="path",CARGO_HOME="cargoHome",RUSTC="rustc",HOME="home",TMPDIR="tmp",CARGO_BUILD_JOBS="jobs",CARGO_NET_OFFLINE="offline",CARGO_PROFILE_DEV_DEBUG="debug",CARGO_PROFILE_TEST_DEBUG="debug",CARGO_INCREMENTAL="incremental",RUST_TEST_THREADS="threads",CARGO_TARGET_DIR="targetDir")
  for label,args in [("application-build",["build","--release","--locked","--offline","--bin","miniserve"]),("application-owner-tests",["test","--release","--locked","--offline"])]:
   cp=work/(label+".command.json");write(cp,command(cargo,args,refs,maximum=1200000))
   result=native(label,["project-exec",capturepath,cp,"--root",staged if label=="application-build" else source]);assert result["status"]=="completed-project-command" and result["programSucceeded"] and result["selectedInputsUnchanged"]
   if label=="application-build":
    binary=work/"source-built-miniserve";shutil.copy2(staged/"target/release/miniserve",binary)
    r["applicationBinary"]=dict(sha256=sha(binary),bytes=binary.stat().st_size,target="x86_64-unknown-linux-gnu",producer="captured/staged source build before owner tests")
    shutil.copy2(binary,out/"artifacts/miniserve");shutil.copyfile(source/"LICENSE",out/"artifacts/MINISERVE-LICENSE")
   if label.endswith("tests"):
    summaries=re.findall(r"test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored",result["stdout"]["text"]);assert summaries and sum(int(p) for p,f,i in summaries)>0 and all(f=="0" for p,f,i in summaries),result["stdout"]["text"][-1000:];r["upstreamTestSummaries"]=summaries
  assert {n:sha(staged/n) for n in names}==before and {n:sha(source/n) for n in names}==before
  assert not run("upstream-status-after-tests",["git","status","--porcelain=v1","--untracked-files=no"],cwd=source).strip()
  r["ownerTestContext"]="Original pinned public Git clone; reviewed public test data stays outside all Patamaps captures"
  recipe=ROOT/"scripts/deployment/miniserve";owner=work/"owner";owner.mkdir();(owner/"public").mkdir()
  for n in ["prepare_bundle.py","probe.sh"]:shutil.copyfile(recipe/n,owner/n)
  (owner/"public/status.txt").write_text("patamaps-miniserve-qualified\n")
  identity="urn:qualification:miniserve:deployment"
  values={"graph.json":dict(schemaVersion="0.1.0",documentType="graph",id=identity+":source",namespace="miniserve-deployment",revision="1",entities=[dict(id=identity+":service",kind="deployment-runtime",label="Miniserve 0.35.0",attributes=dict(sourceCommit=REV,target="linux/amd64"))],mappings=[],authorities=[]),"policy.json":dict(schemaVersion="0.1.0",documentType="policy",id=identity+":policy",graph=dict(id=identity,revision="1"),mappings=[],constraints=[],evidence=[]),"projection.json":dict(schemaVersion="0.1.0",documentType="projection-spec",id=identity+":projection",select=dict(kinds=["deployment-runtime"]),slots=[]),"producer.json":r["applicationBinary"],"service.json":dict(schemaVersion="miniserve-qualified-1",nonsecret=True,target="linux/amd64",bind="127.0.0.1",port=9100,routePrefix="/qualified",documentRoot="public")}
  for n,v in values.items():write(owner/n,v)
  profile=dict(profile="patamaps-project-inputs-1",id=identity+":inputs",nonsecretInputs=True,inputs=[*values,"prepare_bundle.py","probe.sh","public/status.txt"],components=[dict(id="service",kind="deployment",root=".",entrypoints=["service.json"])],nonsecretConfiguration={},secretReferences={})
  workspace=dict(schemaVersion="0.1.0",documentType="workspace-config",id=identity,namespace="miniserve-deployment",revision="1",sources=[dict(adapter="portable-shard",id=identity+":source",path="graph.json")],packs=[],policy="policy.json",projections=[dict(path="projection.json",emissions=[dict(path="generated/service.json",language="json")])],context=dict(scope="explicit external service qualification"),evaluatedAt="2026-10-22T00:00:00Z")
  def context(label,path):
   base=work/(label+"-binary");base.mkdir();shutil.copy2(path,base/"runtime");(base/"runtime").chmod(0o755)
   sp=work/(label+"-selection.json");write(sp,dict(profile="patamaps-project-context-selection-1",id=identity+":"+label,nonsecretInputs=True,paths=["runtime"],symlinks="refuse"))
   snap=work/(label+"-snapshot");cap=native(label+"-context",["project-context-capture",sp,"--root",base,"--destination",snap])
   binding=work/(label+"-binding.json");write(binding,dict(profile="patamaps-project-build-context-1",snapshot=str(snap),digest=cap["digest"],overlays={},writablePaths=["bundle"]))
   return snap,binding
  snapshot,binding=context("built",binary);state=work/"state"
  for port in [9100,9101]:
   with socket.socket() as sock:sock.bind(("127.0.0.1",port))
  def plan(label,dig,mode="positive"):
   pp=work/(label+"-plan.json")
   write(pp,dict(profile="patamaps-project-build-1",maximumRetainedAttempts=8,project=profile,workspace=workspace,buildSteps=[command(sys.executable,["prepare_bundle.py"],inputs=["prepare_bundle.py"])],verificationSteps=[command(sys.executable,["prepare_bundle.py","--verify"],inputs=["prepare_bundle.py"]),command(cli,["elf-target-check","bundle/miniserve","--target","linux/amd64","--digest","sha256:"+dig]),command("/bin/bash",["probe.sh",mode,out/("runtime-"+label)],inputs=["probe.sh"],maximum=60000)],outputs=[dict(path="bundle",kind="tree")]))
   return pp
  good=native("native-deployment-select",["project-build",plan("positive",sha(binary)),"--source",owner,"--state",state,"--context",binding]);assert good["status"]=="selected-project-build"
  pointer=(state/"selected.json").read_bytes();candidate=state/good["attempt"]/"candidate"
  r["runtimeControls"]=(out/"runtime-positive/passed-controls.txt").read_text().splitlines();assert len(r["runtimeControls"])==8
  def refused(label,pp,bp,diagnostic):
   fail=native(label,["project-build",pp,"--source",owner,"--state",state,"--context",bp],1)
   assert fail["previousSelectionPreserved"] and (state/"selected.json").read_bytes()==pointer
   records=[json.loads(p.read_text()) for p in (state/fail["attempt"]).glob("*.json")]
   assert diagnostic in json.dumps(records),diagnostic
  original=(owner/"service.json").read_bytes();write(owner/"service.json",{**values["service.json"],"port":65536})
  refused("invalid-config-selection",plan("invalid-config",sha(binary)),binding,"SERVICE_CONFIG_LISTENER");(owner/"service.json").write_bytes(original)
  refused("wrong-listener-selection",plan("wrong-listener",sha(binary),"wrong-listener"),binding,"CONFIRMED_WRONG_LISTENER_REFUSED")
  refused("wrong-digest-selection",plan("wrong-digest","0"*64),binding,"ELF_BINDING")
  arm=work/"official-arm64";run("official-arm64",["curl","--fail","--location","--max-time","120","--max-filesize","3145728","--output",arm,"https://github.com/svenstaro/miniserve/releases/download/v0.35.0/miniserve-0.35.0-aarch64-unknown-linux-musl"]);assert sha(arm)==ARM_SHA
  _,ab=context("arm64",arm);refused("wrong-architecture-selection",plan("wrong-architecture",ARM_SHA),ab,"ELF_ARCHITECTURE")
  owner.rename(work/"owner.retained-offline");snapshot.rename(work/"built-snapshot.retained-offline")
  replay=native("offline-selected-replay",["project-build-verify",state]);assert replay["status"]=="verified-selected-build-bindings"
  artifact=candidate/"bundle/miniserve";backup=work/"qualified-runtime.retained";artifact.rename(backup);shutil.copy2(arm,artifact)
  cp=work/"stale.command.json";write(cp,command("/bin/sh",["-c","printf invoked > forbidden.marker"]))
  run("stale-before-effects",[cli,"project-exec-selected",state,cp],expected=2)
  assert not (candidate/"forbidden.marker").exists() and "PROJECT_BUILD_SELECTED_OUTPUT_CHANGED" in (out/"logs/stale-before-effects.stderr").read_text()
  artifact.rename(work/"stale-arm64.retained");backup.rename(artifact)
  cp=work/"selected-runtime.command.json";write(cp,command("/bin/bash",["probe.sh","positive",out/"runtime-selected"],inputs=["probe.sh"],maximum=60000))
  result=native("selected-runtime-repeat",["project-exec-selected",state,cp]);assert result["status"]=="completed-selected-project-command" and result["selectionPointerUnchanged"] and (state/"selected.json").read_bytes()==pointer
  archive=out/"artifacts/selected-state.tar.gz"
  with tarfile.open(archive,"w:gz") as tar:
   for name in ["driver.lock","selected.json",good["attempt"]]:tar.add(state/name,arcname="selected-state/"+name)
  failures={d.name:{f.name:json.loads(f.read_text()) for f in d.glob("*.json")} for d in (state/"attempts").iterdir() if d.name!=Path(good["attempt"]).name}
  write(out/"failed-attempt-records.json",failures)
  r["portableSelectedState"]=dict(sha256=sha(archive),bytes=archive.stat().st_size,selectionDigest=sha(state/"selected.json"),creatingCompilerDigest=sha(cli),scope="Selected attempt only; failed JSON records preserved separately")

  r.update(status="passed-source-built-miniserve-linux-deployment",sourceBuild=True,upstreamSourceUnchanged=True,capturedSourceStageMatchesFrozenInventory=True,configuredSourceAndSnapshotUnavailableReplay=True,previousSelectionPreservedOnFourRefusals=True,staleRuntimeRefusedBeforeCommand=True,restoredSelectedRuntimePassed=True,runtimeVerificationBeforeSelection=True,actualHttp=True,actualBrowser=False)
 except BaseException as e:r.update(status="failed",error=type(e).__name__+": "+str(e));save();raise
 save()
if __name__=="__main__":main()
