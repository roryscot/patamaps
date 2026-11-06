import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {guardedCommand} from './candidate/guarded-run.mjs';

const directory=path.dirname(fileURLToPath(import.meta.url));
const root=path.join(directory,'candidate-slow-inventory');
const leaseDirectory=path.join(root,'lease');
const control=path.join(root,'control');
const work=path.join(root,'work');
const requests=path.join(leaseDirectory,'scheduler','requests');
const before=fs.readdirSync(requests);
assert.equal(before.length,1);
const first=JSON.parse(fs.readFileSync(path.join(requests,before[0])));
assert.equal(first.state,'finished');
assert.equal(first.leaseReleaseCompleted,true);
assert.equal(fs.existsSync(path.join(leaseDirectory,'active-run')),false);
const policy={version:1,minimumFreeBytes:0,reserveFreeBytes:500000000,maximumRunGrowthBytes:67108864,
  maximumRetainedBytes:100000000000,monitorIntervalMs:250,terminationGraceMs:1000};
const result=await guardedCommand('follow-up-same-isolated-scheduler','/usr/bin/true',[],{
  root:work,cwd:work,temporary:work,directory:control,childControlDirectory:control,leaseDirectory,
  environment:{PATH:'/usr/bin:/bin',LANG:'C'},policy,capacity:()=>10000000000,retentionRoots:()=>[work],
  inventory:()=>0,containerSnapshot:()=>({known:true,ids:['preexisting-fixture']}),
});
assert.equal(result,0);
assert.equal(fs.existsSync(path.join(leaseDirectory,'active-run')),false);
const after=fs.readdirSync(requests);
assert.equal(after.length,2);
const id=after.find(file=>!before.includes(file));
const followUp=JSON.parse(fs.readFileSync(path.join(requests,id)));
assert.equal(followUp.state,'finished');
assert.equal(followUp.leaseReleaseCompleted,true);
assert.ok(followUp.sequence>first.sequence);
console.log(JSON.stringify({refusedRequestReleased:true,subsequentRequestQueuedAndReleased:true,subsequentExitCode:result}));
