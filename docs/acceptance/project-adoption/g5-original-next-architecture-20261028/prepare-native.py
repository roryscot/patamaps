"""Native preparation only for the frozen actual-owner runtime architecture plan."""
from pathlib import Path,PurePosixPath
import hashlib,json,os,shutil,subprocess,sys,tarfile,time,urllib.request
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
BASE=Path(__file__).resolve().parent
assert os.environ.get("WARGAME_STORAGE_RUN_TOKEN"),"Canonical supervisor required"
sys.path.insert(0,str(ROOT/"scripts"))
from project_watch import stop
CLI=ROOT/"target/debug/patamaps"
CLI_DIGEST="sha256:cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355"
X64_DIGEST="sha256:5796fd9700e83170bc7ddfdf7f18858c794a9f91cb39dd6f9e95060b292f2563"
ARM_ARCHIVE_DIGEST="sha256:6b0863fb9f627bf4a6c5948dce1de4398174a2e05dbe717503d828e211ca01f0"
ORIGINAL=ROOT/".tools/buildctl/a96986e9-673c-4940-8d68-71e08ed53e85/mount/work"
STATE=Path("/Volumes/dev_src_case_sensitive/projects/.preservation/patamaps/build-states-envelope/original-next-node-20261028")
START=time.monotonic()
def digest(p):
 with Path(p).open("rb")as f:return "sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
def write(p,v):
 with Path(p).open("x")as f:json.dump(v,f,indent=2);f.write("\n")
