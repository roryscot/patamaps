import hashlib,json,os,stat,tarfile
from datetime import datetime,timezone
from pathlib import Path
root=Path('/Users/admin/dev/patamaps/patamaps')
out=root/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('additional-extracted-review-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
def digest(stream):
 h=hashlib.sha256()
 for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return 'sha256:'+h.hexdigest()
files=[];archives=[]
for name in ['installed-ekq21tjf','installed-tknc_1d5']:
 work=root/'.tools/capabilities'/name
 distribution=json.loads((work/'package/distribution.json').read_bytes())
 archive=work/'package'/distribution['sourceArchive']['path']
 with archive.open('rb') as stream:archive_digest=digest(stream)
 assert archive_digest==distribution['sourceArchive']['digest']
 source_root,=(work/'source').iterdir()
 expected={}
 for p in sorted(source_root.rglob('*')):
  s=p.lstat()
  if stat.S_ISDIR(s.st_mode):continue
  assert stat.S_ISREG(s.st_mode),str(p)+' is not an ordinary file'
  with p.open('rb') as stream:file_digest=digest(stream)
  member=source_root.name+'/'+p.relative_to(source_root).as_posix()
  expected[member]={'path':str(p),'bytes':s.st_size,'allocatedBytes':s.st_blocks*512,'digest':file_digest,'recoveryArchive':str(archive),'recoveryMember':member}
 seen=set()
 with tarfile.open(archive,'r|gz') as tar:
  for member in tar:
   if member.name not in expected:continue
   assert member.name not in seen and member.isfile()
   item=expected[member.name]
   assert member.size==item['bytes']
   with tar.extractfile(member) as stream:assert digest(stream)==item['digest'],item['path']
   item['recoveryVerified']='Full archived member bytes independently hashed and matched to the current file.'
   seen.add(member.name)
 assert seen==set(expected)
 files.extend(expected.values())
 archives.append({'path':str(archive),'digest':archive_digest,'matchedFiles':len(expected),'preservedSourceRoot':str(source_root)})
 print(json.dumps({'verified':name,'files':len(expected)}),flush=True)
receipt={'status':'exact-deletion-list-recovery-verified-awaiting-owner-approval','verifiedAtUtc':datetime.now(timezone.utc).isoformat(),'files':files,'fileCount':len(files),'bytes':sum(f['bytes'] for f in files),'allocatedBytes':sum(f['allocatedBytes'] for f in files),'archivesPreserved':archives,'preserved':'Working source checkout, all verified source/native archives, installed binaries, consumer workspaces, logs, receipts, current accepted installation, all parent directories and every unlisted file.','lostAtOriginalPaths':'Only the inventoried extracted files would disappear. Full member hashes verify recoverable bytes in the retained archives; restoring the original paths has not been exercised. The two old extracted source trees would be empty until restored.','directoriesDeleted':False,'deleted':[],'storageBlocker':{'supervisorRecord':'/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/bb3122c9-97b0-4f63-923d-48402d819790/run.json','milestone':'compiler','checksStarted':False,'reason':'Below 1 GB reserve'}}
p=out/'inventory.json';p.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'inventory':str(p),'fileCount':receipt['fileCount'],'bytes':receipt['bytes'],'allocatedBytes':receipt['allocatedBytes']}),flush=True)
