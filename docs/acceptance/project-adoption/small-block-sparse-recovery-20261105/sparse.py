from pathlib import Path
import json,os,sys,fcntl,struct,hashlib,stat,subprocess,plistlib,signal,time,datetime
B=Path(__file__).resolve().parent;R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
F=json.loads((B/'frozen.json').read_text())
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert all(sha(p)==h for p,h in F['inputs'].items())
def write(p,v):
 with Path(p).open('x')as f:os.fchmod(f.fileno(),0o600);json.dump(v,f,indent=2);f.write('\n')
def db():
 d=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect','advocates-local-advocates-db-1'],text=True,timeout=15))[0]
 return dict(id=d['Id'],running=d['State']['Running'],startedAt=d['State']['StartedAt'],restartCount=d['RestartCount'])
initialDb=db();assert initialDb['running']
lease=json.loads((C/'active-run/owner.json').read_text());assert lease['token']==os.environ.get('WARGAME_STORAGE_RUN_TOKEN')
request=json.loads((C/'scheduler/requests'/f"{lease['requestId']}.json").read_text())
assert request['enforcement']=='native-exclusive'and request['exclusive']and request['limits']['diskBytes']==536870912
assert struct.calcsize('=IIqq')==24
sdk=Path(F['sdkHeader']);header=sdk.read_text();assert '#define F_PUNCHHOLE     99'in header and 'typedef struct fpunchhole'in header
block=4096;zeros=b'\0'*block
began=time.monotonic();report=dict(status='running-byte-preserving-sparse-recovery',images=[],fixtureControls=0,filesDeleted=0,logicalBytesChanged=0,installedGuardChanged=False,parallelActivated=False,machineLimitsChanged=False,requestId=request['id'])
def interrupted(s,f):raise RuntimeError('ZERO_ONLY_RECOVERY_INTERRUPTED')
for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,interrupted)
signal.alarm(600)
def identity(fd,row):
 s=os.fstat(fd)
 if not(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_uid==os.getuid()and s.st_dev==row['device']and s.st_ino==row['inode']and s.st_size==row['size']):raise RuntimeError('STALE_OR_UNOWNED_FILE')
 return s
def zeroOnly(fd,row,offset,length,journal):
 identity(fd,row)
 if offset<0 or length<=0 or offset%block or length%block or offset+length>row['size']:raise RuntimeError('INVALID_ALIGNED_ZERO_RANGE')
 for at in range(offset,offset+length,block):
  if os.pread(fd,block,at)!=zeros:raise RuntimeError('NONZERO_RANGE_REFUSED')
 entry=dict(offset=offset,length=length,verifiedAllZeroBefore=True)
 journal.append(entry)
 fcntl.fcntl(fd,99,struct.pack('=IIqq',0,0,offset,length))
 os.fsync(fd)
 for at in range(offset,offset+length,block):
  if os.pread(fd,block,at)!=zeros:raise RuntimeError('ZERO_RANGE_POST_READ_MISMATCH')
 entry['allZeroAfter']=True
def description(p):
 s=p.lstat()
 return dict(device=s.st_dev,inode=s.st_ino,size=s.st_size,mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,sha256=sha(p),allocatedBytes=s.st_blocks*512)
