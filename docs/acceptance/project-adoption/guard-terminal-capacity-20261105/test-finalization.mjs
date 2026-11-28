import assert from 'node:assert/strict';
import {existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import * as installed from '/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs';
import * as candidate from './guarded-run.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const results=[];
const parse=p=>JSON.parse(readFileSync(p,'utf8'));
for(const [name,engine,uncertain,expectedState] of [
 ['stock-terminal-fault',installed,false,'running'],
 ['candidate-terminal-fault-stopped',candidate,false,'finished'],
 ['candidate-terminal-fault-uncertain',candidate,true,'needs-review'],
]){
 const root=path.join(dir,name);
 const marker=path.join(root,'child-exited-marker');
 const leaseDirectory=path.join(root,'lease');
 mkdirSync(root);
 let snapshots=0,terminalReads=0;
 const policy={...installed.loadPolicy(),maximumRunGrowthBytes:67108864,monitorIntervalMs:60000};
 await assert.rejects(engine.guardedCommand('patamaps-terminal-fault-fixture',process.execPath,
  ['-e','require("node:fs").writeFileSync(process.argv[1],"child completed")',marker],
  {root,cwd:root,temporary:root,directory:root,leaseDirectory,policy,
   environment:{PATH:'/usr/bin:/bin'},
   capacity:()=>{if(existsSync(marker)){terminalReads++;throw Error('Injected final accounting failure');}return 20_000_000_000;},
   containerSnapshot:()=>({known:!uncertain||++snapshots===1,ids:[]})}),
  /Injected final accounting failure|Owned workload stop unconfirmed/);
 assert.equal(terminalReads,1);
 const requestDir=path.join(leaseDirectory,'scheduler','requests');
 const requests=readdirSync(requestDir);
 assert.equal(requests.length,1);
 const request=parse(path.join(requestDir,requests[0]));
 assert.equal(request.state,expectedState);
 assert.equal(existsSync(path.join(leaseDirectory,'active-run')),expectedState!=='finished');
 if(engine===candidate){
  const record=expectedState==='finished'
   ? parse(path.join(leaseDirectory,'runs',readdirSync(path.join(leaseDirectory,'runs'))[0],'run.json'))
   : parse(path.join(leaseDirectory,'active-run','retained-run.json'));
  assert.equal(record.completed,false);
  assert.equal(record.exitCode,75);
  assert.equal(record.freeBytesAtEnd,null);
  assert.equal(record.terminalCapacityUnavailable,true);
  assert.equal(request.leaseReleaseCompleted,expectedState==='finished');
 }
 results.push({name,expectedState,terminalReads,terminalFailurePreserved:engine===candidate});
}
writeFileSync(path.join(dir,'fixture-review.json'),JSON.stringify({cases:results,installedGuardChanged:false,applicationBuildRun:false},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({passed:results.length,cases:results}));
