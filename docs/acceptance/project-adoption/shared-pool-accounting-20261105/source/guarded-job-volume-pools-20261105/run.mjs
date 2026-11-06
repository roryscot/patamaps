import {statSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {ownedVolumeUsage,conservativeCapacity} from './accounting.mjs';
import {existsSync,readFileSync,readdirSync,realpathSync}from'node:fs';
import path from'node:path';
import os from'node:os';
import {pathToFileURL}from'node:url';
const directory='/Users/admin/Documents/Codex/storage-safeguards';
const root='/Volumes/dev_src_case_sensitive/projects/patamaps';
const config=JSON.parse(readFileSync(path.join(directory,'projects.json'),'utf8'));
if(config.version!==1||config.projects.patamaps.root!==root)throw Error('Canonical project configuration changed');
const spec=JSON.parse(readFileSync(process.argv[2],'utf8'));
if(Object.keys(spec).sort().join(',')!=='argv,cwd,maximumRunGrowthBytes,version'||spec.version!==1)throw Error('Closed guarded-job declaration required');
if(!Array.isArray(spec.argv)||!spec.argv.length||spec.argv.some(x=>typeof x!=='string'||!x||x.includes('\0'))||!path.isAbsolute(spec.argv[0])||realpathSync(spec.cwd)!==realpathSync(root))throw Error('Explicit argv and canonical project cwd required');
if(process.env.WARGAME_STORAGE_RUN_TOKEN)throw Error('A follow-up must queue independently, not inherit a reservation');
const engine=await import(pathToFileURL(config.engine));
const {retentionInventory}=await import(pathToFileURL(path.join(directory,'retention_admission.mjs')));
const approved=engine.loadPolicy();
const requested=spec.maximumRunGrowthBytes;
if(!Number.isSafeInteger(requested)||requested<67108864||requested>approved.maximumRunGrowthBytes)throw Error('Requested run allowance must fit the approved policy');
if(approved.maximumRunGrowthBytes!==4000000000||approved.reserveFreeBytes!==500000000||approved.maximumRetainedBytes!==100000000000)throw Error('Approved policy bindings changed');
const policy=Object.freeze({...approved,maximumRunGrowthBytes:requested});
const project=config.projects.patamaps;
const roots=()=>{
 const result=[project.root,...(project.retentionRoots??[]),...config.cacheRoots].filter(existsSync);
 for(const temporary of [...new Set([os.tmpdir(),'/private/tmp'])].filter(existsSync))
  for(const entry of readdirSync(temporary,{withFileTypes:true}))
   if(entry.isDirectory()&&project.temporaryPrefixes.some(prefix=>entry.name.startsWith(prefix)))result.push(path.join(temporary,entry.name));
 return[...new Set(result)].sort();
};
const locations=()=>[project.root,spec.cwd,os.tmpdir(),'/private/tmp',...(project.retentionRoots??[]),...config.cacheRoots].filter(existsSync);
let sampled=null,sampledAt=-Infinity;
const volumes=(fresh=false)=>{
 const now=performance.now();
 if(fresh||sampled===null||now-sampledAt>=1000){
  const result=execFileSync("/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3",['-I','-S','-B',new URL('./query.py',import.meta.url).pathname,project.root],{timeout:5500,maxBuffer:65536,encoding:'utf8',stdio:['ignore','pipe','pipe']});
  sampled=ownedVolumeUsage(JSON.parse(result),project.root);sampledAt=performance.now();
 }
 return sampled;
};
const disks=()=>{
 const result=new Map();
 for(const location of locations()){const device=statSync(location).dev,bytes=engine.availableBytes(location);result.set(device,Math.min(result.get(device)??Infinity,bytes));}
 return result;
};
let poolSample=null,poolSampleAt=-Infinity,lastWitness=-Infinity;
const poolDocument=()=>{
 const now=performance.now();
 if(poolSample===null||now-poolSampleAt>=1000){
  poolSample=JSON.parse(execFileSync('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3',['-I','-S','-B',new URL('./query-pools.py',import.meta.url).pathname,JSON.stringify(locations())],{encoding:'utf8',timeout:5500,maxBuffer:65536,stdio:['ignore','pipe','pipe']}));
  poolSampleAt=performance.now();
 }
 if(now-lastWitness>=10000){console.error(JSON.stringify({type:'physical-pool-capacity-sample',atUtc:new Date().toISOString(),disks:[...disks()],ownedVolumes:volumes(),poolDocument:poolSample}));lastWitness=now;}
 return poolSample;
};
const capacity=conservativeCapacity(disks,()=>volumes(),poolDocument);
const inventory=(locations)=>{const rootAllocatedBytes=engine.retainedBytes(locations),owned=volumes(true),total=rootAllocatedBytes+owned.bytes;console.error(JSON.stringify({type:'owned-volume-retention-admission',rootAllocatedBytes,ownedVolumeBytes:owned.bytes,ownedVolumeCount:owned.count,retainedAllocatedBytes:total}));return total;};
process.chdir(spec.cwd);
process.exitCode=await engine.guardedCommand('patamaps',spec.argv[0],spec.argv.slice(1),{
 directory:path.join(os.homedir(),'Documents/Codex/.storage-control/other-projects'),
 childControlDirectory:path.join(os.homedir(),'Documents/Codex/.storage-control/wargame'),
 leaseDirectory:engine.sharedLeaseDirectory,
 root:project.root,cwd:spec.cwd,policy,capacity,retentionRoots:roots,
 inventory:retentionInventory(inventory,policy),
 environment:{...process.env,LOCAL_STORAGE_PROJECT:project.root}
});
