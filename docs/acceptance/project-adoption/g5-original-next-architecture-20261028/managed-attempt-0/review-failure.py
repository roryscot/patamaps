"""Inspect the initial failure without rerunning the workload."""
from pathlib import Path
import hashlib,json,subprocess
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=R/".tools/project-adoption/next-runtime-architecture-20261028/managed-0"
O=R/"docs/acceptance/project-adoption/g5-original-next-architecture-20261028/managed-attempt-0"
D="/Applications/Docker.app/Contents/Resources/bin/docker"
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/"preparation.json");v=read(B/"managed-result.json");c=v["controls"];r=read(B/"request-after.json")
assert p["status"]=="prepared-original-next-runtime-architecture"
assert v["status"]=="failed"and v["executorExitCode"]==1 and c["status"]=="failed"
assert c["applicationLaunches"]==0 and c["cases"]==[] and c["ownedChildCount"]==0
assert "disk.bsize*disk.blocks<=536870912n"in c["error"]
assert c["allOwnedChildrenStopped"]and c["listenerStopped"]and not c["architectureGateAccepted"]
assert r["state"]=="finished"and r["exitCode"]==1 and r["releaseProof"]["containerStopped"]and r["releaseProof"]["hostProcessGroupStopped"]
assert r["limits"]==dict(cpu=2,memoryBytes=1610612736,diskBytes=536870912)
q=r["workspace"]
js="import {MacDocker} from '/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs';import fs from 'node:fs';const r=JSON.parse(fs.readFileSync("+json.dumps(str(B/"request-after.json"))+"));const b=new MacDocker();b.config(r,{stopped:true});b.verifyWorkspace(r);console.log(JSON.stringify({filesystemBytes:r.workspace.filesystemBytes,imageBytes:r.workspace.imageBytes,mounts:b.inspect(r.containerIds[0]).Mounts}));"
observed=json.loads(subprocess.check_output(["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","--input-type=module","-e",js],text=True,timeout=60))
assert observed["filesystemBytes"]==535781376 and observed["imageBytes"]==535822336
assert len(observed["mounts"])==1 and observed["mounts"][0]["Source"]==q["work"]and observed["mounts"][0]["Destination"]=="/work"and observed["mounts"][0]["RW"]is True
assert all(sha(B/n)==h for n,h in read(B/"frozen-drivers.json").items())
summary=dict(status="verified-initial-managed-inspection-failure",reservationId=r["id"],reservationFinished=True,ownedContainerAndHostGroupStopped=True,
 executorExitCode=1,applicationLaunches=0,casesCompleted=0,architectureApplicationGateAccepted=False,
 failure="In-container statfs reported a filesystem larger than the declared512MiB; actual reported byte count was not persisted.",
 actualReportedByteCountRecorded=False,physicalHostFilesystemBytes=535781376,backingImageBytes=535822336,declaredDiskBytes=536870912,
 physicalQuotaIdentityAndOnlyWorkBindIndependentlyVerified=True,kernelLimits=c["kernelLimits"],
 preparationPassed=True,runtimeFilesRehashedInPreparation=2480,protectedInputsUnchanged=v["protectedInputsUnchanged"],
 controlsReceiptSha256=v["controlsReceiptSha256"],requestAfterSha256=sha(B/"request-after.json"),
 driverDigests=read(B/"frozen-drivers.json"),reviewerSha256=sha(__file__),filesDeleted=0,servicesStopped=0,policyChanged=False,
 productDefectEstablished=False,fullGoalComplete=False,
 nextRepair="Use existing executor host quota identity/bind checks as the physical bound; preserve and report the distinct Linux namespace statfs observation before effects. Same512MiB quota, inputs, image and other controls. Initial workload and source selection must not be rerun.")
O.mkdir(exist_ok=False)
with(O/"failure-review.json").open("x")as out:json.dump(summary,out,indent=2);out.write("\n")
for name in ["prepare.py","run-managed.py","controls.mjs"]:
 with(O/name).open("xb")as out:out.write((B/name).read_bytes())
with(O/"review-failure.py").open("xb")as out:out.write(Path(__file__).read_bytes())
print(json.dumps({k:summary[k]for k in ["status","applicationLaunches","reservationFinished","architectureApplicationGateAccepted"]}))
