from pathlib import Path
import json,hashlib,tarfile,stat,datetime
repo=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
review=repo/'docs/acceptance/project-adoption/extracted-source-cleanup-review-20261020';review.mkdir(exist_ok=False)
roots=['installed-fbbrad0l','installed-79sti59b','installed-stoub0kb','installed-nwstqeg6','installed-ebuqh4fy','installed-mine0f7b','installed-bwdyjx59','installed-qsd41hw1','installed-4xe55_ip']
def digest(file):
 h=hashlib.sha256()
 while True:
  b=file.read(1024*1024)
  if not b:break
  h.update(b)
 return h.hexdigest()
records=[];summaries=[];excluded=[]
for name in roots:
 home=repo/'.tools/capabilities'/name;d=json.loads((home/'package/distribution.json').read_text());archive=home/'package'/d['sourceArchive']['path']
 with archive.open('rb') as f:sha=digest(f)
 assert 'sha256:'+sha==d['sourceArchive']['digest']
 count=0;allocated=0
 with tarfile.open(archive,'r|gz') as tar:
  seen=set()
  for member in tar:
   assert member.name not in seen;seen.add(member.name)
   parts=Path(member.name).parts
   assert not member.name.startswith('/') and '..' not in parts
   if not member.isfile():continue
   p=home/'source'/member.name
   if not p.exists():continue
   st=p.lstat()
   if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size!=member.size:
    excluded.append({'path':str(p),'reason':'not an ordinary singly-linked equal-size archive member'});continue
   with tar.extractfile(member) as f:expected=digest(f)
   with p.open('rb') as f:actual=digest(f)
   after=p.lstat()
   assert (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
   if expected!=actual:excluded.append({'path':str(p),'reason':'bytes differ from retained archive'});continue
   records.append(dict(path=str(p),type='regular-file',device=st.st_dev,inode=st.st_ino,size=st.st_size,allocatedBytes=st.st_blocks*512,mtimeNs=st.st_mtime_ns,mode=stat.S_IMODE(st.st_mode),links=1,sha256=actual,recoveryArchive=str(archive),archiveSha256=sha,member=member.name))
   count+=1;allocated+=st.st_blocks*512
 summaries.append(dict(installation=name,verifiedFiles=count,allocatedBytes=allocated,archive=str(archive),archiveSha256=sha))
 print(json.dumps(summaries[-1]),flush=True)
with (review/'inventory.jsonl').open('x') as f:
 for r in records:f.write(json.dumps(r,sort_keys=True)+'\n')
out=dict(status='proposal-only-no-deletion',recordedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=len(records),allocatedBytes=sum(x['allocatedBytes'] for x in records),installations=summaries,excludedCount=len(excluded),allArchivesMatchDistributionDigests=True,allListedFilesMatchExactArchiveMembers=True,restorationExercised=False,filesDeleted=0,inventorySha256=hashlib.sha256((review/'inventory.jsonl').read_bytes()).hexdigest())
(review/'summary.json').write_text(json.dumps(out,indent=2)+'\n');(review/'excluded.json').write_text(json.dumps(excluded,indent=2)+'\n')
print('DONE',json.dumps({k:v for k,v in out.items() if k!='installations'}),flush=True)
