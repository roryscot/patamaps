import fs from'node:fs';import path from'node:path';import{fileURLToPath}from'node:url';import{createHash}from'node:crypto';import{execFileSync}from'node:child_process';
import{conservativeCapacity,ownedVolumeUsage}from'./accounting.mjs';import{conservativeCapacity as legacyCapacity}from'../guarded-job-volume-accounting-20261104/accounting.mjs';
const B=path.dirname(fileURLToPath(import.meta.url)),R='/Volumes/dev_src_case_sensitive/projects/patamaps',C='/Users/admin/Documents/Codex/.storage-control/heavy-builds',PY=R+'/.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3',DOCKER='/Applications/Docker.app/Contents/Resources/bin/docker';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),sha=p=>'sha256:'+createHash('sha256').update(fs.readFileSync(p)).digest('hex'),save=(name,value)=>fs.writeFileSync(B+'/'+name,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
const F=read(B+'/frozen.json');for(const[p,h]of Object.entries(F.inputs))if(sha(p)!==h)throw Error('POOL_PROBE_INPUT_CHANGED');
const driver=read(B+'/driver-identity.json');const owner=read(C+'/active-run/owner.json'),request=read(C+'/scheduler/requests/'+owner.requestId+'.json');
if(owner.token!==process.env.WARGAME_STORAGE_RUN_TOKEN||driver.pid!==process.ppid||driver.parentPid!==owner.pid||String(owner.pid)!==process.env.WARGAME_STORAGE_OWNER_PID||request.enforcement!=='native-exclusive'||!request.exclusive||request.limits.diskBytes!==536870912)throw Error('POOL_PROBE_OWNER_CHANGED');
const locations=F.locations;
function db(){const d=JSON.parse(execFileSync(DOCKER,['inspect',F.protectedDatabase.id],{encoding:'utf8',timeout:15000}))[0];return{id:d.Id,running:d.State.Running,startedAt:d.State.StartedAt,restartCount:d.RestartCount};}
const beforeDb=db();if(JSON.stringify(beforeDb)!==JSON.stringify(F.protectedDatabase))throw Error('PROTECTED_DATABASE_CHANGED');
const began=performance.now();let result={status:'running-real-shared-pool-probe',reservationId:request.id,filesDeleted:0,limitsChanged:false,installedGuardChanged:false,parallelActivated:false};
function sample(){
 const disks=new Map();
 for(const p of locations){const dev=fs.statSync(p).dev,s=fs.statfsSync(p,{bigint:true}),free=Number(s.bavail*s.bsize);disks.set(dev,Math.min(disks.get(dev)??Infinity,free));}
 const document=JSON.parse(execFileSync(PY,['-I','-S','-B',B+'/query-pools.py',JSON.stringify(locations)],{encoding:'utf8',timeout:5500,maxBuffer:65536}));
 const volume=ownedVolumeUsage(JSON.parse(execFileSync(PY,['-I','-S','-B',R+'/.tools/guarded-job-volume-accounting-20261104/query.py',R],{encoding:'utf8',timeout:5500,maxBuffer:65536})),R);
 return{atUtc:new Date().toISOString(),disks:[...disks].sort((a,b)=>a[0]-b[0]),document,volume};
}
try{
 const units=execFileSync(process.execPath,[B+'/test-accounting.mjs'],{encoding:'utf8',timeout:20000,maxBuffer:65536});
 save('unit-executed.json',{stdout:units,controlsPassed:36});if(!units.includes('"controlsPassed":36'))throw Error('POOL_UNIT_CONTROLS_FAILED');
 const quiet=[];
 for(let i=0;i<3;i++){quiet.push(sample());if(i<2)await new Promise(resolve=>setTimeout(resolve,1000));}
 const frees=quiet.map(x=>x.document.pools[0]?.freeBytes);if(frees.some(x=>!Number.isSafeInteger(x))||Math.max(...frees)-Math.min(...frees)>8388608)throw Error('POOL_BASELINE_NOT_QUIET');
 let current=quiet.at(-1);
 if(current.disks.length!==2||current.document.devices.length!==2||current.document.pools.length!==1||new Set(current.document.devices.map(x=>x.pool)).size!==1)throw Error('REAL_SHARED_POOL_NOT_CONFIRMED');
 const old=legacyCapacity(()=>new Map(current.disks),()=>current.volume),corrected=conservativeCapacity(()=>new Map(current.disks),()=>current.volume,()=>current.document);
 const before={sample:current,legacyAvailable:old(),correctedAvailable:corrected()};
 save('before.json',{quietSamples:quiet,capacity:before});
 const file=B+'/owned-64-mib-probe.bin';const fd=fs.openSync(file,'wx',0o600),block=Buffer.alloc(1048576),hash=createHash('sha256');
 for(let i=0;i<block.length;i++)block[i]=(i*73+(i>>10)*31+17)%251+1;
 try{for(let i=0;i<64;i++){block.writeUInt32LE(i,0);fs.writeSync(fd,block);hash.update(block);}fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
 const st=fs.statSync(file);if(st.size!==67108864||st.blocks*512<67108864)throw Error('REAL_DENSE_ALLOCATION_NOT_ESTABLISHED');
 current=sample();const after={sample:current,legacyAvailable:old(),correctedAvailable:corrected()};
 const oldGrowth=before.legacyAvailable-after.legacyAvailable,newGrowth=before.correctedAvailable-after.correctedAvailable;
 save('after.json',after);
 if(current.volume.bytes!==before.sample.volume.bytes||newGrowth<33554432||oldGrowth-newGrowth<33554432)throw Error('ACTUAL_DUPLICATE_CHARGE_NOT_ESTABLISHED');
 if(JSON.stringify(db())!==JSON.stringify(beforeDb))throw Error('PROTECTED_DATABASE_CHANGED');
 for(const[p,h]of Object.entries(F.inputs))if(sha(p)!==h)throw Error('POOL_PROBE_INPUT_CHANGED');
 result={...result,status:'passed-real-shared-pool-capacity-probe',controlsPassed:36,denseLogicalBytes:st.size,denseAllocatedBytes:st.blocks*512,denseFileDigest:'sha256:'+hash.digest('hex'),legacyObservedChargeBytes:oldGrowth,correctedObservedChargeBytes:newGrowth,duplicatePhysicalChargeAvoidedBytes:oldGrowth-newGrowth,trackedFilesystemDevices:2,physicalPools:1,ownedVolumeAdditionalChargeUnchanged:true,unrelatedDatabaseStartIdentityUnchanged:true,actualPerformanceAcceptance:false,actualApplicationBuild:false};
}catch(error){result={...result,status:'failed-real-shared-pool-capacity-probe',failureCode:error.message};throw error;}
finally{result.elapsedSeconds=(performance.now()-began)/1000;result.finishedAtUtc=new Date().toISOString();save('probe-result.json',result);}
console.log(JSON.stringify(result));
