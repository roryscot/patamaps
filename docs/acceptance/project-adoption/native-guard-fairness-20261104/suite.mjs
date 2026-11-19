import fs from 'node:fs';
import path from 'node:path';
import cp from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const B=path.dirname(fileURLToPath(import.meta.url)),R='/Volumes/dev_src_case_sensitive/projects/patamaps',E=path.join(R,'.tools/native-guard-candidate-parent-watch-20261104/engine');
const PY=path.join(R,'.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});
const need=(x,m)=>{if(!x)throw Error(m);};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const sha=p=>'sha256:'+createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function until(fn,ms=30000){const end=Date.now()+ms;while(Date.now()<end){const v=fn();if(v)return v;await pause(25);}throw Error('FAIR_SUITE_WAIT_DEADLINE');}
const [mode,group,who,countArg]=process.argv.slice(2);
if(mode==='payload'){
 const dir=path.join(B,group);
 save(path.join(dir,who+'.payload.json'),{pid:process.pid,parentPid:process.ppid,startedAt:new Date().toISOString()});
 await until(()=>fs.existsSync(path.join(dir,who+'.release')),20000);
 process.exit(0);
}
for(const k of ['WARGAME_STORAGE_RUN_TOKEN','WARGAME_STORAGE_OWNER_PID'])delete process.env[k];
process.env.WARGAME_STORAGE_CONTROL_DIR=path.join(B,'unused-control');
process.env.WARGAME_STORAGE_LEASE_DIR=path.join(B,'unused-lease');
const engine=await import(pathToFileURL(path.join(E,'guarded-run.mjs')));
const scheduler=await import(pathToFileURL(path.join(E,'buildctl.mjs')));
const installed=await import('file:///Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs');
const approved=installed.loadPolicy();need(approved.maximumRunGrowthBytes===4000000000&&approved.reserveFreeBytes===500000000&&approved.maximumRetainedBytes===100000000000,'FAIR_POLICY_CHANGED');
const policy={...approved,maximumRunGrowthBytes:67108864};
function records(dir){const p=path.join(dir,'lease/scheduler/requests');return fs.existsSync(p)?fs.readdirSync(p).filter(x=>x.endsWith('.json')).map(x=>read(path.join(p,x))).sort((a,b)=>a.sequence-b.sequence):[];}
if(mode==='worker'){
 const dir=path.join(B,group),project=path.join(dir,'project-'+who),control=path.join(dir,who+'-control');
 fs.mkdirSync(project,{mode:0o700});await until(()=>fs.existsSync(path.join(dir,who+'.go')));
 const results=[];
 for(let i=1;i<=Number(countArg);i++){
  const label=who+i;let code=null,caught=null;
  try{code=await engine.guardedCommand(label,process.execPath,[fileURLToPath(import.meta.url),'payload',group,label],{directory:control,childControlDirectory:control,leaseDirectory:path.join(dir,'lease'),root:project,cwd:project,temporary:dir,environment:{...process.env},policy,retentionRoots:()=>[B]});}
  catch(error){caught=error.message;}
  results.push({label,code,caught});save(path.join(dir,label+'.worker-result.json'),results.at(-1));
  if(caught)break;
 }
 save(path.join(dir,who+'.worker-results.json'),results);process.exit(0);
}
need(mode===undefined,'CLOSED_FAIR_SUITE_MODE');
const F=read(path.join(B,'frozen.json'));need(Object.entries(F.inputs).every(([p,h])=>sha(p)===h),'FAIR_FROZEN_CHANGED');
const kernel=(op,ids)=>JSON.parse(cp.execFileSync(PY,['-I','-S','-B',path.join(B,'kernel-control.py'),op,JSON.stringify(ids)],{encoding:'utf8',timeout:30000,maxBuffer:131072}));
const children=[],rows=[],observed=[];
function launch(group,who,n){
 const dir=path.join(B,group);fs.mkdirSync(dir,{recursive:true,mode:0o700});
 const out=fs.openSync(path.join(dir,who+'.stdout'),'wx',0o600),err=fs.openSync(path.join(dir,who+'.stderr'),'wx',0o600);
 const child=cp.spawn(process.execPath,[fileURLToPath(import.meta.url),'worker',group,who,String(n)],{env:{...process.env},detached:true,stdio:['ignore',out,err]});fs.closeSync(out);fs.closeSync(err);
 children.push(child);const id=kernel('probe',[child.pid]).identities[child.pid];need(id&&id.parentPid===process.pid&&id.pgid===child.pid,'FAIR_WORKER_LINEAGE');observed.push(id);return child;
}
function go(group,who){fs.writeFileSync(path.join(B,group,who+'.go'),'go\n',{flag:'wx',mode:0o600});}
function release(group,label){fs.writeFileSync(path.join(B,group,label+'.release'),'release\n',{flag:'wx',mode:0o600});}
function active(dir){const r=records(dir);need(r.filter(x=>x.state==='running').length<=1,'ATOMIC_NATIVE_OVERLAP');return r;}
async function done(child){await until(()=>child.exitCode!==null||child.signalCode!==null);need(child.exitCode===0&&child.signalCode===null,'FAIR_WORKER_FAILED');}
let failure=null;const start=Date.now();
const deadline=setTimeout(()=>process.kill(process.pid,'SIGTERM'),300000);
try{
 const g='simultaneous',dir=path.join(B,g),a=launch(g,'a',1),b=launch(g,'b',1);go(g,'a');go(g,'b');
 const first=await until(()=>{const r=active(dir);return r.length===2&&r.some(x=>x.state==='running')&&r.some(x=>x.state==='queued')?r:null;});
 const winner=first.find(x=>x.state==='running'),waiter=first.find(x=>x.state==='queued');
 await until(()=>fs.existsSync(path.join(dir,winner.label+'.payload.json')));
 need(!fs.existsSync(path.join(dir,waiter.label+'.payload.json')),'QUEUED_PAYLOAD_RAN');
 save(path.join(dir,'simultaneous-observation.json'),{requests:first,owner:read(path.join(dir,'lease/active-run/owner.json'))});
 release(g,winner.label);
 await until(()=>{const r=active(dir);return r.find(x=>x.id===waiter.id)?.state==='running';});
 await until(()=>fs.existsSync(path.join(dir,waiter.label+'.payload.json')));release(g,waiter.label);await done(a);await done(b);
 const final=records(dir);need(final.every(x=>x.state==='finished'&&x.leaseReleaseCompleted===true),'SIMULTANEOUS_NOT_RELEASED');
 need(Date.parse(final.find(x=>x.id===waiter.id).startedAt)>=Date.parse(final.find(x=>x.id===winner.id).finishedAt),'SIMULTANEOUS_TIME_OVERLAP');
 rows.push({case:'simultaneous-native-acquisition',passed:true,requests:final.map(x=>({id:x.id,label:x.label,state:x.state,releaseCompleted:x.leaseReleaseCompleted,startedAt:x.startedAt,finishedAt:x.finishedAt})),concurrentNativeWriters:1});
 const fg='fair-followup',fd=path.join(B,fg),fa=launch(fg,'a',2);go(fg,'a');
 await until(()=>active(fd).some(x=>x.label==='a1'&&x.state==='running'));await until(()=>fs.existsSync(path.join(fd,'a1.payload.json')));
 const fb=launch(fg,'b',1);go(fg,'b');
 await until(()=>active(fd).some(x=>x.label==='b1'&&x.state==='queued'));release(fg,'a1');
 const middle=await until(()=>{const r=active(fd);return r.length===3&&r.some(x=>x.label==='b1'&&x.state==='running')&&r.some(x=>x.label==='a2'&&x.state==='queued')?r:null;});
 need(middle.find(x=>x.label==='a2').sequence>middle.find(x=>x.label==='b1').sequence,'FOLLOWUP_NOT_NEW_QUEUE_REQUEST');
 need(!fs.existsSync(path.join(fd,'a2.payload.json')),'FOLLOWUP_BYPASSED_WAITER');
 save(path.join(fd,'fairness-observation.json'),{requests:middle,owner:read(path.join(fd,'lease/active-run/owner.json'))});
 await until(()=>fs.existsSync(path.join(fd,'b1.payload.json')));release(fg,'b1');
 await until(()=>active(fd).some(x=>x.label==='a2'&&x.state==='running'));await until(()=>fs.existsSync(path.join(fd,'a2.payload.json')));release(fg,'a2');await done(fa);await done(fb);
 const ff=records(fd);need(ff.every(x=>x.state==='finished'&&x.leaseReleaseCompleted===true),'FAIR_REQUESTS_NOT_RELEASED');
 rows.push({case:'fair-followup-requeues-behind-other-project',passed:true,grantOrder:ff.slice().sort((a,b)=>Date.parse(a.startedAt)-Date.parse(b.startedAt)).map(x=>x.label),requests:ff.map(x=>({id:x.id,label:x.label,sequence:x.sequence,state:x.state,releaseCompleted:x.leaseReleaseCompleted}))});
 const outputRoot=path.join(B,'output-contract');fs.mkdirSync(outputRoot,{mode:0o700});
 const alias=path.join(B,'output-alias');fs.symlinkSync(outputRoot,alias);
 const make=(out,instances=[])=>({outputs:[scheduler.canonical(out)],instances,exclusive:true,phase:'functional',limits:{cpu:1,memoryBytes:1000000,diskBytes:1000000}});
 const left=make(outputRoot),right=make(path.join(alias,'nested'));
 const cap={cpu:4,memoryBytes:4000000,diskBytes:4000000};
 need(scheduler.outputConflict(left,right)&&scheduler.admission(right,[left],cap,{})==='shared output or application instance','ALIASED_SHARED_OUTPUT_NOT_PROTECTED');
 need(scheduler.outputConflict(make(path.join(B,'o1'),['owned-instance']),make(path.join(B,'o2'),['owned-instance'])),'SHARED_INSTANCE_NOT_PROTECTED');
 need(scheduler.admission({...make(path.join(B,'o3')),phase:'benchmark'},[make(path.join(B,'o4'))],cap,{})==='exclusive work','BENCHMARK_NOT_EXCLUSIVE');
 rows.push({case:'shared-output-alias-instance-and-benchmark-contract',passed:true,actualCanonicalAlias:true,decisionsChecked:3,parallelActivated:false});
 const cg='ordinary-cancel',cd=path.join(B,cg),oc=launch(cg,'a',1);go(cg,'a');
 await until(()=>active(cd).some(x=>x.state==='running'&&x.processGroup));const payload=await until(()=>{const p=path.join(cd,'a1.payload.json');return fs.existsSync(p)?read(p):null;});
 const live=kernel('probe',[payload.pid]).identities[payload.pid];need(live&&live.parentPid===oc.pid&&live.pgid===live.pid,'ORDINARY_PAYLOAD_NOT_INDEPENDENTLY_IDENTIFIED');observed.push(live);
 const current=kernel('probe',[oc.pid]).identities[oc.pid];need(current&&current.parentPid===process.pid,'ORDINARY_WORKER_IDENTITY_CHANGED');
 const cancellationAt=Date.now();oc.kill('SIGTERM');await done(oc);
 const rr=records(cd);need(rr.length===1&&rr[0].state==='needs-review'&&rr[0].leaseReleaseCompleted!==true,'ORDINARY_UNCERTAINTY_FALSE_RELEASE');
 const retained=read(path.join(cd,'lease/active-run/retained-run.json'));
 need(retained.existingContainerUncertainty===true&&retained.containersAtStart.ids.includes(F.protectedDatabaseId),'EXISTING_CONTAINER_UNCERTAINTY_LOST');
 const stopped=kernel('probe',[live.pid]);need(stopped.identities[live.pid]===null&&stopped.groupsStopped[live.pid]===true,'ORDINARY_PAYLOAD_NOT_STOPPED');
 rows.push({case:'ordinary-unregistered-cancel-preserves-container-uncertainty',passed:true,reservation:rr[0].id,state:rr[0].state,releaseCompleted:rr[0].leaseReleaseCompleted??false,processGroupStopped:true,existingContainerUncertainty:true,elapsedMs:Date.now()-cancellationAt,manualRecovery:false});
}catch(error){failure={type:error.name,code:/^[A-Z0-9_]+$/.test(error.message)?error.message:'PRIVATE_DIAGNOSTIC_REQUIRED'};}
finally{
 clearTimeout(deadline);
 for(const c of children){if(c.exitCode===null&&c.signalCode===null){const id=kernel('probe',[c.pid]).identities[c.pid];if(id&&id.parentPid===process.pid)c.kill('SIGTERM');}}
 await pause(500);
 const ids=[...new Map(observed.map(x=>[x.pid,x])).values()],cleanup=kernel('stop',ids);
 need(cleanup.every(x=>x.stopped&&x.groupStopped),'FAIR_CLEANUP_UNCONFIRMED');
 save(path.join(B,'independent-stop.json'),cleanup);
 save(path.join(B,'result.json'),{status:failure?'failed-native-fairness-and-fallback-controls':'passed-native-fairness-and-fallback-controls',rows,failure,elapsedMs:Date.now()-start,filesDeleted:0,parallelActivated:false,installedGuardChanged:false,negativeHoldPreserved:true,frozenInputsMatched:Object.entries(F.inputs).every(([p,h])=>sha(p)===h)});
}
if(failure)process.exitCode=1;
