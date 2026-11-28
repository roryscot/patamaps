import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {guardedCommand} from './guarded-run.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const maximum=450000000, margin=300000000, starting=10000000000;
const policy={version:1,minimumFreeBytes:0,reserveFreeBytes:500000000,
 maximumRunGrowthBytes:maximum,maximumRetainedBytes:100000000000,monitorIntervalMs:250,terminationGraceMs:1000};
async function run(label,loss,allowed){
 const d=path.join(root,label),work=path.join(d,'work'),lease=path.join(d,'lease'),control=path.join(d,'control');
 const marker=path.join(work,'spawned');
 fs.mkdirSync(work,{recursive:true,mode:0o700});
 let current=starting;
 const options={root:work,cwd:work,temporary:work,directory:control,childControlDirectory:control,
  leaseDirectory:lease,policy,minimumRemainingGrowthBeforeLaunchBytes:margin,
  environment:{PATH:'/usr/bin:/bin',LANG:'C'},capacity:()=>current,retentionRoots:()=>[work],
  inventory:()=>{current=starting-loss;return 0;},containerSnapshot:()=>({known:true,ids:['existing-test-container']})};
 const command=()=>guardedCommand(label,'/bin/sh',['-c','printf started > "$1"','probe',marker],options);
 if(allowed)assert.equal(await command(),0);
 else await assert.rejects(command(),/insufficient disk-growth margin before workload startup/);
 assert.equal(fs.existsSync(marker),allowed);
 assert.equal(fs.existsSync(path.join(lease,'active-run')),false);
 const req=path.join(lease,'scheduler','requests'), names=fs.readdirSync(req);
 assert.equal(names.length,1);
 const r=JSON.parse(fs.readFileSync(path.join(req,names[0])));
 assert.equal(r.state,'finished');
 assert.equal(r.leaseReleaseCompleted,true);
 const runs=path.join(lease,'runs'), reports=fs.readdirSync(runs);
 const g=JSON.parse(fs.readFileSync(path.join(runs,reports[0],'run.json')));
 assert.equal(g.remainingGrowthAtLaunchCheckBytes,maximum-loss);
 assert.equal(g.exitCode,allowed?0:75);
 return {label,lossBytes:loss,remainingBytes:maximum-loss,started:allowed,released:true};
}
const cases=[await run('observed-resume-loss',447836160,false),await run('one-byte-below-margin',150000001,false),
 await run('exact-margin',150000000,true)];
console.log(JSON.stringify({status:'verified-staged-prelaunch-growth-margin',marginBytes:margin,
 allowanceBytes:maximum,cases,isolatedScheduler:true,installedGuardChanged:false}));
