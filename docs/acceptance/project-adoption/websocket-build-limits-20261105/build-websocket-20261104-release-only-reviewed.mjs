import fs from'node:fs';import{createHash}from'node:crypto';import{execFileSync}from'node:child_process';
import{Scheduler,alive,workloadStopped}from'/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import{releaseLease}from'/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs';
const D='/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/owner-auth-endpoint-20261029/build-websocket-20261104/stopped-reservation-recovery',C='/Users/admin/Documents/Codex/.storage-control/heavy-builds',id='23f3439b-70e4-4f07-89be-e3e25b810c16';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),sha=p=>'sha256:'+createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const proof=read(D+'/RECOVERY_PLAN.json'),scheduler=new Scheduler(C),file=scheduler.file(id);
if(proof.reservationId!==id||proof.observations.length!==3||!(proof.previousSelectedArtifactFilesRehashed===7446&&proof.sourceInputsRehashed===943&&proof.newSelectionAbsent))throw Error('RECOVERY_SCOPE');
const req=read(file),owner=read(C+'/active-run/owner.json');
function check(){
 for(const[p,h]of Object.entries(proof.originalPreimages))if(sha(p)!==h)throw Error('RECOVERY_PREIMAGE_CHANGED');
 if(req.state!=='needs-review'||owner.requestId!==id||owner.pid!==95049||alive(95049)!==false||!proof.processGroups.every(workloadStopped))throw Error('RECOVERY_NOT_STOPPED');
 const running=execFileSync('/Applications/Docker.app/Contents/Resources/bin/docker',['ps','--no-trunc','--format','{{.ID}}'],{encoding:'utf8',timeout:15000}).trim().split('\n');
 if(JSON.stringify(running)!==JSON.stringify(proof.observations.at(-1).runningContainers))throw Error('RECOVERY_CONTAINER_CHANGED');
}
check();
const archived=scheduler.transaction(()=>{
 check();const destination=releaseLease(owner,C);
 const updated={...req,state:'finished',finishedAt:new Date().toISOString(),heartbeat:new Date().toISOString(),leaseReleaseCompleted:true,progress:'Manual recovery after three complete stopped-process/container checks; original frontend quota failure retained',manualStoppedRecovery:{proof:D+'/RECOVERY_PLAN.json',originalRequestSha256:proof.originalPreimages[file],leaseArchive:destination,automaticWorkloadAcceptance:false}};
 fs.writeFileSync(file,JSON.stringify(updated,null,2)+'\n',{mode:0o600});return destination;
});
const result={status:'recovered-only-stopped-websocket-build-reservation',reservationId:id,archivedLease:archived,originalQuotaFailurePreserved:true,automaticWorkloadAcceptance:false,filesDeleted:0,installedGuardChanged:false};
fs.writeFileSync(D+'/result.json',JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});
fs.writeFileSync(archived+'/manual-recovery.json',JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});
console.log(JSON.stringify({recoveredOnly:id,threeStoppedChecks:true,previousSelectionsAndSourcesUnchanged:true,originalFailurePreserved:true}));
