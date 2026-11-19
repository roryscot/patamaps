// Additional conservative accounting for labelled owned Docker volumes.
// No policy/guard installation change; native exclusive fallback remains.
export function ownedVolumeUsage(document,project){
 if(!document||!Array.isArray(document.Volumes))throw Error('Incomplete Docker volume inventory');
 let bytes=0,count=0;const seen=new Set();
 for(const volume of document.Volumes){
  const labels=volume?.Labels;
  if(labels?.['buildctl.project']!==project)continue;
  if(typeof volume.Name!=='string'||!volume.Name||seen.has(volume.Name))throw Error('Ambiguous owned volume identity');
  seen.add(volume.Name);
  const size=volume.UsageData?.Size;
  if(!Number.isSafeInteger(size)||size<0)throw Error('Unknown owned volume allocation');
  bytes+=size;if(!Number.isSafeInteger(bytes))throw Error('Owned volume allocation overflow');
  count++;
 }
 return {bytes,count};
}
export function conservativeCapacity(readDisks,readVolumes){
 let initial=null,initialVolume=null;
 return ()=>{
  const disks=readDisks(),volume=readVolumes();
  if(!(disks instanceof Map)||!disks.size||![...disks.values()].every(x=>Number.isSafeInteger(x)&&x>=0))throw Error('Unknown filesystem capacity');
  if(!Number.isSafeInteger(volume.bytes)||volume.bytes<0)throw Error('Unknown owned volume usage');
  if(initial===null){initial=new Map(disks);initialVolume=volume.bytes;}
  if(disks.size!==initial.size||[...initial.keys()].some(k=>!disks.has(k)))throw Error('Filesystem identity changed');
  const physicalGrowth=[...initial].reduce((sum,[device,free])=>sum+Math.max(0,free-disks.get(device)),0);
  const volumeGrowth=Math.max(0,volume.bytes-initialVolume);
  // Docker growth can already reduce host free space. Double charging is intentional.
  return Math.min(...disks.values(),Math.min(...initial.values())-physicalGrowth-volumeGrowth);
 };
}
