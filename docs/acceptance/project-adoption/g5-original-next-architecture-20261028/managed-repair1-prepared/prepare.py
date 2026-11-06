"""Quota staging for the frozen original Next architecture increment; no application run."""
from pathlib import Path,PurePosixPath
import hashlib,io,json,os,shutil,stat,subprocess,tarfile,time,zipfile
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
BASE=Path(__file__).resolve().parent
NATIVE=BASE.parent/"native-0"
ORIGINAL=ROOT/".tools/buildctl/a96986e9-673c-4940-8d68-71e08ed53e85/mount/work"
STATE=Path("/Volumes/dev_src_case_sensitive/projects/.preservation/patamaps/build-states-envelope/original-next-node-20261028")
NODE="/Users/admin/.nvm/versions/node/v22.23.3/bin/node"
GH=ROOT/".tools/intel-gh-2.102.0-20261015/unpacked/gh_2.102.0_macOS_amd64/bin/gh"
EXECUTOR="/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs"
START=time.monotonic()
assert os.environ.get("WARGAME_STORAGE_RUN_TOKEN"),"Canonical supervisor required"
assert not (BASE/"preparation.json").exists(),"One preparation attempt only"
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write(p,v):
 with Path(p).open("x")as f:json.dump(v,f,indent=2);f.write("\n")
def bound():assert time.monotonic()-START<900,"Preparation work deadline"
def file(root,relative):
 parts=PurePosixPath(relative)
 assert isinstance(relative,str)and parts.as_posix()==relative and not parts.is_absolute()and ".."not in parts.parts and parts.parts
 assert all(stat.S_ISDIR(a.lstat().st_mode)for a in [root,*root.parents]),"Source root/ancestor not a real directory"
 p=root
 for i,part in enumerate(parts.parts):
  p=p/part;s=p.lstat()
  assert stat.S_ISREG(s.st_mode)if i==len(parts.parts)-1 else stat.S_ISDIR(s.st_mode),"Unsafe source ancestor/member"
 return p
def copy(source,target,digest,mode):
 bound();assert stat.S_ISREG(source.lstat().st_mode)and sha(source)==digest
 assert stat.S_IMODE(source.lstat().st_mode)==mode and not mode&0o7000
 target.parent.mkdir(parents=True,exist_ok=True)
 with source.open("rb")as src,target.open("xb")as dst:
  while b:=src.read(1048576):bound();dst.write(b)
 target.chmod(mode)
 assert sha(target)==digest and stat.S_IMODE(target.lstat().st_mode)==mode
 assert sha(source)==digest and stat.S_IMODE(source.lstat().st_mode)==mode
