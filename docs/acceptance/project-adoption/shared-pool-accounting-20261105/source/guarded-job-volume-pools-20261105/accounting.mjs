// Candidate physical-pool accounting. Policy ceilings and owned-volume charge unchanged.
export {ownedVolumeUsage} from '../guarded-job-volume-accounting-20261104/accounting.mjs';
import {conservativeCapacity as legacyCapacity} from '../guarded-job-volume-accounting-20261104/accounting.mjs';
const valid=n=>Number.isSafeInteger(n)&&n>=0;
function schema(document,disks){
 if(!document||document.version!==1||Object.keys(document).sort().join(',')!=='devices,pools,version'||!Array.isArray(document.devices)||!Array.isArray(document.pools))throw Error('Unknown storage pool inventory');
 const pools=new Map(),bindings=new Map();
 for(const row of document.pools){
  if(!row||Object.keys(row).sort().join(',')!=='freeBytes,id'||typeof row.id!=='string'||!row.id||row.id.length>200||pools.has(row.id)||!valid(row.freeBytes))throw Error('Ambiguous storage pool capacity');
  pools.set(row.id,row.freeBytes);
 }
 for(const row of document.devices){
  if(!row||Object.keys(row).sort().join(',')!=='device,pool'||!valid(row.device)||!disks.has(row.device)||bindings.has(row.device)||!pools.has(row.pool))throw Error('Ambiguous filesystem pool binding');
  bindings.set(row.device,row.pool);
 }
 if([...pools.keys()].some(id=>![...bindings.values()].includes(id)))throw Error('Unbound storage pool');
 return {pools,bindings,signature:JSON.stringify([...bindings].sort((a,b)=>a[0]-b[0]))};
}
export function conservativeCapacity(readDisks,readVolumes,readPools){
 if(readPools===undefined)return legacyCapacity(readDisks,readVolumes);
 let initial=null,initialVolume=null,initialPools=null,initialSignature=null,initialMinimum=null;
 return ()=>{
  const disks=readDisks(),volume=readVolumes();
  if(!(disks instanceof Map)||!disks.size||![...disks].every(([dev,bytes])=>valid(dev)&&valid(bytes)))throw Error('Unknown filesystem capacity');
  if(!valid(volume?.bytes))throw Error('Unknown owned volume usage');
  const parsed=schema(readPools(),disks);
  if(initial===null){
   initial=new Map(disks);initialVolume=volume.bytes;initialPools=new Map(parsed.pools);initialSignature=parsed.signature;
   initialMinimum=Math.min(...disks.values(),...parsed.pools.values());
  }
  if(disks.size!==initial.size||[...initial.keys()].some(k=>!disks.has(k))||parsed.signature!==initialSignature||parsed.pools.size!==initialPools.size||[...initialPools.keys()].some(k=>!parsed.pools.has(k)))throw Error('Filesystem or pool identity changed');
  const growth=new Map();
  for(const[dev,before]of initial){
   const pool=parsed.bindings.get(dev),key=pool===undefined?'device:'+dev:'pool:'+pool;
   growth.set(key,Math.max(growth.get(key)??0,Math.max(0,before-disks.get(dev))));
  }
  for(const[id,before]of initialPools){
   const key='pool:'+id;
   growth.set(key,Math.max(growth.get(key)??0,Math.max(0,before-parsed.pools.get(id))));
  }
  const physicalGrowth=[...growth.values()].reduce((sum,n)=>sum+n,0);
  if(!valid(physicalGrowth))throw Error('Physical growth overflow');
  const volumeGrowth=Math.max(0,volume.bytes-initialVolume);
  const charged=physicalGrowth+volumeGrowth;if(!valid(charged))throw Error('Capacity charge overflow');
  // Shared physical free space is charged once. Independent pools add.
  // Per-volume capacity loss can only increase a pool's charge.
  // Docker volume growth is still intentionally additionally charged.
  return Math.min(...disks.values(),...parsed.pools.values(),initialMinimum-charged);
 };
}
