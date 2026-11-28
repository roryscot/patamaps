import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
const expected=JSON.parse(fs.readFileSync('/work/expected.json','utf8'));
const receipt={status:'failed',cases:[],applicationLaunches:0,wrongArchitectureExecuted:false,architectureGateAccepted:false,staleContractAccepted:false,applicationReleaseAccepted:false};
const children=[],app='/work/app/packages/web',base='http://127.0.0.1:32139';
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let expired=false;
const deadline=setTimeout(()=>{expired=true;for(const c of children)if(!c.closed)c.child.kill('SIGTERM');},180000);
const checkTime=()=>assert.equal(expired,false,'Controller deadline');
async function response(){try{const r=await fetch(base,{headers:{'User-Agent':'Mozilla/5.0 PatamapsQualification/1.0'},redirect:'manual',signal:AbortSignal.timeout(2000)});const text=await r.text();assert.ok(Buffer.byteLength(text)<=8388608);return {status:r.status,html:(r.headers.get('content-type')??'').includes('text/html'),bytes:Buffer.byteLength(text),digest:createHash('sha256').update(text).digest('hex')};}catch(error){if(error?.code==='ERR_ASSERTION')throw error;return null;}}
function spawnOwned(executable,args,env){
 const child=spawn(executable,args,{cwd:app,env,stdio:['ignore','pipe','pipe']});
 const item={child,closed:false,out:'',err:'',bytes:0,spawnError:null,outputBound:false};children.push(item);
 child.on('error',e=>{item.spawnError=e.code??'unknown';});
 child.on('close',()=>{item.closed=true;});
 for(const [stream,key]of [[child.stdout,'out'],[child.stderr,'err']])stream.on('data',b=>{item.bytes+=b.length;item[key]=(item[key]+b.toString()).slice(-1048576);if(item.bytes>4194304){item.outputBound=true;child.kill('SIGTERM');}});
 return item;
}
async function stopOwned(c){
 if(!c.closed)c.child.kill('SIGTERM');
 for(let i=0;i<50&&!c.closed;i++)await delay(100);
 if(!c.closed)c.child.kill('SIGKILL');
 for(let i=0;i<50&&!c.closed;i++)await delay(100);
 assert.equal(c.closed,true,'Owned child stop unconfirmed');
}
async function native(args){
 checkTime();
 const c=spawnOwned('/work/patamaps',args,{PATH:'/usr/bin:/bin',HOME:'/work/home',TMPDIR:'/work/tmp',RUST_BACKTRACE:'0'});
 try{for(let i=0;i<300&&!c.closed;i++){checkTime();await delay(100);}assert.ok(c.closed,'Native verifier deadline');assert.equal(c.outputBound,false);assert.equal(c.spawnError,null);return {code:c.child.exitCode,out:c.out,err:c.err};}
 finally{await stopOwned(c);}
}
function verifyInputs(){
 for(const f of expected.files){const p='/work/app/'+f.path;assert.equal(sha(p),f.sha256);assert.equal(fs.lstatSync(p).isFile(),true);assert.equal(fs.lstatSync(p).mode&0o7777,f.mode);}
 for(const [name,v]of Object.entries(expected.tools)){assert.equal(sha('/work/'+name),v.sha256);assert.equal(fs.lstatSync('/work/'+name).mode&0o7777,v.mode);}
 assert.equal(fs.readFileSync(app+'/.next/BUILD_ID','utf8').trim(),expected.linuxBuildId);
}
async function admittedLaunch(path,digest){
 assert.equal(await response(),null,'Listener occupied before launch');
 const result=await native(['elf-target-check',path,'--target','linux/amd64','--digest','sha256:'+digest]);
 if(result.code!==0)return {refused:true,...result};
 const report=JSON.parse(result.out);assert.equal(report.status,'matched-elf-target-header');assert.equal(report.target,'linux/amd64');assert.equal(report.digest,'sha256:'+digest);assert.equal(report.executionPerformed,false);
 receipt.applicationLaunches++;
 fs.writeFileSync('/work/admitted-launch-'+receipt.applicationLaunches+'.marker','admitted',{flag:'wx'});
 return {refused:false,item:spawnOwned(path,[app+'/server.js'],{...expected.environment,PORT:'32139',HOSTNAME:'127.0.0.1',HOME:'/work/home',TMPDIR:'/work/tmp',PATH:'/usr/bin:/bin'})};
}
async function healthy(label){
 const run=await admittedLaunch('/work/node',expected.tools.node.sha256);assert.equal(run.refused,false);
 try{
  let value=null;
  const readyUntil=Date.now()+30000;
  while(Date.now()<readyUntil){checkTime();if(run.item.closed)break;value=await response();if(value?.status===200&&value.html&&value.bytes>100)break;await delay(250);}
  assert.ok(value?.status===200&&value.html&&value.bytes>100,'Actual HTML readiness failed');
  assert.equal(run.item.outputBound,false);
  receipt.cases.push({name:label,status:'passed',httpStatus:value.status,htmlBytes:value.bytes,responseDigest:value.digest});
 }finally{await stopOwned(run.item);assert.equal(await response(),null,'Application listener survived');}
}
try{
 assert.equal(process.version,'v24.11.1');assert.equal(process.platform,'linux');assert.equal(process.arch,'x64');
 verifyInputs();
 const limits={};for(const[k,file]of Object.entries({cpu:'cpu.max',memory:'memory.max',swap:'memory.swap.max',pids:'pids.max'}))limits[k]=fs.readFileSync('/sys/fs/cgroup/'+file,'utf8').trim();
 assert.deepEqual(limits,{cpu:'200000 100000',memory:'1610612736',swap:'0',pids:'256'});receipt.kernelLimits=limits;
 assert.deepEqual(Object.keys(os.networkInterfaces()).filter(n=>n!=='lo'),[]);receipt.onlyLoopbackInterface=true;
 let readonly=false;try{fs.writeFileSync('/patamaps-architecture-root-write','forbidden',{flag:'wx'});}catch(e){readonly=['EROFS','EACCES'].includes(e.code);}assert.equal(readonly,true);receipt.rootWriteRefused=true;
 const disk=fs.statfsSync('/work',{bigint:true});assert.ok(disk.bsize*disk.blocks<=536870912n);receipt.writableFilesystemBytes=String(disk.bsize*disk.blocks);
 fs.writeFileSync('/work/architecture-write-probe','x',{flag:'wx'});receipt.quotaWritePassed=true;
 for(const p of expected.deniedPaths)assert.throws(()=>fs.readFileSync(p),e=>e.code==='ENOENT');receipt.declaredHostPathsUnavailable=true;
 const engine=await native(['engine']);assert.equal(engine.code,0);assert.deepEqual(JSON.parse(engine.out),expected.compilerEngine);
 const arm=await native(['elf-target-check','/work/node-arm64','--target','linux/arm64','--digest','sha256:'+expected.tools['node-arm64'].sha256]);assert.equal(arm.code,0);assert.equal(JSON.parse(arm.out).header.machine,183);
 await healthy('baseline-selected-x64-real-html');
 const before=receipt.applicationLaunches;assert.equal(fs.existsSync('/work/admitted-launch-2.marker'),false);
 const wrong=await admittedLaunch('/work/node-arm64',expected.tools['node-arm64'].sha256);
 assert.equal(wrong.refused,true);assert.equal(wrong.code,2);assert.match(wrong.err,/ELF_ARCHITECTURE/);assert.equal(receipt.applicationLaunches,before);assert.equal(fs.existsSync('/work/admitted-launch-2.marker'),false);assert.equal(await response(),null);
 receipt.cases.push({name:'authentic-arm64-before-application-effects',status:'refused',exitCode:2,diagnostic:'ELF_ARCHITECTURE',correctDigestSupplied:true,applicationLaunchCountUnchanged:true,downstreamMarkerAbsent:true});
 await healthy('post-refusal-selected-x64-real-html');
 verifyInputs();receipt.stagedInputsUnchanged=true;assert.equal(receipt.applicationLaunches,2);
 receipt.status='passed-managed-original-next-runtime-architecture';receipt.architectureGateAccepted=true;
}catch(error){receipt.error=error.stack;process.exitCode=1;}
finally{
 clearTimeout(deadline);receipt.allOwnedChildrenStopped=true;
 for(const c of [...children].reverse()){try{await stopOwned(c);}catch(e){receipt.allOwnedChildrenStopped=false;receipt.stopError=String(e);process.exitCode=1;receipt.status='failed';receipt.architectureGateAccepted=false;}}
 receipt.listenerStopped=(await response())===null;
 if(!receipt.listenerStopped||expired){receipt.status='failed';receipt.architectureGateAccepted=false;process.exitCode=1;}
 receipt.ownedChildCount=children.length;receipt.kernelExecFormatDenialClaimed=false;receipt.automaticGenericLaunchProtection=false;
 receipt.inputManifestDigest=sha('/work/expected.json');receipt.controllerDigest=sha('/work/controls.mjs');
 fs.writeFileSync('/work/runtime-receipt.json',JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:receipt.status,cases:receipt.cases.length,architectureGateAccepted:receipt.architectureGateAccepted,allOwnedChildrenStopped:receipt.allOwnedChildrenStopped,listenerStopped:receipt.listenerStopped}));
}