report=dict(status="failed",filesDeleted=0,servicesStopped=0,policyChanged=False,applicationRun=False,attempt=1)
try:
 native=json.loads((NATIVE/"receipt.json").read_text())
 assert native["status"]=="passed-native-original-next-runtime-selection-preparation"
 assert sha(STATE/"selected.json")=="6db82ee515f78afb0b83339ff66eb1beb3fb7e3fae3d87534aa51a0ca46d0238"
 assert not (NATIVE/"owner").exists()and not (NATIVE/"context-x86_64").exists()
 assert sha(ORIGINAL/"expected.json")=="b08b5a281185568cc48a14a533339ad49a7656bf433c060a098245ad03a88577"
 original=json.loads((ORIGINAL/"expected.json").read_text())
 assert len(original["files"])==2480 and original["links"]==[]
 assert original["linuxBuildId"]=="88oi95a5YM6PvetCCaAoU"
 assert original["linuxBuildReceiptSha256"]=="a4cb438d9e3edb3e89f2680ec8917496b381a4641b27954c326bb167099a81eb"
 rows=[];seen=set()
 for row in original["files"]:
  name=row["path"];assert name not in seen;seen.add(name)
  p=file(ORIGINAL/"app",name);assert not p.name.startswith(".env")
  assert sha(p)==row["sha256"]
  mode=stat.S_IMODE(p.lstat().st_mode);assert not mode&0o7000
  rows.append(dict(path=name,sha256=row["sha256"],mode=mode,bytes=p.stat().st_size))
 assert sum(r["bytes"]for r in rows)==86098993
 # The source manifests are private compiled outputs, not nonsecret source capture.
 protected={str(ORIGINAL/"expected.json"):sha(ORIGINAL/"expected.json"),
            str(ORIGINAL/"node"):sha(ORIGINAL/"node"),
            str(STATE/"selected.json"):sha(STATE/"selected.json"),
            str(ROOT/"target/debug/patamaps"):sha(ROOT/"target/debug/patamaps"),
            str(NATIVE/"receipt.json"):sha(NATIVE/"receipt.json")}
 assert protected[str(ROOT/"target/debug/patamaps")]=="cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355"
 x64=file(STATE,native["selection"]["attempt"]+"/candidate/runtime")
 arm=file(NATIVE,"aarch64/runtime")
 assert sha(x64)=="5796fd9700e83170bc7ddfdf7f18858c794a9f91cb39dd6f9e95060b292f2563"
 assert sha(arm)=="9189756f81aa0d5c706826f2a7763227a5abba0b5ca8c770096a25f35cf10e55"
 for p in [x64,arm]:protected[str(p)]=sha(p)
 # Reuse only the exact verifier bytes from passed initial staging. No archive redownload.
 previous=BASE.parent/"managed-0"
 previousPrep=json.loads((previous/"preparation.json").read_text())
 assert previousPrep["status"]=="prepared-original-next-runtime-architecture"
 previousReady=json.loads((previous/"prepared.json").read_text());previousWork=Path(previousReady["workspace"])
 distribution=json.loads((previous/"distribution-binding.json").read_text())
 retained=ROOT/"docs/acceptance/project-adoption/g5-retained-dynamic-next-20261028/attempt-40770841087/package/distribution.json"
 assert distribution==json.loads(retained.read_text())and distribution["engines"]==native["nativeCompiler"]["engine"]
 sourceBinary=file(previousWork,"patamaps")
 assert sha(sourceBinary)=="aaefe1394d50b3e11b1465fef4a0be1885089c8e108e317120cb09d55cf85455"
 binary=sourceBinary.read_bytes();assert len(binary)==63168200
 binarymode=stat.S_IMODE(sourceBinary.lstat().st_mode)
 protected[str(sourceBinary)]=sha(sourceBinary)
 meta=dict(digest=previousPrep["artifact"]["digest"])
 artifactBytes=previousPrep["artifact"]["bytes"]
 definition=dict(project=str(ROOT),image="sha256:69f919497cada9a8611f3de61df902d9f94bf20f84552ef5bd93125c38608ef9",phase="functional",
  limits=dict(cpu=2,memoryBytes=1610612736,diskBytes=536870912),
  outputs=[str(BASE/"managed-output")],instances=["patamaps-original-next-runtime-architecture"],source=False,
  command=["/work/node","/work/controls.mjs"])
 write(BASE/"definition.json",definition);write(BASE/"application-inputs.json",rows)
 write(BASE/"protected-inputs.json",protected);write(BASE/"distribution-binding.json",distribution)
 # Only this preparation is covered by the canonical native owner. Run later through fair queue.
 output=subprocess.check_output([NODE,EXECUTOR,"_prepare",str(BASE/"definition.json")],timeout=300,text=True)
 ready=json.loads(output.strip().splitlines()[-1]);write(BASE/"prepared.json",ready)
 report["reservationId"]=ready["prepared"];dest=Path(ready["workspace"])
 disk=os.statvfs(dest);assert disk.f_frsize*disk.f_blocks<=536870912
 assert disk.f_frsize*disk.f_bavail>=476283961,"Measured payload allowance unavailable"
 report["initialFilesystemBytes"]=disk.f_frsize*disk.f_blocks
 report["initialAvailableBytes"]=disk.f_frsize*disk.f_bavail
 for row in rows:copy(file(ORIGINAL/"app",row["path"]),dest/"app"/row["path"],row["sha256"],row["mode"])
 tools={}
 for name,source in [("node",x64),("node-arm64",arm)]:
  tools[name]=dict(sha256=sha(source),mode=stat.S_IMODE(source.lstat().st_mode))
  copy(source,dest/name,tools[name]["sha256"],tools[name]["mode"])
 with (dest/"patamaps").open("xb")as out:out.write(binary)
 (dest/"patamaps").chmod(binarymode)
 tools["patamaps"]=dict(sha256=distribution["binaryDigest"].removeprefix("sha256:"),mode=binarymode)
 assert sha(dest/"patamaps")==tools["patamaps"]["sha256"]
 controlhash=sha(BASE/"controls.mjs");copy(BASE/"controls.mjs",dest/"controls.mjs",controlhash,0o644)
 expected=dict(files=rows,tools=tools,linuxBuildId=original["linuxBuildId"],linuxBuildReceiptSha256=original["linuxBuildReceiptSha256"],
  environment=original["environment"],compilerEngine=native["nativeCompiler"]["engine"],
  deniedPaths=[str(ROOT/"Cargo.toml"),str(ORIGINAL/"app/packages/web/server.js"),str(x64)],
  selectedPointerSha256=protected[str(STATE/"selected.json")])
 assert all(Path(p).is_file()for p in expected["deniedPaths"])
 # Existing backend physical identity and sole work-bind checks are authoritative for quota.
 requestFile=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds/scheduler/requests")/(ready["prepared"]+".json")
 proofJs="""import fs from 'node:fs';import {MacDocker} from '/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs';const r=JSON.parse(fs.readFileSync(process.argv[1]));const b=new MacDocker();const d=b.config(r,{stopped:true});b.verifyWorkspace(r);const s=fs.statfsSync(r.workspace.work);console.log(JSON.stringify({requestId:r.id,definitionHash:r.definitionHash,verifiedBy:'MacDocker.config/verifyWorkspace',beforeQueue:true,source:r.source,workBindSource:d.Mounts[0].Source,workBindDestination:d.Mounts[0].Destination,workBindCount:d.Mounts.length,diskBytes:r.limits.diskBytes,filesystemBytes:s.bsize*s.blocks,imageBytes:fs.lstatSync(r.workspace.image).size,imageDevice:r.workspace.imageDevice,imageInode:r.workspace.imageInode,mountDevice:r.workspace.mountDevice}));"""
 hostQuota=json.loads(subprocess.check_output([NODE,"--input-type=module","-e",proofJs,str(requestFile)],timeout=60,text=True))
 assert hostQuota["requestId"]==ready["prepared"]and hostQuota["definitionHash"]==ready["definitionHash"]
 assert hostQuota["diskBytes"]==536870912 and 0<hostQuota["filesystemBytes"]<=536870912 and 0<hostQuota["imageBytes"]<=536870912
 assert hostQuota["source"]is False and hostQuota["workBindCount"]==1 and hostQuota["workBindSource"]==str(dest)and hostQuota["workBindDestination"]=="/work"
 write(BASE/"host-quota-before-queue.json",hostQuota)
 expected.update(hostQuota=hostQuota,reservationId=ready["prepared"],reservationDefinitionHash=ready["definitionHash"])

 write(dest/"expected.json",expected)
 for row in rows:
  p=file(ORIGINAL/"app",row["path"]);assert sha(p)==row["sha256"]and stat.S_IMODE(p.lstat().st_mode)==row["mode"]
 assert all(sha(p)==h for p,h in protected.items())
 report.update(artifactReusedFromPassedPreparation=True,hostQuotaEvidenceVerified=True,status="prepared-original-next-runtime-architecture",runtimeFiles=len(rows),runtimeBytes=sum(r["bytes"]for r in rows),
  runtimeSourceAndCopyMatched=True,protectedInputsUnchanged=True,selectedPointerUnchanged=True,
  inputManifestSha256=sha(dest/"expected.json"),controllerSha256=controlhash,
  selectedPointerSha256=protected[str(STATE/"selected.json")],artifact=dict(id=12851904399,runId=40770841087,digest=meta["digest"],bytes=artifactBytes,rawArchiveRetained=False),
  linuxBinaryDigest=distribution["binaryDigest"],driverSha256=sha(__file__),definition=definition,
  finalAvailableBytes=os.statvfs(dest).f_frsize*os.statvfs(dest).f_bavail,
  sourceRevision=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip())
except BaseException as error:
 report["error"]=type(error).__name__+": "+str(error);raise
finally:
 write(BASE/"preparation.json",report)
 print(json.dumps({k:report.get(k)for k in ["status","reservationId","runtimeFiles","applicationRun"]}),flush=True)