try:
 fixture=B/'thirty-two-kib-patterned-fixture.bin'
 with fixture.open('xb')as f:
  os.fchmod(f.fileno(),0o600)
  for i in range(8):f.write(zeros if i%2 else bytes([65+i])*block)
  f.flush();os.fsync(f.fileno())
 expected=description(fixture);fd=os.open(fixture,os.O_RDWR|os.O_NOFOLLOW)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);controls=[]
  try:zeroOnly(fd,expected,0,block,[])
  except RuntimeError as e:assert str(e)=='NONZERO_RANGE_REFUSED';controls.append('nonzero-range-refused-before-fcntl')
  else:raise RuntimeError('NONZERO_CONTROL_DID_NOT_REFUSE')
  wrong={**expected,'inode':expected['inode']+1}
  try:zeroOnly(fd,wrong,block,block,[])
  except RuntimeError as e:assert str(e)=='STALE_OR_UNOWNED_FILE';controls.append('stale-identity-refused-before-fcntl')
  else:raise RuntimeError('STALE_CONTROL_DID_NOT_REFUSE')
  journal=[];zeroOnly(fd,expected,block,block,journal)
 finally:os.close(fd)
 actual=description(fixture);assert actual['sha256']==expected['sha256']and actual['size']==expected['size']and actual['inode']==expected['inode']and actual['allocatedBytes']<expected['allocatedBytes']
 controls.append('real-filesystem-zero-range-preserves-entire-file-digest-size-inode-and-reduces-allocation')
 write(B/'fixture-review.json',dict(status='passed-three-actual-zero-only-controls',controls=controls,before=expected,after=actual,journal=journal))
 report['fixtureControls']=3
 for index,row in enumerate(json.loads((B/'images.json').read_text())):
  p=Path(row['path']);assert p.name=='workspace.dmg'and p.parent.parent==R/'.tools/buildctl'and not p.is_symlink()
  info=plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil','info','-plist'],timeout=20))
  assert not any(x.get('image-path')==str(p)for x in info.get('images',[])),'IMAGE_CURRENTLY_MOUNTED'
  openCheck=subprocess.run(['/usr/sbin/lsof','-nP','--',str(p)],capture_output=True,text=True,timeout=15)
  assert openCheck.returncode==1 and openCheck.stdout=='','SOURCE_IMAGE_OPEN'
  original=json.loads((C/'scheduler/requests'/f'{p.parent.name}.json').read_text());assert original['state']=='finished'
  for cid in original.get('containerIds',[]):
   d=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',cid],text=True,timeout=15))[0]
   assert not d['State']['Running']and not d['State']['Restarting']and d['State']['Pid']==0
  current=p.lstat();assert all(row[k]==v for k,v in [('device',current.st_dev),('inode',current.st_ino),('size',current.st_size),('mtimeNs',current.st_mtime_ns),('ctimeNs',current.st_ctime_ns)])
  assert sha(p)==row['sha256'],'SOURCE_IMAGE_HASH_CHANGED'
  row=dict(row);ranges=[];offset=0
  with p.open('rb') as source:
   while chunk:=source.read(block):
    if len(chunk)==block and chunk==zeros:
     if ranges and ranges[-1]['offset']+ranges[-1]['length']==offset:ranges[-1]['length']+=block
     else:ranges.append(dict(offset=offset,length=block))
    offset+=len(chunk)
  assert offset==row['size']
  row['zeroRanges']=ranges;row['allZeroAlignedBytes']=sum(x['length']for x in ranges)
  write(B/f'image-{index}-readonly-zero-survey.json',dict(path=str(p),sourceSha256=row['sha256'],sourceBytes=offset,zeroRanges=ranges,allZeroAlignedBytes=row['allZeroAlignedBytes'],noFilesystemChangesYet=True))
  before=description(p);journal=[];fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW)
  try:
   fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);identity(fd,row)
   with (B/f'image-{index}-journal.jsonl').open('x')as ledger:
    os.fchmod(ledger.fileno(),0o600)
    for part in row['zeroRanges']:
     ledger.write(json.dumps(dict(kind='intent',**part))+'\n');ledger.flush();os.fsync(ledger.fileno())
     zeroOnly(fd,row,part['offset'],part['length'],journal)
     ledger.write(json.dumps(dict(kind='completed',**journal[-1]))+'\n');ledger.flush();os.fsync(ledger.fileno())
  finally:os.close(fd)
  after=description(p)
  assert all(after[k]==before[k]for k in ['sha256','size','inode','device','mode','uid']),'WHOLE_IMAGE_PRESERVATION_FAILED'
  assert after['allocatedBytes']<=before['allocatedBytes'],'ALLOCATION_INCREASED'
  value=dict(path=str(p),before=before,after=after,zeroRanges=len(journal),verifiedZeroBytes=sum(x['length']for x in journal),allocationReductionBytes=before['allocatedBytes']-after['allocatedBytes'],wholeImageSha256Identical=True,fileIdentityAndSizePreserved=True,filesystemAllocationTimestampsMayChange=True,originalFinishedRequestUnchanged=True,filesDeleted=0)
  report['images'].append(value);write(B/f'image-{index}-review.json',value)
 assert db()==initialDb
 report.update(status='passed-three-small-block-closed-images-byte-identical-sparse-recovery',allocationReductionBytes=sum(x['allocationReductionBytes']for x in report['images']),allWholeImageDigestsIdentical=True,unrelatedDatabaseIdentityUnchanged=True)
except BaseException as error:
 report.update(status='failed-byte-preserving-sparse-recovery',failureType=type(error).__name__,failureCode=str(error)if str(error).isupper()else'PRIVATE_DIAGNOSTIC_REQUIRED')
 raise
finally:
 signal.alarm(0);report['elapsedSeconds']=time.monotonic()-began;report['finishedAtUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(B/'result.json',report)
