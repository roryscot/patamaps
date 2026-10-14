import hashlib,json,os,tarfile,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path('/Users/admin/dev/patamaps/patamaps');sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
work=root/'.tools/capabilities/installed-bmgsq0pg';distribution=json.loads((work/'package/distribution.json').read_bytes());archive_path=work/'package'/distribution['sourceArchive']['path']
prefix=distribution['sourceArchive']['path'].removesuffix('-source.tar.gz');source=work/'source'/prefix
out=root/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('installed-extraction-stage-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
def digest(stream):
 h=hashlib.sha256()
 for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return 'sha256:'+h.hexdigest()
with archive_path.open('rb') as stream:assert digest(stream)==distribution['sourceArchive']['digest']
written=0;restored=[];verified=0;partial=[]
with tarfile.open(archive_path,'r:gz') as archive:
 for member in archive.getmembers():
  assert member.isfile() and member.name.startswith(prefix+'/')
  relative=Path(member.name).relative_to(prefix);assert '..' not in relative.parts and not relative.is_absolute()
  path=source/relative
  with archive.extractfile(member) as stream:
   old_size=path.stat().st_size if path.exists() else 0
   assert not path.is_symlink() and old_size<=member.size
   if old_size:
    with path.open('rb') as old:
     for block in iter(lambda:old.read(1024*1024),b''):assert block==stream.read(len(block)),str(path)
   if old_size==member.size and path.exists():verified+=1;continue
   remaining=member.size-old_size
   if written+remaining>120000000:continue
   if old_size:
    with path.open('rb') as old:partial.append({'path':str(path),'priorBytes':old_size,'priorDigest':digest(old),'recovery':'Verified exact retained archive prefix; bytes preserved and suffix appended.'})
   path.parent.mkdir(parents=True,exist_ok=True)
   with path.open('ab' if path.exists() else 'xb') as target:
    for block in iter(lambda:stream.read(1024*1024),b''):target.write(block)
   os.chmod(path,member.mode)
   assert path.stat().st_size==member.size
   written+=remaining;restored.append(relative.as_posix())
report={'status':'passed','sourceArchive':str(archive_path),'sourceArchiveDigest':distribution['sourceArchive']['digest'],'sourceRoot':str(source),'byteGrowthLimit':120000000,'bytesAppendedOrCreated':written,'existingCompleteFilesVerified':verified,'filesCompleted':restored,'partialFilesCompleted':partial,'deleted':[],'storageSettingsChanged':False}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'receipt':str((out/'receipt.json').relative_to(root)),'bytesWritten':written,'filesCompleted':len(restored),'existingCompleteVerified':verified}),flush=True)
