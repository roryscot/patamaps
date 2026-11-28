from pathlib import Path
import json,hashlib,subprocess,re,plistlib,datetime
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/zero-preserving-small-block-closed-images-20261105';C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
result=read(B/'result.json');declared=read(B/'images.json')
assert result['status']=='passed-three-small-block-closed-images-byte-identical-sparse-recovery'and len(result['images'])==len(declared)==3
assert result['filesDeleted']==result['logicalBytesChanged']==0 and result['fixtureControls']==3 and result['elapsedSeconds']<=600
assert read(B/'supervisor-exit.json')['exitCode']==0
expected=hashlib.sha256()
for i in range(8):expected.update(b'\0'*4096 if i%2 else bytes([65+i])*4096)
fixture=read(B/'fixture-review.json')
assert fixture['status']=='passed-three-actual-zero-only-controls'and sha(B/'thirty-two-kib-patterned-fixture.bin')==fixture['before']['sha256']==fixture['after']['sha256']==expected.hexdigest()
assert fixture['before']['allocatedBytes']-fixture['after']['allocatedBytes']==4096
info=plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil','info','-plist'],timeout=20));rows=[]
for i,(entry,actual)in enumerate(zip(declared,result['images'])):
 p=Path(entry['path']);s=p.lstat()
 assert not p.is_symlink()and str(p)==actual['path']and not any(x.get('image-path')==str(p)for x in info.get('images',[]))
 assert sha(p)==entry['sha256']==actual['before']['sha256']==actual['after']['sha256']
 assert s.st_ino==entry['inode']==actual['before']['inode']==actual['after']['inode']and s.st_dev==entry['device']==actual['before']['device']==actual['after']['device']
 assert s.st_size==entry['size']==actual['before']['size']==actual['after']['size']
 assert s.st_uid==entry['uid']==actual['before']['uid']==actual['after']['uid']and s.st_nlink==1
 assert s.st_mode&0o777==entry['mode']==actual['before']['mode']==actual['after']['mode']
 assert s.st_blocks*512==actual['after']['allocatedBytes']
 survey=read(B/f'image-{i}-readonly-zero-survey.json');ledger=[json.loads(line)for line in(B/f'image-{i}-journal.jsonl').read_text().splitlines()]
 assert len(ledger)%2==0
 journal=[]
 for at in range(0,len(ledger),2):
  intent,done=ledger[at:at+2]
  assert intent['kind']=='intent'and done['kind']=='completed'and intent['offset']==done['offset']and intent['length']==done['length']
  journal.append({k:v for k,v in done.items()if k!='kind'})
 assert survey['path']==str(p)and survey['sourceSha256']==entry['sha256']and survey['sourceBytes']==s.st_size and survey['noFilesystemChangesYet']
 assert len(journal)==len(survey['zeroRanges'])==actual['zeroRanges']
 assert all(x['offset']==y['offset']and x['length']==y['length']and x['verifiedAllZeroBefore']and x['allZeroAfter']for x,y in zip(journal,survey['zeroRanges']))
 assert all(x['offset']%4096==0 and x['length']%4096==0 and x['length']>0 and x['offset']+x['length']<=s.st_size for x in journal)
 total=sum(x['length']for x in journal)
 assert total==survey['allZeroAlignedBytes']==actual['verifiedZeroBytes']
 assert 0<=actual['allocationReductionBytes']==actual['before']['allocatedBytes']-actual['after']['allocatedBytes']<=total
 original=read(C/'scheduler/requests'/f'{p.parent.name}.json');assert original['state']=='finished'
 rows.append(dict(path=str(p),logicalBytes=s.st_size,sha256=entry['sha256'],wholeFileRehashedAndIdentical=True,inodeSizeModeOwnerPreserved=True,allocatedBytesBefore=actual['before']['allocatedBytes'],allocatedBytesAfter=s.st_blocks*512,allocationReductionBytes=actual['allocationReductionBytes'],zeroRanges=len(journal),closed=True,originalRequestStillFinished=True,allocationMetadataTimestampsMayChange=True))
assert sum(x['allocationReductionBytes']for x in rows)==result['allocationReductionBytes'] and result['allocationReductionBytes']>0
stream=(B/'supervisor.stdout').read_text()+(B/'supervisor.stderr').read_text();ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
guard=read(C/'runs'/ids[0]/'run.json');request=read(C/'scheduler/requests'/f"{result['requestId']}.json")
assert guard['completed']and guard['exitCode']==0 and guard['freeBytesAtStart']-guard['minimumFreeBytesObserved']<=536870912
assert request['state']=='finished'and request['leaseReleaseCompleted']and request['limits']['diskBytes']==536870912 and request['enforcement']=='native-exclusive'
protected=read(R/'.tools/native-guard-shared-runtime-log-scope-20261104/protected-service-before.json')
db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',protected['id']],text=True,timeout=15))[0]
assert dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==protected
review=dict(status='independently-accepted-three-small-block-byte-identical-sparse-recoveries',images=rows,totalLogicalBytesRehashed=sum(x['logicalBytes']for x in rows),allocationReductionBytes=result['allocationReductionBytes'],allImageBytesAndPathsPreserved=True,fixtureControls=3,allFrozenInputsRehashed=len(F['inputs']),canonicalReservation=result['requestId'],canonicalReservationReleased=True,maximumJobGrowthBytes=536870912,machineGrowthCeilingBytes=4000000000,retentionCeilingBytes=100000000000,reserveBytes=500000000,accountingRulesChanged=False,filesDeleted=0,unrelatedServicesInterrupted=0,unrelatedDatabaseStartIdentityUnchanged=True,installedGuardChanged=False,parallelActivated=False,frozenManifestSha256=sha(B/'frozen.json'),reviewerSha256=sha(__file__),reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with(B/'independent-review.json').open('x')as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in review.items()if k!='images'}))
