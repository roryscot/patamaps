import hashlib,json,os,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
work=ROOT/'.tools/intel-toolchain';config=json.loads((work/'components.json').read_bytes());prefix=Path(config['prefix']);prefix.mkdir(exist_ok=True)
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('intel-toolchain-assembly-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir();(out/'driver.py').write_bytes(Path(__file__).read_bytes())
limit=120000000;written=0;complete=True;inventory={};partial=[]
def digest(stream):
 h=hashlib.sha256()
 for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return 'sha256:'+h.hexdigest()
for component in config['components']:
 archive=Path(component['archive'])
 with archive.open('rb') as f:assert digest(f)==component['archiveDigest']
 with tarfile.open(archive,'r:xz') as tar:
  for m in tar.getmembers():
   if not m.name.startswith(component['memberPrefix']) or m.isdir() or m.name==component['memberPrefix']+'manifest.in':continue
   rel=PurePosixPath(m.name[len(component['memberPrefix']):]);assert rel.parts and not rel.is_absolute() and '..' not in rel.parts
   target=prefix.joinpath(*rel.parts);assert target.parent.resolve().is_relative_to(prefix.resolve())
   if m.issym():
    link=PurePosixPath(m.linkname);assert not link.is_absolute();assert (target.parent/m.linkname).resolve().is_relative_to(prefix.resolve())
    if target.is_symlink():assert os.readlink(target)==m.linkname
    else:assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(m.linkname)
    inventory[rel.as_posix()]={'path':rel.as_posix(),'symlink':m.linkname};continue
   assert m.isfile() or m.islnk();assert not target.is_symlink()
   with tar.extractfile(m) as stream:
    size=m.size if m.isfile() else tar.getmember(m.linkname).size
    old=target.stat().st_size if target.exists() else 0;assert old<=size
    expected=hashlib.sha256()
    if old:
     with target.open('rb') as prior:
      for block in iter(lambda:prior.read(1024*1024),b''):assert block==stream.read(len(block)),str(target);expected.update(block)
    amount=min(size-old,limit-written)
    if amount:
     target.parent.mkdir(parents=True,exist_ok=True)
     with target.open('ab' if target.exists() else 'xb') as dest:
      left=amount
      while left:
       block=stream.read(min(left,1024*1024));assert block;dest.write(block);expected.update(block);left-=len(block);written+=len(block)
    if old+amount<size:
     complete=False
     if amount:partial.append({'path':rel.as_posix(),'bytes':old+amount,'archivePrefixVerified':True})
     continue
    assert target.is_file() and target.stat().st_size==size
    with target.open('rb') as f:assert digest(f)=='sha256:'+expected.hexdigest(),str(target)
    assert not m.mode&0o7000;target.chmod(m.mode&0o777)
    row={'path':rel.as_posix(),'bytes':size,'digest':'sha256:'+expected.hexdigest(),'mode':m.mode&0o777}
    if rel.as_posix() in inventory:assert inventory[rel.as_posix()]==row
    inventory[rel.as_posix()]=row
report={'status':'passed','complete':complete,'prefix':str(prefix),'bytesWritten':written,'stageGrowthLimit':limit,'verifiedCompleteEntries':len(inventory),'partialFiles':partial,'componentManifestDigest':'sha256:'+hashlib.sha256((work/'components.json').read_bytes()).hexdigest(),'deleted':[],'storageSettingsChanged':False,'recordedAtUtc':datetime.now(timezone.utc).isoformat()}
if complete:
 final=work/'assembly-complete.json';assert not final.exists();final.write_text(json.dumps({'status':'all-official-component-payloads-byte-verified','inventory':list(inventory.values()),**report},indent=2)+'\n')
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');(work/'state.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'complete':complete,'bytesWritten':written,'receipt':str(out/'receipt.json')}),flush=True)
