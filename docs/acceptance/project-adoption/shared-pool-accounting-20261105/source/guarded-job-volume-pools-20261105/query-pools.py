from pathlib import Path
import os,sys,json,subprocess,plistlib,re
locations=json.loads(sys.argv[1]);assert isinstance(locations,list)and locations and all(isinstance(p,str)and os.path.isabs(p)for p in locations)
tracked={}
for location in locations:
 s=os.stat(location)
 if s.st_dev not in tracked:tracked[s.st_dev]=location
bindings=[];pools={};containers={}
for device,location in tracked.items():
 output=subprocess.check_output(['/bin/df','-P',location],text=True,timeout=2)
 name=output.splitlines()[-1].split()[0]
 if not re.fullmatch(r'/dev/disk[0-9]+(?:s[0-9]+)*',name):continue
 info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist',name],timeout=2))
 assert info.get('DeviceIdentifier')==name.removeprefix('/dev/')
 if info.get('FilesystemType')!='apfs':continue
 reference=info.get('APFSContainerReference');assert isinstance(reference,str)and re.fullmatch(r'disk[0-9]+',reference)
 if reference not in containers:
  doc=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','apfs','list','-plist',reference],timeout=3))
  matches=[x for x in doc.get('Containers',[])if x.get('ContainerReference')==reference];assert len(matches)==1
  containers[reference]=matches[0]
 container=containers[reference];uuid=container.get('APFSContainerUUID');free=container.get('CapacityFree');ceiling=container.get('CapacityCeiling')
 assert isinstance(uuid,str)and re.fullmatch(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}',uuid)
 assert type(free)is int and type(ceiling)is int and 0<=free<=ceiling<=9007199254740991
 volume=[x for x in container.get('Volumes',[])if x.get('DeviceIdentifier')==info['DeviceIdentifier']];assert len(volume)==1
 assert volume[0]['APFSVolumeUUID']==info.get('VolumeUUID')and os.stat(info['MountPoint']).st_dev==device
 pool='apfs:'+uuid.upper();pools[pool]=free;bindings.append(dict(device=device,pool=pool))
print(json.dumps(dict(version=1,devices=sorted(bindings,key=lambda x:x['device']),pools=[dict(id=k,freeBytes=v)for k,v in sorted(pools.items())])))
