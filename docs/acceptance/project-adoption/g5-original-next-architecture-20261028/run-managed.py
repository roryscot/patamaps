"""Separately queued managed run; never nested under the native preparation owner."""
from pathlib import Path
import hashlib,json,os,subprocess,time
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
BASE=Path(__file__).resolve().parent
NODE="/Users/admin/.nvm/versions/node/v22.23.3/bin/node"
EXECUTOR="/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs"
BUILDCTL="/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs"
DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
assert not os.environ.get("WARGAME_STORAGE_RUN_TOKEN"),"Managed run must queue separately"
assert not (BASE/"managed-result.json").exists(),"One managed run only"
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write(p,v):
 with Path(p).open("x")as f:json.dump(v,f,indent=2);f.write("\n")
prep=json.loads((BASE/"preparation.json").read_text());assert prep["status"]=="prepared-original-next-runtime-architecture"
assert sha(BASE/"prepare.py")==prep["driverSha256"]and sha(BASE/"controls.mjs")==prep["controllerSha256"]
ready=json.loads((BASE/"prepared.json").read_text());assert ready["prepared"]==prep["reservationId"]
workspace=Path(ready["workspace"])
assert sha(workspace/"expected.json")==prep["inputManifestSha256"]
protected=json.loads((BASE/"protected-inputs.json").read_text());assert all(sha(p)==h for p,h in protected.items())
js="import {Scheduler} from "+json.dumps(BUILDCTL)+";const s=new Scheduler();console.log(JSON.stringify({directory:s.directory,request:s.requests().find(x=>x.id==="+json.dumps(ready["prepared"])+"),lease:undefined}));"
current=json.loads(subprocess.check_output([NODE,"--input-type=module","-e",js],text=True,timeout=30))
directory=Path(current["directory"]);assert current["request"]["state"]=="prepared"
assert not (directory/"active-run").exists(),"Preparation owner has not released; wait, do not run"
result=dict(status="failed",reservationId=ready["prepared"],filesDeleted=0,servicesStopped=0,policyChanged=False,architectureGateAccepted=False,staleContractAccepted=False,applicationReleaseAccepted=False)
try:
 with (BASE/"managed.stdout.log").open("xb")as out,(BASE/"managed.stderr.log").open("xb")as err:
  completed=subprocess.run([NODE,EXECUTOR,"run",ready["prepared"]],cwd=ROOT,stdout=out,stderr=err)
 result["executorExitCode"]=completed.returncode
 result["executorStdoutSha256"]=sha(BASE/"managed.stdout.log");result["executorStderrSha256"]=sha(BASE/"managed.stderr.log")
 run=json.loads((directory/"scheduler/requests"/(ready["prepared"]+".json")).read_text())
 write(BASE/"request-after.json",run)
 result["reservationState"]=run["state"]
 containers=[]
 for cid in run["containerIds"]:
  d=json.loads(subprocess.check_output([DOCKER,"inspect",cid],text=True,timeout=30))[0]
  write(BASE/("container-"+cid+".json"),d)
  s=d["State"];assert not s["Running"]and not s["Paused"]and not s["Restarting"]and s["Pid"]==0
  containers.append(dict(id=cid,running=False,paused=False,restarting=False,pid=0,image=d["Image"]))
 result["containersConfirmedStopped"]=containers
 result["protectedInputsUnchanged"]=all(sha(p)==h for p,h in protected.items())
 assert result["protectedInputsUnchanged"]
 f=workspace/"runtime-receipt.json"
 if f.exists():
  controls=json.loads(f.read_text());result["controlsReceiptSha256"]=sha(f)
  result["controls"]=controls
 assert completed.returncode==0,"Managed executor did not pass; preserve failed outputs"
 assert run["state"]=="finished"and run["releaseProof"]["containerStopped"]and run["releaseProof"]["hostProcessGroupStopped"]
 assert controls["status"]=="passed-managed-original-next-runtime-architecture"
 assert controls["architectureGateAccepted"]and controls["allOwnedChildrenStopped"]and controls["listenerStopped"]
 assert controls["stagedInputsUnchanged"]and controls["applicationLaunches"]==2 and not controls["wrongArchitectureExecuted"]
 assert controls["inputManifestDigest"]==prep["inputManifestSha256"]and controls["controllerDigest"]==prep["controllerSha256"]
 assert [v["name"]for v in controls["cases"]]==["baseline-selected-x64-real-html","authentic-arm64-before-application-effects","post-refusal-selected-x64-real-html"]
 # Independent host verification of retained application members, modes and tools.
 expected=json.loads((workspace/"expected.json").read_text())
 for row in expected["files"]:
  for p in [workspace/"app"/row["path"],Path("/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/buildctl/a96986e9-673c-4940-8d68-71e08ed53e85/mount/work/app")/row["path"]]:
   assert p.is_file()and not p.is_symlink()and sha(p)==row["sha256"]and p.stat().st_mode&0o7777==row["mode"]
 for name,v in expected["tools"].items():assert sha(workspace/name)==v["sha256"]and(workspace/name).stat().st_mode&0o7777==v["mode"]
 result.update(status="passed-managed-original-next-runtime-architecture",architectureGateAccepted=True,runtimeFilesRehashed=len(expected["files"]),selectionPointerUnchanged=True)
except BaseException as error:
 result["error"]=type(error).__name__+": "+str(error);raise
finally:
 result["driverSha256"]=sha(__file__)
 write(BASE/"managed-result.json",result)
 print(json.dumps({k:result.get(k)for k in ["status","reservationId","executorExitCode","reservationState","architectureGateAccepted"]}),flush=True)
