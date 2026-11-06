"""Independent post-run inspection; never starts an app, compiler or container."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,os,stat,subprocess
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
BASE=ROOT/".tools/project-adoption/next-runtime-architecture-20261028/managed-1"
ORIGINAL=ROOT/".tools/buildctl/a96986e9-673c-4940-8d68-71e08ed53e85/mount/work"
STATE=Path("/Volumes/dev_src_case_sensitive/projects/.preservation/patamaps/build-states-envelope/original-next-node-20261028")
CONTROL=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds")
OUT=ROOT/"docs/acceptance/project-adoption/g5-original-next-architecture-20261028"
DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
NODE="/Users/admin/.nvm/versions/node/v22.23.3/bin/node"
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
def regular(root,name):
 q=PurePosixPath(name);assert not q.is_absolute()and".."not in q.parts and q.as_posix()==name
 p=root;assert stat.S_ISDIR(p.lstat().st_mode)
 for i,part in enumerate(q.parts):
  p/=part
  assert stat.S_ISREG(p.lstat().st_mode)if i==len(q.parts)-1 else stat.S_ISDIR(p.lstat().st_mode)
 return p
frozen=read(BASE/"frozen-drivers.json")
assert all(sha(BASE/n)==d for n,d in frozen.items())
prep=read(BASE/"preparation.json");result=read(BASE/"managed-result.json");ready=read(BASE/"prepared.json")
assert prep["status"]=="prepared-original-next-runtime-architecture"and result["status"]=="passed-managed-original-next-runtime-architecture"
assert ready["prepared"]==prep["reservationId"]==result["reservationId"]
assert result["executorExitCode"]==0 and prep["applicationRun"]is False
assert prep["driverSha256"]==frozen["prepare.py"]and result["driverSha256"]==frozen["run-managed.py"]
workspace=Path(ready["workspace"]);expected=read(workspace/"expected.json");receipt=read(workspace/"runtime-receipt.json")
assert sha(workspace/"expected.json")==prep["inputManifestSha256"]==receipt["inputManifestDigest"]
assert sha(workspace/"controls.mjs")==prep["controllerSha256"]==receipt["controllerDigest"]==frozen["controls.mjs"]
assert sha(workspace/"runtime-receipt.json")==result["controlsReceiptSha256"]and receipt==result["controls"]
assert receipt["status"]=="passed-managed-original-next-runtime-architecture"
assert receipt["architectureGateAccepted"]and receipt["stagedInputsUnchanged"]and receipt["allOwnedChildrenStopped"]and receipt["listenerStopped"]
assert receipt["applicationLaunches"]==2 and receipt["wrongArchitectureExecuted"]is False
assert not receipt["kernelExecFormatDenialClaimed"]and not receipt["automaticGenericLaunchProtection"]
assert not receipt["staleContractAccepted"]and not receipt["applicationReleaseAccepted"]
assert receipt["kernelLimits"]==dict(cpu="200000 100000",memory="1610612736",swap="0",pids="256")
assert receipt["onlyLoopbackInterface"]and receipt["rootWriteRefused"]and receipt["quotaWritePassed"]and receipt["declaredHostPathsUnavailable"]
assert receipt["hostQuotaEvidenceBound"]is True and receipt["namespaceStatfsUsedAsQuota"]is False
assert 0<int(receipt["namespaceFilesystemBytes"])
quota=read(BASE/"host-quota-before-queue.json")
assert expected["hostQuota"]==quota and quota["requestId"]==ready["prepared"]and quota["definitionHash"]==ready["definitionHash"]
assert quota["filesystemBytes"]==receipt["physicalHostFilesystemBytes"]and 0<quota["filesystemBytes"]<=536870912
assert 0<quota["imageBytes"]<=536870912 and quota["diskBytes"]==536870912
assert quota["verifiedBy"]=="MacDocker.config/verifyWorkspace"and quota["beforeQueue"]is True
assert quota["source"]is False and quota["workBindCount"]==1 and quota["workBindSource"]==str(workspace)and quota["workBindDestination"]=="/work"
checks=receipt["nativeChecks"];assert len(checks)==5
assert checks[0]["arguments"]==["engine"]and checks[0]["code"]==0 and json.loads(checks[0]["out"])==expected["compilerEngine"]
for index,name,target,machine in [(1,"node-arm64","linux/arm64",183),(2,"node","linux/amd64",62),(4,"node","linux/amd64",62)]:
 c=checks[index];digest="sha256:"+expected["tools"][name]["sha256"]
 assert c["arguments"]==["elf-target-check","/work/"+name,"--target",target,"--digest",digest]and c["code"]==0
 matched=json.loads(c["out"]);assert matched["status"]=="matched-elf-target-header"and matched["target"]==target and matched["digest"]==digest
 assert matched["header"]["machine"]==machine and matched["executionPerformed"]is False
c=checks[3];assert c["arguments"]==["elf-target-check","/work/node-arm64","--target","linux/amd64","--digest","sha256:"+expected["tools"]["node-arm64"]["sha256"]]
assert c["code"]==2 and"ELF_ARCHITECTURE"in c["err"]

cases=receipt["cases"];assert len(cases)==3
assert [v["name"]for v in cases]==["baseline-selected-x64-real-html","authentic-arm64-before-application-effects","post-refusal-selected-x64-real-html"]
for v in [cases[0],cases[2]]:
 assert v["status"]=="passed"and v["httpStatus"]==200 and 100<v["htmlBytes"]<=8388608
 assert len(v["responseDigest"])==64
v=cases[1];assert v["status"]=="refused"and v["exitCode"]==2 and v["diagnostic"]=="ELF_ARCHITECTURE"
assert v["correctDigestSupplied"]and v["applicationLaunchCountUnchanged"]and v["downstreamMarkerAbsent"]
for n in [1,2]:assert(workspace/("admitted-launch-"+str(n)+".marker")).read_text()=="admitted"
assert not(workspace/"admitted-launch-3.marker").exists()
old=read(ORIGINAL/"expected.json");assert sha(ORIGINAL/"expected.json")=="b08b5a281185568cc48a14a533339ad49a7656bf433c060a098245ad03a88577"
assert len(expected["files"])==len(old["files"])==2480 and old["links"]==[]
assert [{k:r[k]for k in ["path","sha256"]}for r in expected["files"]]==old["files"]
assert expected["environment"]==old["environment"]and expected["linuxBuildId"]==old["linuxBuildId"]=="88oi95a5YM6PvetCCaAoU"
for row in expected["files"]:
 for root in [ORIGINAL/"app",workspace/"app"]:
  p=regular(root,row["path"]);assert sha(p)==row["sha256"]and stat.S_IMODE(p.lstat().st_mode)==row["mode"]and p.stat().st_size==row["bytes"]
assert sum(r["bytes"]for r in expected["files"])==86098993
for name,digest in [("node","5796fd9700e83170bc7ddfdf7f18858c794a9f91cb39dd6f9e95060b292f2563"),("node-arm64","9189756f81aa0d5c706826f2a7763227a5abba0b5ca8c770096a25f35cf10e55"),("patamaps","aaefe1394d50b3e11b1465fef4a0be1885089c8e108e317120cb09d55cf85455")]:
 assert expected["tools"][name]["sha256"]==digest
 p=regular(workspace,name);assert sha(p)==digest and stat.S_IMODE(p.lstat().st_mode)==expected["tools"][name]["mode"]
protected=read(BASE/"protected-inputs.json");assert all(sha(p)==h for p,h in protected.items())
assert sha(STATE/"selected.json")=="6db82ee515f78afb0b83339ff66eb1beb3fb7e3fae3d87534aa51a0ca46d0238"
native=read(BASE.parent/"native-0/receipt.json")
assert sha(native["selection"]["runtimePath"])==expected["tools"]["node"]["sha256"]
assert expected["compilerEngine"]==native["nativeCompiler"]["engine"]
distribution=read(BASE/"distribution-binding.json")
assert distribution==read(OUT.parent/"g5-retained-dynamic-next-20261028/attempt-40770841087/package/distribution.json")
assert distribution["engines"]==expected["compilerEngine"]and distribution["binaryDigest"]=="sha256:"+expected["tools"]["patamaps"]["sha256"]
run=read(CONTROL/"scheduler/requests"/(ready["prepared"]+".json"))
assert run["state"]=="finished"and run["exitCode"]==0 and run["ownershipSealed"]and run["enforcement"]=="container-fixed-volume"
assert run["releaseProof"]["containerStopped"]and run["releaseProof"]["hostProcessGroupStopped"]
assert run["limits"]==dict(cpu=2,memoryBytes=1610612736,diskBytes=536870912)
assert run["kernelLimits"][:4]==["200000 100000","1610612736","0","256"]
assert run["exclusive"]is True,"No parallel activation in this scope"
for k in ["imageBytes","imageDevice","imageInode","mountDevice","filesystemBytes"]:assert quota[k]==run["workspace"][k]
assert quota["definitionHash"]==run["definitionHash"]
inventory=read(ROOT/"docs/acceptance/project-adoption/g5-retained-dynamic-next-20261028/attempt-40770841087/source-inventory.json")
inputs=[i for i in inventory if i["path"].startswith(("crates/","vendor/"))or i["path"]in ["Cargo.toml","Cargo.lock","rust-toolchain.toml"]]
assert len(inputs)==188
for item in inputs:assert "sha256:"+sha(ROOT/item["path"])==item["digest"]

js="import {MacDocker} from '/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs';import fs from 'node:fs';const r=JSON.parse(fs.readFileSync("+json.dumps(str(CONTROL/"scheduler/requests"/(ready["prepared"]+".json")))+"));const b=new MacDocker();b.config(r,{stopped:true});b.verifyWorkspace(r);console.log(JSON.stringify({configurationVerified:true,quotaIdentityVerified:true}));"
enforcement=json.loads(subprocess.check_output([NODE,"--input-type=module","-e",js],text=True,timeout=60))
assert enforcement==dict(configurationVerified=True,quotaIdentityVerified=True)
containers=[]
for cid in run["containerIds"]:
 d=json.loads(subprocess.check_output([DOCKER,"inspect",cid],text=True,timeout=30))[0]
 assert d["Image"]=="sha256:69f919497cada9a8611f3de61df902d9f94bf20f84552ef5bd93125c38608ef9"
 s=d["State"];assert s["Running"]is False and s["Paused"]is False and s["Restarting"]is False and s["Pid"]==0
 containers.append(dict(id=cid,stopped=True,image=d["Image"]))
# Review the specific preparation release, not merely absence of a current lease.
parser=argparse.ArgumentParser()
parser.add_argument("--native-request-id",required=True)
parser.add_argument("--native-guard-id",required=True)
args=parser.parse_args()
assert len(args.native_request_id)==36 and all(c in "0123456789abcdef-"for c in args.native_request_id)
request=read(CONTROL/"scheduler/requests"/(args.native_request_id+".json"))
assert str(BASE/"prepare.py")in request["command"]
assert request["state"]=="finished"and request["leaseReleaseCompleted"]is True
assert len(args.native_guard_id)==36 and all(c in "0123456789abcdef-"for c in args.native_guard_id)
guardfile=CONTROL/"runs"/args.native_guard_id/"run.json"
guard=read(guardfile)
assert guard["completed"]is True and guard["exitCode"]==0 and guard["filesDeleted"]==0
assert guard["root"]==str(ROOT)and guard["label"]==request["label"]=="patamaps"
assert guard["leaseDirectory"]==str(CONTROL)
assert request["startedAt"]<=guard["startedAt"]<=guard["finishedAt"]<=request["finishedAt"]
database=json.loads(subprocess.check_output([DOCKER,"inspect","advocates-local-advocates-db-1"],text=True,timeout=30))[0]
assert database["Id"]=="a0aad891673301454689ad960980e85efa82078e93fbd326b77c149708676d0b"and database["State"]["Running"]
initial=read(BASE.parent/"managed-0/managed-result.json")
initialPublished=read(OUT/"managed-attempt-0/failure-review.json")
initialReady=read(BASE.parent/"managed-0/prepared.json")
assert initial["status"]=="failed"and initial["executorExitCode"]==1
assert initial["controls"]["applicationLaunches"]==0 and initial["controls"]["architectureGateAccepted"]is False
assert sha(Path(initialReady["workspace"])/"runtime-receipt.json")==initialPublished["controlsReceiptSha256"]==initial["controlsReceiptSha256"]
initialRequest=read(CONTROL/"scheduler/requests/4a6ad3a1-6817-4512-85d5-6093fc32bec1.json")
assert initialRequest["state"]=="finished"and initialRequest["exitCode"]==1 and initialRequest["releaseProof"]["containerStopped"]
deniedPublished=read(OUT/"managed-repair1-prepared/admission.json")
deniedGuard=CONTROL/"runs/aedfb95d-a9f8-4c00-b2e9-0474ee69157c/run.json"
assert sha(deniedGuard)==deniedPublished["guardSha256"]
assert read(deniedGuard)["completed"]is False and read(deniedGuard)["exitCode"]==75

summary=dict(status="passed-independent-original-next-architecture-review",sourceRevision=prep["sourceRevision"],driverDigests=frozen,reviewerSha256=sha(__file__),
 nativePreparationReservation=request["id"],nativePreparationReleased=True,nativeGuardId=guardfile.parent.name,nativeGuardSha256=sha(guardfile),
 managedReservation=run["id"],managedReservationReleased=True,managedExecutorExitCode=0,managedRequestSha256=sha(CONTROL/"scheduler/requests"/(run["id"]+".json")),
 managedReceiptSha256=sha(workspace/"runtime-receipt.json"),runtimeFiles=2480,runtimeBytes=86098993,originalAndStagedFilesAndModesIndependentlyRehashed=True,
 originalExpectedManifestSha256=sha(ORIGINAL/"expected.json"),linuxBuildId=expected["linuxBuildId"],linuxBuildReceiptSha256=expected["linuxBuildReceiptSha256"],
 selectedPointerSha256=sha(STATE/"selected.json"),selectionAndProtectedInputsUnchanged=True,nodeVersion="24.11.1",
 toolDigests={k:v["sha256"]for k,v in expected["tools"].items()},linuxCompilerEngine=expected["compilerEngine"],artifact=prep["artifact"],
 cases=cases,applicationLaunches=2,wrongArchitectureExecuted=False,allOwnedChildrenStopped=True,listenerStopped=True,containers=containers,
 kernelLimits=receipt["kernelLimits"],filesystemBytes=receipt["physicalHostFilesystemBytes"],namespaceFilesystemBytes=int(receipt["namespaceFilesystemBytes"]),namespaceStatfsUsedAsQuota=False,hostQuotaAdmissionProofSha256=sha(BASE/"host-quota-before-queue.json"),relevantRustInputsMatchedB615=len(inputs),nativeVerifierCalls=5,initialManagedFailurePreserved=True,managedRepair=1,enforcement=enforcement,
 sourceMount=False,network="none",readonlyRoot=True,exclusiveFallback=True,protectedDatabaseRunning=True,
 filesDeleted=0,servicesStopped=0,policyChanged=False,applicationRebuilt=False,architectureApplicationGateAccepted=True,
 kernelExecFormatDenialClaimed=False,automaticGenericLaunchProtection=False,loaderClosureAccepted=False,originalFontTransportPristine=False,
 staleContractAccepted=False,authenticationAccepted=False,performanceAccepted=False,applicationReleaseAccepted=False,fullGoalComplete=False,
 scope="Explicit native digest/ELF target admission before actual retained Next public HTML startup, genuine ARM64 refusal before downstream application effects, and x64 post-refusal startup. Existing captured-real-font transport lineage retained; no full deployment, auth, stale-contract, performance or G0-G6 acceptance.")
assert not(OUT/"managed-architecture.json").exists()
with(OUT/"managed-architecture.json").open("x")as out:json.dump(summary,out,indent=2);out.write("\n")
for name in ["prepare.py","run-managed.py","controls.mjs"]:
 target={"prepare.py":"prepare-managed.py","run-managed.py":"run-managed.py","controls.mjs":"controls.mjs"}[name]
 with(OUT/target).open("xb")as out:out.write((BASE/name).read_bytes())
with(OUT/"review-managed.py").open("xb")as out:out.write(Path(__file__).read_bytes())
print(json.dumps({k:summary[k]for k in ["status","runtimeFiles","managedReservationReleased","architectureApplicationGateAccepted","fullGoalComplete"]}))
