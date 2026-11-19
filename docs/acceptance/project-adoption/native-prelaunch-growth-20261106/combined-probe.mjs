import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {guardedCommand} from './guarded-run.mjs';

const dir=path.dirname(fileURLToPath(import.meta.url));
const work=path.join(dir,'work');
const lease=path.join(dir,'lease');
const control=path.join(dir,'control');
const marker=path.join(work,'spawned');
fs.mkdirSync(work,{mode:0o700});
const policy={version:1,minimumFreeBytes:0,reserveFreeBytes:500000000,maximumRunGrowthBytes:67108864,
  maximumRetainedBytes:100000000000,monitorIntervalMs:250,terminationGraceMs:1000};
let scanned=false, snapshots=0, rootsReads=0, postSnapshotReads=0;
const env={PATH:'/usr/bin:/bin',LANG:'C'};
const stable={root:work,cwd:work,temporary:work,directory:control,childControlDirectory:control,leaseDirectory:lease,
  policy,environment:env,capacity:()=>10000000000,retentionRoots:()=>[work],inventory:()=>0,
  containerSnapshot:()=>({known:true,ids:['preexisting-fixture']})};
await assert.rejects(guardedCommand('combined-prelaunch-and-final-accounting-fault','/bin/sh',
  ['-c','printf started > "$1"','guard-probe',marker],{
    ...stable,inventory:()=>{scanned=true;return 0;},
    capacity:()=>{if(snapshots && ++postSnapshotReads>1)throw Error('fixture final capacity unavailable');
      return scanned?10000000000-policy.maximumRunGrowthBytes-1:10000000000;},
    containerSnapshot:()=>{snapshots++;return stable.containerSnapshot();},
    retentionRoots:()=>{if(++rootsReads>1)throw Error('fixture final retained roots unavailable');return [work];},
  }),/disk-growth budget was exceeded/);
assert.equal(fs.existsSync(marker),false);
assert.equal(fs.existsSync(path.join(lease,'active-run')),false);
assert.equal(snapshots,1);
const read=(file)=>JSON.parse(fs.readFileSync(file));
const runs=path.join(lease,'runs');
const records=()=>fs.readdirSync(runs).map(n=>path.join(runs,n,'run.json')).filter(p=>fs.existsSync(p)).map(read);
const [failed]=records();
assert.equal(failed.exitCode,75);
assert.equal(failed.completed,false);
assert.match(failed.stopReason,/disk-growth budget was exceeded/);
assert.deepEqual(failed.finalAccountingErrors.map(e=>e.field),['freeBytesAtEnd','retainedRootsAtEnd']);
assert.equal(failed.terminalCapacityUnavailable,true);
assert.equal(await guardedCommand('next-job-same-lease','/usr/bin/true',[],stable),0);
assert.equal(fs.existsSync(path.join(lease,'active-run')),false);
assert.equal(records().length,2);
const req=path.join(lease,'scheduler','requests');
assert.ok(fs.readdirSync(req).map(n=>read(path.join(req,n))).every(x=>x.state==='finished'&&x.leaseReleaseCompleted));
console.log(JSON.stringify({failedBeforeSpawn:true,primaryGrowthDiagnosticPreserved:true,
  bothFinalAccountingErrorsRecorded:true,refusedLeaseReleased:true,followUpQueuedAndReleased:true}));
