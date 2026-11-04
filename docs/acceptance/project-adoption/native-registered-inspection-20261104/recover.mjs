import {readFileSync,existsSync,mkdirSync,writeFileSync,renameSync}from'node:fs';
import {createHash,randomUUID}from'node:crypto';
import {Scheduler,alive,workloadStopped,nativeFinalizationPending}from'/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
const base='/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-registered-inspection-20261028/retry-proposal-1/ownership-change-recovery-20261104';
const control='/Users/admin/Documents/Codex/.storage-control/heavy-builds';
const id='df47f504-2503-45cc-9f44-f7f02d6bc2b8';
const sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const proof=JSON.parse(readFileSync(base+'/review-1/stop-proof.json'));
if(proof.requestId!==id||proof.observations.length!==2||!proof.registeredChannelsClosed||!proof.sharedLeaseAlreadyMissing)throw Error('Incomplete frozen stop proof');
if(sha(base+'/RECOVERY_PLAN.md')!==proof.recoveryPlanSha256||sha(base+'/audit-v2.py')!==proof.observerSha256)throw Error('Recovery scope changed');
const scheduler=new Scheduler();
const filename=scheduler.file(id);
let result;
for(let attempt=0;attempt<100;attempt++){
 try{
 result=scheduler.transaction(()=>{
  const request=JSON.parse(readFileSync(filename));
  if(sha(filename)!==proof.originalRequestSha256||request.state!=='running'||request.owner.pid!==42989||request.processGroup!==43292||request.ownershipSealed!==true)throw Error('Request preimage changed');
  if(proof.ownedPids.some(pid=>alive(pid)!==false)||proof.ownedGroups.some(group=>!workloadStopped(group)))throw Error('Owned process identity remains live or uncertain');
  if(existsSync(control+'/active-run'))throw Error('Shared lease appeared during review');
  if(scheduler.requests().some(r=>r.id!==id&&(['running','needs-review','preparing'].includes(r.state)||nativeFinalizationPending(r))))throw Error('Another active reservation exists');
  const archive=control+'/scheduler/recoveries/native-missing-lease-'+id+'-'+randomUUID();
  mkdirSync(archive,{mode:0o700});
  writeFileSync(archive+'/request.original.json',readFileSync(filename),{flag:'wx',mode:0o600});
  writeFileSync(archive+'/stop-proof.json',readFileSync(base+'/review-1/stop-proof.json'),{flag:'wx',mode:0o600});
  const now=new Date().toISOString();
  const recovery={kind:'one-off-reviewed-native-missing-lease-recovery',requestId:id,recoveredAtUtc:now,authorization:'Owner2026-11-04 delegated continuation approvals/checks; agent-selected exact recovery scope',originalRequestSha256:proof.originalRequestSha256,stopProofSha256:sha(base+'/review-1/stop-proof.json'),archive,compatibilityLeaseAlreadyMissing:true,leaseArchiveUnavailable:true,failedSupervisorExitCode:75,failedTestExitCode:1,automaticReleaseQualified:false,policyChanged:false,filesDeleted:0,servicesInterrupted:0};
  writeFileSync(archive+'/recovery.json',JSON.stringify(recovery,null,2)+'\n',{flag:'wx',mode:0o600});
  request.state='finished';request.finishedAt=now;request.heartbeat=now;request.leaseReleaseCompleted=true;
  request.exitCode=75;request.progress='One-off reviewed stop; compatibility lease already missing; failed exit75 preserved';
  request.operatorRecovery=recovery;
  const staging=filename+'.reviewed-'+randomUUID()+'.staging';
  writeFileSync(staging,JSON.stringify(request,null,2)+'\n',{flag:'wx',mode:0o600});renameSync(staging,filename);
  writeFileSync(base+'/recovery-result.json',JSON.stringify(recovery,null,2)+'\n',{flag:'wx',mode:0o600});
  return recovery;
 });
 break;
 }catch(error){if(error.code!=='BUSY')throw error;await new Promise(resolve=>setTimeout(resolve,100));}
}
if(!result)throw Error('Could not obtain canonical scheduler transaction');
console.log(JSON.stringify({requestId:id,state:JSON.parse(readFileSync(filename)).state,capacityReleased:true,compatibilityLeaseWasAlreadyMissing:true,failedExit75Preserved:true,filesDeleted:0,servicesInterrupted:0}));
