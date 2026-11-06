import fs from'node:fs';import path from'node:path';import os from'node:os';import{fileURLToPath,pathToFileURL}from'node:url';import{createHash}from'node:crypto';import{execFileSync}from'node:child_process';
import{ownedVolumeUsage,conservativeCapacity}from'../guarded-job-volume-accounting-20261104/accounting.mjs';
const B=path.dirname(fileURLToPath(import.meta.url)),R='/Volumes/dev_src_case_sensitive/projects/patamaps',control='/Users/admin/Documents/Codex/storage-safeguards',PY=R+'/.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3';
if(process.argv.length!==2||process.env.WARGAME_STORAGE_RUN_TOKEN)throw Error('One fresh scoped maintenance entry required');
const F=JSON.parse(fs.readFileSync(B+'/frozen.json')),sha=p=>'sha256:'+createHash('sha256').update(fs.readFileSync(p)).digest('hex');
for(const[p,h]of Object.entries(F.inputs))if(sha(p)!==h)throw Error('MAINTENANCE_INPUT_CHANGED');
const config=JSON.parse(fs.readFileSync(control+'/projects.json')),project=config.projects.patamaps;if(project.root!==R)throw Error('PROJECT_ROOT_CHANGED');
const engine=await import(pathToFileURL(config.engine)),{retentionInventory}=await import(pathToFileURL(control+'/retention_admission.mjs'));
const approved=engine.loadPolicy();if(approved.maximumRunGrowthBytes!==4000000000||approved.reserveFreeBytes!==500000000||approved.maximumRetainedBytes!==100000000000)throw Error('APPROVED_POLICY_CHANGED');
const policy={...approved,maximumRunGrowthBytes:1000000000};
const roots=()=>{const all=[R,...(project.retentionRoots??[]),...config.cacheRoots].filter(fs.existsSync);for(const temp of [...new Set([os.tmpdir(),'/private/tmp'])].filter(fs.existsSync))for(const e of fs.readdirSync(temp,{withFileTypes:true}))if(e.isDirectory()&&project.temporaryPrefixes.some(p=>e.name.startsWith(p)))all.push(path.join(temp,e.name));return[...new Set(all)].sort();};
const locations=()=>[R,os.tmpdir(),'/private/tmp',...(project.retentionRoots??[]),...config.cacheRoots].filter(fs.existsSync);
const disks=()=>{const result=new Map();for(const p of locations()){const dev=fs.statSync(p).dev,free=engine.availableBytes(p);result.set(dev,Math.min(result.get(dev)??Infinity,free));}return result;};
function usage(){const doc=JSON.parse(execFileSync(PY,['-I','-S','-B',R+'/.tools/guarded-job-volume-accounting-20261104/query.py',R],{encoding:'utf8',timeout:5500,maxBuffer:65536}));return{...ownedVolumeUsage(doc,R),volumes:doc.Volumes.filter(x=>x.Labels?.['buildctl.project']===R).map(x=>({name:x.Name,bytes:x.UsageData.Size})).sort((a,b)=>a.name<b.name?-1:a.name>b.name?1:0)};}
const baseline=usage();if(JSON.stringify(baseline)!==JSON.stringify(F.ownedVolumeUsage))throw Error('CLOSED_OWNED_VOLUME_BASELINE_CHANGED');
// Maintenance only: all Patamaps containers are stopped; no automatic restart is allowed.
// No owned volume writer starts. Host growth remains monitored while Docker is offline.
// The exact closed owned-volume charge is retained in admission and checked after restart.
const capacity=conservativeCapacity(disks,()=>baseline);
const inventory=locations=>engine.retainedBytes(locations)+baseline.bytes;
let code=1;
try{
 code=await engine.guardedCommand('patamaps-idle-view-maintenance',PY,['-I','-S','-B',B+'/recovery.py'],{directory:path.join(os.homedir(),'Documents/Codex/.storage-control/other-projects'),childControlDirectory:path.join(os.homedir(),'Documents/Codex/.storage-control/wargame'),leaseDirectory:engine.sharedLeaseDirectory,root:R,cwd:R,policy,capacity,retentionRoots:roots,inventory:retentionInventory(inventory,policy),environment:{...process.env,LOCAL_STORAGE_PROJECT:R}});
}finally{
 const p=B+'/receipt.json';
 if(fs.existsSync(p)){const result=JSON.parse(fs.readFileSync(p));if((result.databaseStopAttempted||result.desktopStopAttempted)&&!result.databaseReady)execFileSync(PY,['-I','-S','-B',B+'/recovery.py','--restore-only'],{timeout:360000,stdio:['ignore','inherit','inherit']});}
}
if(JSON.stringify(usage())!==JSON.stringify(baseline))throw Error('CLOSED_OWNED_VOLUME_USAGE_CHANGED');
process.exitCode=code;
