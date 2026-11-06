import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root=path.dirname(fileURLToPath(import.meta.url));
const variant=process.argv[2];
assert.ok(['baseline','candidate'].includes(variant));
const {guardedCommand}=await import(pathToFileURL(path.join(root,variant,'guarded-run.mjs')));
const freeAtStart=10_000_000_000;
const limit=67_108_864;
const policy={
  version:1,minimumFreeBytes:0,reserveFreeBytes:500_000_000,
  maximumRunGrowthBytes:limit,maximumRetainedBytes:100_000_000_000,
  monitorIntervalMs:250,terminationGraceMs:1_000,
};
const read=(p)=>JSON.parse(fs.readFileSync(p,'utf8'));

async function run(label,{inventoryLoss=0,snapshotLoss=0,containers=[],expected}) {
  const box=path.join(root,variant+'-'+label);
  const work=path.join(box,'work');
  const lease=path.join(box,'lease');
  const control=path.join(box,'control');
  fs.mkdirSync(work,{recursive:true,mode:0o700});
  const marker=path.join(work,'spawned');
  let free=freeAtStart, inventoryCalls=0, snapshots=0, exitCode=null, error=null;
  const options={
    root:work,cwd:work,temporary:work,directory:control,childControlDirectory:control,
    leaseDirectory:lease,policy,environment:{PATH:'/usr/bin:/bin',LANG:'C'},
    capacity:()=>free,retentionRoots:()=>[work],
    inventory:()=>{inventoryCalls++;free-=inventoryLoss;return 0;},
    containerSnapshot:()=>{if(++snapshots===1)free-=snapshotLoss;return {known:true,ids:containers};},
  };
  try{
    exitCode=await guardedCommand(label,'/bin/sh',['-c','printf started > "$1"; sleep 1','guard-probe',marker],options);
  }catch(e){error=e.message;}
  const requestPath=path.join(lease,'scheduler','requests');
  const names=fs.readdirSync(requestPath);
  assert.equal(names.length,1);
  const request=read(path.join(requestPath,names[0]));
  const leaseHeld=fs.existsSync(path.join(lease,'active-run'));
  const records=leaseHeld?[path.join(lease,'active-run','retained-run.json')]:
    fs.readdirSync(path.join(lease,'runs')).map(name=>path.join(lease,'runs',name,'run.json')).filter(p=>fs.existsSync(p));
  assert.equal(records.length,1);
  const receipt=read(records[0]);
  const spawned=fs.existsSync(marker);
  assert.equal(inventoryCalls,1);
  if(expected==='hold'){
    assert.equal(spawned,true);
    assert.equal(leaseHeld,true);
    assert.equal(snapshots,2);
    assert.equal(request.state,'needs-review');
    assert.equal(request.leaseReleaseCompleted,false);
    assert.equal(receipt.existingContainerUncertainty,true);
    assert.match(error,/Owned workload stop unconfirmed/);
  }else if(expected==='refuse'){
    assert.equal(spawned,false);
    assert.equal(leaseHeld,false);
    assert.equal(snapshots,1);
    assert.equal(request.ownershipSealed,false);
    assert.equal(request.state,'finished');
    assert.equal(request.leaseReleaseCompleted,true);
    assert.match(error,/disk-growth budget was exceeded/);
  }else{
    assert.equal(spawned,true);
    assert.equal(leaseHeld,false);
    assert.equal(snapshots,2);
    assert.equal(exitCode,0);
    assert.equal(request.state,'finished');
    assert.equal(request.leaseReleaseCompleted,true);
  }
  const passed=expected==='allow';
  assert.equal(receipt.exitCode,passed?0:75);
  assert.equal(receipt.completed,passed);
  assert.equal(receipt.minimumFreeBytesObserved,freeAtStart-inventoryLoss-snapshotLoss);
  return {label,spawned,leaseHeld,requestState:request.state,leaseReleased:request.leaseReleaseCompleted,
    receiptExitCode:receipt.exitCode,chargedBytes:freeAtStart-receipt.minimumFreeBytesObserved};
}

const cases=[await run('slow-inventory',{inventoryLoss:limit+1,containers:['preexisting-fixture'],expected:variant==='baseline'?'hold':'refuse'})];
if(variant==='candidate'){
  cases.push(await run('snapshot-loss',{snapshotLoss:limit+1,containers:['preexisting-fixture'],expected:'refuse'}));
  cases.push(await run('exact-limit',{inventoryLoss:limit,containers:['preexisting-fixture'],expected:'allow'}));
  cases.push(await run('unchanged-capacity',{expected:'allow'}));
}
console.log(JSON.stringify({variant,cases,isolatedLeases:true,realShellChildren:true,capacityAndContainerInventoryInjected:true}));