report=dict(status="running-native-preparation",commands=[],filesDeleted=0,applicationRun=False,qualificationAccepted=False,attempt=0)
def save():(BASE/"receipt.json").write_text(json.dumps(report,indent=2)+"\n")
def capacity():assert time.monotonic()-START<900,"Native preparation work deadline"
def call(label,argv,expected=0,env=None):
 capacity();out=BASE/(label+".stdout");err=BASE/(label+".stderr")
 with out.open("xb")as stdout,err.open("xb")as stderr:
  child=subprocess.Popen([sys.executable,"-B",str(ROOT/"scripts/project_watch.py"),"__guard",*map(str,argv)],cwd=BASE,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
  try:
   began=time.monotonic()
   while child.poll()is None:
    capacity();assert time.monotonic()-began<300,"Command deadline"
    assert out.stat().st_size<=1048576 and err.stat().st_size<=1048576,"Log bound"
    time.sleep(.2)
   code=child.returncode
  finally:stop(child)
 report["commands"].append(dict(label=label,exitCode=code,expectedExitCode=expected,stdoutDigest=digest(out),stderrDigest=digest(err)));save()
 assert code==expected,(label,code)
 return json.loads(out.read_text())
try:
 assert not (BASE/"receipt.json").exists()
 assert digest(CLI)==CLI_DIGEST
 protected={ORIGINAL/"expected.json":"sha256:b08b5a281185568cc48a14a533339ad49a7656bf433c060a098245ad03a88577",
            ORIGINAL/"node":X64_DIGEST}
 for p,d in protected.items():assert p.is_file()and not p.is_symlink()and digest(p)==d
 expected=json.loads((ORIGINAL/"expected.json").read_text())
 assert len(expected["files"])==2480 and not expected["links"]
 assert expected["linuxBuildId"]=="88oi95a5YM6PvetCCaAoU"
 assert expected["linuxBuildReceiptSha256"]=="a4cb438d9e3edb3e89f2680ec8917496b381a4641b27954c326bb167099a81eb"
 engine=call("native-engine",[CLI,"engine"])
 assert engine["compiler"]=="sha256:7261d65205d62c538ba0b2b62444e8acd67acf4ad5b4d43f7bc9f39fc4d118a2"
 assert engine["workspace"]=="sha256:f086e884c32a6cbf035e2f815e062ffbc466cc18f440ff16ecc847698ea7ae59"
 report["nativeCompiler"]=dict(digest=CLI_DIGEST,engine=engine)
 archive=BASE/"node-v24.11.1-linux-arm64.tar.xz"
 with urllib.request.urlopen("https://nodejs.org/dist/v24.11.1/"+archive.name,timeout=120)as response,archive.open("xb")as out:
  count=0
  while chunk:=response.read(65536):
   capacity();count+=len(chunk);assert count<=80*1024**2;out.write(chunk)
 assert digest(archive)==ARM_ARCHIVE_DIGEST
 roots={a:BASE/a for a in ["x86_64","aarch64"]}
 for p in roots.values():p.mkdir()
 shutil.copy2(ORIGINAL/"node",roots["x86_64"]/"runtime")
 assert digest(roots["x86_64"]/"runtime")==X64_DIGEST
 matches=0;expanded=0;members=0
 with tarfile.open(archive,"r|xz")as tar:
  for member in tar:
   capacity();members+=1;expanded+=member.size
   assert members<16000 and expanded<=1024**3
   path=PurePosixPath(member.name);assert not path.is_absolute()and".."not in path.parts
   if member.name!="node-v24.11.1-linux-arm64/bin/node":continue
   matches+=1;assert matches==1 and member.isfile()and 64<=member.size<=256*1024**2
   stream=tar.extractfile(member);destination=roots["aarch64"]/"runtime"
   with destination.open("xb")as out:
    copied=0
    while chunk:=stream.read(65536):capacity();copied+=len(chunk);assert copied<=member.size;out.write(chunk)
   assert copied==member.size;destination.chmod(member.mode&0o777)
 assert matches==1
 digests={a:digest(p/"runtime")for a,p in roots.items()}
 report["runtimeInputs"]=dict(version="24.11.1",digests=digests,armArchiveDigest=ARM_ARCHIVE_DIGEST,armMember="node-v24.11.1-linux-arm64/bin/node",armExecuted=False)
 for arch,target in [("x86_64","linux/amd64"),("aarch64","linux/arm64")]:
  result=call(arch+"-matching-target",[CLI,"elf-target-check",roots[arch]/"runtime","--target",target,"--digest",digests[arch]])
  assert result["status"]=="matched-elf-target-header"and result["executionPerformed"]is False
  assert result["digest"]==digests[arch]and result["target"]==target
 owner=BASE/"owner";owner.mkdir();identity="urn:qualification:original-next:node-runtime"
 values={
  "graph.json":dict(schemaVersion="0.1.0",documentType="graph",id=identity+":source",namespace="original-next-runtime",revision="1",entities=[dict(id=identity+":runtime",kind="deployment-runtime",label="Actual original-owner Node runtime",attributes=dict(requiredTarget="linux/amd64",version="24.11.1",linuxBuildId=expected["linuxBuildId"],linuxBuildReceiptDigest="sha256:"+expected["linuxBuildReceiptSha256"]))],mappings=[],authorities=[]),
  "policy.json":dict(schemaVersion="0.1.0",documentType="policy",id=identity+":policy",graph=dict(id=identity,revision="1"),mappings=[],constraints=[],evidence=[]),
  "projection.json":dict(schemaVersion="0.1.0",documentType="projection-spec",id=identity+":projection",select=dict(kinds=["deployment-runtime"]),slots=[]),
  "producer.json":dict(originalOwnerCommit="c61d51a57120abbbca65d4cb4a432c1cef9343bb",nodeVersion="24.11.1",runtimeDigests=digests,originalRuntimeManifestDigest=protected[ORIGINAL/"expected.json"],armArchiveDigest=ARM_ARCHIVE_DIGEST)}
 for n,v in values.items():write(owner/n,v)
 profile=dict(profile="patamaps-project-inputs-1",id=identity+":inputs",nonsecretInputs=True,inputs=list(values),components=[dict(id="runtime",kind="deployment",root=".",entrypoints=["producer.json"])],nonsecretConfiguration={},secretReferences={})
 workspace=dict(schemaVersion="0.1.0",documentType="workspace-config",id=identity,namespace="original-next-runtime",revision="1",sources=[dict(adapter="portable-shard",id=identity+":source",path="graph.json")],packs=[],policy="policy.json",projections=[dict(path="projection.json",emissions=[dict(path="generated/runtime-observation.json",language="json")])],context=dict(scope="owner-declared existing runtime selection; no compilation or activation"),evaluatedAt="2026-10-28T00:00:00Z")
 def command(exe,args):return dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences={},invocation=dict(executable=str(exe),arguments=args,codeInputs=[],bounds=dict(maximumElapsedMs=60000,maximumStdoutBytes=65536,maximumStderrBytes=65536)))
 assert STATE.parent.is_dir()and not STATE.exists()
 pointer=None
 for arch in ["x86_64","aarch64"]:
  definition=dict(profile="patamaps-project-context-selection-1",id=identity+":"+arch,nonsecretInputs=True,paths=["runtime"],symlinks="refuse")
  selected=BASE/(arch+"-selection.json");write(selected,definition);snapshot=BASE/("context-"+arch)
  captured=call(arch+"-context-capture",[CLI,"project-context-capture",selected,"--root",roots[arch],"--destination",snapshot])
  binding=dict(profile="patamaps-project-build-context-1",snapshot=str(snapshot),digest=captured["digest"],overlays={},writablePaths=[])
  bp=BASE/(arch+"-binding.json");write(bp,binding)
  plan=dict(profile="patamaps-project-build-1",maximumRetainedAttempts=8,project=profile,workspace=workspace,buildSteps=[command("/usr/bin/true",[])],verificationSteps=[command(CLI,["elf-target-check","runtime","--target","linux/amd64","--digest",digests[arch]])],outputs=[dict(path="runtime",kind="file")])
  pp=BASE/(arch+"-plan.json");write(pp,plan)
  result=call(arch+"-retained-selection",[CLI,"project-build",pp,"--source",owner,"--state",STATE,"--context",bp],0 if arch=="x86_64"else 1)
  if arch=="x86_64":
   assert result["status"]=="selected-project-build";pointer=(STATE/"selected.json").read_bytes()
   candidate=STATE/json.loads(pointer)["attempt"]/"candidate/runtime";assert digest(candidate)==digests[arch]
   report["selection"]=dict(state=str(STATE),pointerDigest="sha256:"+hashlib.sha256(pointer).hexdigest(),runtimeDigest=digests[arch],runtimePath=str(candidate),attempt=result["attempt"])
  else:
   assert result["status"]=="refused-project-build"and result["previousSelectionPreserved"]is True
   assert (STATE/"selected.json").read_bytes()==pointer
   negative=json.loads((STATE/result["attempt"]/"verify-001.json").read_text())
   assert negative["exitCode"]==2 and"ELF_ARCHITECTURE"in negative["stderr"]["text"]
   report["authenticArmRefusal"]=dict(exitCode=2,diagnostic="ELF_ARCHITECTURE",previousPointerUnchanged=True,correctDigestSupplied=digests[arch],armExecuted=False,attempt=result["attempt"])
 owner.rename(BASE/"owner.retained-offline");(BASE/"context-x86_64").rename(BASE/"context-x86_64.retained-offline")
 offline=call("selected-offline-replay",[CLI,"project-build-verify",STATE],env={"PATH":"","HOME":str(BASE)})
 assert offline["status"]=="verified-selected-build-bindings"
 assert (STATE/"selected.json").read_bytes()==pointer and digest(candidate)==digests["x86_64"]
 for p,d in protected.items():assert digest(p)==d
 assert digest(CLI)==CLI_DIGEST
 report.update(status="passed-native-original-next-runtime-selection-preparation",sourceAndSnapshotUnavailableReplay=True,originalRuntimeInputsUnchanged=True,nativeCompilerUnchanged=True,nativeSelectionSubcontrolsPassed=True,managedApplicationRun=False,managedPreparationRun=False,applicationQualificationAccepted=False)
except BaseException as error:
 report.update(status="failed-native-original-next-runtime-preparation",error=type(error).__name__+": "+str(error));raise
finally:
 report["driverDigest"]=digest(Path(__file__));report["sourceRevision"]=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip();save();print(json.dumps(report,indent=2),flush=True)
