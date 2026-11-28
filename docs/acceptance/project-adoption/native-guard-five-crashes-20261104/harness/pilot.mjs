import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const B=path.dirname(fileURLToPath(import.meta.url));
const R='/Volumes/dev_src_case_sensitive/projects/patamaps';
const E=path.join(R,'.tools/native-guard-candidate-parent-watch-20261104/engine');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});
const sha=p=>'sha256:'+createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const manifest=read('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-shared-runtime-log-scope-20261104/frozen.json');
for(const [p,h]of Object.entries(manifest.inputs))if(sha(p)!==h)throw Error('PILOT_FROZEN_INPUT_CHANGED');
for(const k of ['WARGAME_STORAGE_RUN_TOKEN','WARGAME_STORAGE_OWNER_PID'])delete process.env[k];
process.env.WARGAME_STORAGE_CONTROL_DIR=path.join(B,'private-control');
process.env.WARGAME_STORAGE_LEASE_DIR=path.join(B,'private-lease');
const registered=await import(pathToFileURL(path.join(E,'native_inspection_registration.mjs')));
const bridge=await import(pathToFileURL(path.join(E,'native_registered_guard_candidate.mjs')));
const engine=await import(pathToFileURL(path.join(E,'guarded-run.mjs')));
const scheduler=await import(pathToFileURL(path.join(E,'buildctl.mjs')));
const config=read('/Users/admin/Documents/Codex/storage-safeguards/projects.json');
const installed=await import(pathToFileURL(config.engine));
const approved=installed.loadPolicy();
if(approved.maximumRunGrowthBytes!==4000000000||approved.reserveFreeBytes!==500000000||approved.maximumRetainedBytes!==100000000000)throw Error('PILOT_POLICY_CHANGED');
const policy={...approved,maximumRunGrowthBytes:536870912};
const supplied=read(path.join(B,'inputs.json'));
fs.mkdirSync(path.join(B,'stage'),{mode:0o700});
const handle=registered.stageInspectionRegistration({directory:path.join(B,'stage/registration'),archive:supplied.archive,native:supplied.native});
save(path.join(B,'registration-binding.json'),registered.verifyInspectionRegistration(handle));
const project=path.join(B,'test-project');fs.mkdirSync(project,{mode:0o700});
const tmp=path.join(B,'tmp');fs.mkdirSync(tmp,{mode:0o700});
const rows=[];
const identities=s=>[s.controllerIdentity,...s.calls.flatMap(c=>[c.guardianIdentity,c.nativeIdentity])].filter(Boolean);
async function cleanup(root){
 const statusFile=path.join(root,'supervisor-status.json');
 if(!fs.existsSync(statusFile))return {notLaunched:true};
 const status=read(statusFile),ids=identities(status);
 const unique=[...new Map(ids.map(x=>[x.pid,x])).values()];
 if(!unique.length)throw Error('PILOT_NO_IDENTITIES_FOR_CLEANUP');
 const value=JSON.parse(execFileSync(path.join(handle.directory,'runtime/python/bin/python3.13'),['-I','-S','-B',path.join(handle.directory,'source/native_registered_controller.py'),'--stop',JSON.stringify(unique)],{encoding:'utf8',timeout:30000,maxBuffer:65536}));
 const probe=registered.probeRegisteredInspection(handle,unique.map(x=>x.pid));
 if(!value.confirmed||!Object.values(probe.groupsStopped).every(x=>x===true))throw Error('PILOT_CLEANUP_UNCONFIRMED');
 return {confirmed:true,groups:unique.map(x=>x.pid)};
}
async function run(name,operation,action){
 const run=path.join(B,name);fs.mkdirSync(run,{mode:0o700});
 const control=path.join(B,name+'-control'),lease=path.join(B,name+'-lease');
 const inputs=operation==='engine'?{}:supplied.inputs;
 const cap=bridge.createRegisteredGuardInvocation(handle,{operation,runRoot:run,inputs});
 let cancelAt=null,cancelObserved=null,cancelTimer=null,deadlineTimer=null,injectionFailure=null;
 const began=Date.now();
 try{
  deadlineTimer=setTimeout(()=>process.kill(process.pid,'SIGTERM'),90000);
  if(action&&action!=='parent-loss')cancelTimer=setInterval(()=>{
   const p=path.join(run,'supervisor-status.json');
   if(!fs.existsSync(p))return;
   const s=read(p);
   const call=s.calls.find(x=>x.registrationKnown===true&&x.nativeIdentity?.pid>1);
   if(call){
    const probe=registered.probeRegisteredInspection(handle,[call.nativeIdentity.pid]);
    if(JSON.stringify(probe.identities[call.nativeIdentity.pid])!==JSON.stringify(call.nativeIdentity))return;
    cancelObserved=s;cancelAt=Date.now();clearInterval(cancelTimer);
    save(path.join(run,'fault-injection.json'),{action,atMs:cancelAt,status:s,nativeLiveIdentityConfirmed:true});
    try{
     if(action==='cancel')process.kill(process.pid,'SIGTERM');
     else{
      const target=action==='controller-crash'?s.controllerIdentity:call.guardianIdentity;
      execFileSync(path.join(handle.directory,'runtime/python/bin/python3.13'),[path.join('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-shared-runtime-log-scope-20261104','inject-owned-crash.py'),path.join(handle.directory,'source'),JSON.stringify(target)],{encoding:'utf8',timeout:15000,maxBuffer:65536});
     }
    }catch(error){injectionFailure=error.name;process.kill(process.pid,'SIGTERM');}
   }
  },20);
  const code=await engine.guardedCommand('native-candidate-'+name,process.execPath,[fileURLToPath(import.meta.url),name],{
   directory:control,leaseDirectory:lease,childControlDirectory:control,root:project,cwd:project,temporary:tmp,
   environment:{...process.env},policy,retentionRoots:()=>[B],nativeInspection:cap
  });
  clearInterval(cancelTimer);clearTimeout(deadlineTimer);
  const status=read(path.join(run,'supervisor-status.json'));
  const requests=fs.readdirSync(path.join(lease,'scheduler/requests')).filter(x=>x.endsWith('.json')).map(x=>read(path.join(lease,'scheduler/requests',x)));
  if(requests.length!==1||requests[0].state!=='finished'||requests[0].leaseReleaseCompleted!==true)throw Error('PILOT_RESERVATION_NOT_RELEASED');
  const journal=fs.readFileSync(path.join(run,'supervisor-journal.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  const proof=registered.probeRegisteredInspection(handle,identities(status).map(x=>x.pid));
  if(!Object.values(proof.groupsStopped).every(x=>x===true)||!status.channelClosed||status.failure!==null)throw Error('PILOT_CLOSED_PROOF_FAILED');
  if(action==='parent-loss'){
   const records=fs.readdirSync(path.join(lease,'runs')).map(x=>path.join(lease,'runs',x,'run.json')).filter(fs.existsSync);
   if(records.length!==1)throw Error('PARENT_GUARD_RECORD_COUNT');
   const proof=read(records[0]);
   if(code!==75||proof.stopReason!=='Storage guard: native command owner parent stopped; stopping registered inspection'||!proof.registeredNativeStop?.safeToRelease)throw Error('PARENT_LOSS_NOT_INDEPENDENTLY_CONFIRMED');
  }else if(action&&(!cancelAt||Date.now()-cancelAt>60000||(action==='cancel'?code!==75:code===0)||injectionFailure))throw Error('PILOT_ACTION_NOT_ACCEPTED');
  if(!action&&code!==0)throw Error('PILOT_NORMAL_NOT_ACCEPTED');
  rows.push({name,code,action:action??null,injectionFailure,durationMs:Date.now()-began,cancelObserved:cancelAt!==null,cancelToReleaseMs:cancelAt===null?null:Date.now()-cancelAt,reservation:requests[0].id,reservationReleased:true,registeredFrames:journal.length,groupsStopped:identities(status).length,channelClosed:true,registrationBinding:registered.verifyInspectionRegistration(handle)});
  save(path.join(run,'pilot-review.json'),rows.at(-1));
 }finally{
  clearInterval(cancelTimer);clearTimeout(deadlineTimer);
  save(path.join(run,'independent-cleanup.json'),await cleanup(run));
 }
}
let failure=null;
try{
 await run('normal-engine','engine',null);
 await run('cancel-unchanged','unchanged-build','cancel');
 await run('controller-crash','unchanged-build','controller-crash');
 await run('guardian-crash','unchanged-build','guardian-crash');
 await run('owner-parent-death','unchanged-build','parent-loss');
}catch(error){failure={type:error.name,code:typeof error.message==='string'&&/^[A-Z0-9_]+$/.test(error.message)?error.message:'PRIVATE_DIAGNOSTIC_REQUIRED'};}
finally{
 save(path.join(B,'pilot-result.json'),{status:failure?'failed-staged-native-crash-suite':'passed-staged-native-crash-suite',rows,failure,installedGuardUnchanged:sha(config.engine)===manifest.installedGuardDigest,fullTenCaseSuiteAccepted:false,parallelActivated:false,installed:false,filesDeleted:0});
}
if(failure)process.exitCode=1;
