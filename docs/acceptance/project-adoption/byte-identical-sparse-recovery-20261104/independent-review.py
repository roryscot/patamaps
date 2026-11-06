from pathlib import Path
import json,hashlib,subprocess,plistlib,re,datetime
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/zero-preserving-closed-images-20261104';P=R/'.tools/retention-review-20261104-closed-quota-image'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
result=read(B/'result.json');declared=read(B/'images.json')
assert result['status']=='passed-three-closed-images-byte-identical-sparse-recovery'and len(result['images'])==len(declared)==3
assert result['filesDeleted']==result['logicalBytesChanged']==0 and not result['machineLimitsChanged']and not result['installedGuardChanged']and not result['parallelActivated']
assert result['fixtureControls']==3 and result['elapsedSeconds']<=600 and read(B/'supervisor-exit.json')['exitCode']==0
fixture=read(B/'fixture-review.json')
assert fixture['status']=='passed-three-actual-zero-only-controls'and len(fixture['controls'])==3
expected=hashlib.sha256()
for i in range(8):expected.update(b'\0'*1048576 if i%2 else bytes([65+i])*1048576)
assert fixture['before']['sha256']==fixture['after']['sha256']==expected.hexdigest()
assert sha(B/'eight-mib-patterned-fixture.bin')==expected.hexdigest()
assert fixture['before']['allocatedBytes']-fixture['after']['allocatedBytes']==1048576
assert fixture['before']['size']==fixture['after']['size']==8388608 and fixture['before']['inode']==fixture['after']['inode']
info=plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil','info','-plist'],timeout=20));rows=[]
C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
for i,(entry,actual)in enumerate(zip(declared,result['images'])):
 p=Path(entry['path']);assert str(p)==actual['path']and p.is_file()and not p.is_symlink()
 assert not any(x.get('image-path')==str(p)for x in info.get('images',[]))
 s=p.lstat();before=actual['before'];after=actual['after']
 assert sha(p)==entry['sha256']==before['sha256']==after['sha256']
 assert s.st_ino==entry['inode']==before['inode']==after['inode']and s.st_dev==entry['device']==before['device']==after['device']
 assert s.st_size==entry['size']==before['size']==after['size']
 assert s.st_uid==entry['uid']==before['uid']==after['uid']and s.st_nlink==1 and s.st_mode&0o777==before['mode']==after['mode']
 assert s.st_blocks*512==after['allocatedBytes']
 journal=read(B/f'image-{i}-journal.json')
 assert len(journal)==len(entry['zeroRanges'])and actual['zeroRanges']==len(journal)
 assert all(x['verifiedAllZeroBefore']and x['allZeroAfter']and x['offset']==y['offset']and x['length']==y['length']for x,y in zip(journal,entry['zeroRanges']))
 assert all(x['offset']%1048576==0 and x['length']%1048576==0 and x['length']>0 and x['offset']+x['length']<=s.st_size for x in journal)
 assert sum(x['length']for x in journal)==entry['allZeroAlignedBytes']==actual['verifiedZeroBytes']==actual['allocationReductionBytes']
 assert before['allocatedBytes']-after['allocatedBytes']==actual['allocationReductionBytes']and actual['filesDeleted']==0
 original=read(C/'scheduler/requests'/f'{p.parent.name}.json');assert original['state']=='finished'
 rows.append(dict(path=str(p),logicalBytes=s.st_size,sha256=entry['sha256'],wholeImageRehashedAndIdentical=True,inodeSizeModeAndOwnerPreserved=True,allocatedBytesBefore=before['allocatedBytes'],allocatedBytesAfter=after['allocatedBytes'],allocationReductionBytes=actual['allocationReductionBytes'],zeroRanges=len(journal),closed=True,originalRequestStillFinished=True,filesystemAllocationMetadataTimestampsMayChange=True))
assert sum(x['allocationReductionBytes']for x in rows)==3470786560==result['allocationReductionBytes']
stream=(B/'supervisor.stdout').read_text()+(B/'supervisor.stderr').read_text();ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
outer=read(C/'runs'/ids[0]/'run.json')
assert outer['completed']and outer['exitCode']==0 and outer['freeBytesAtStart']-outer['minimumFreeBytesObserved']<=536870912
request=read(C/'scheduler/requests'/f"{result['requestId']}.json")
assert request['state']=='finished'and request['leaseReleaseCompleted']and request['enforcement']=='native-exclusive'and request['limits']['diskBytes']==536870912
protected=read(R/'.tools/native-guard-shared-runtime-log-scope-20261104/protected-service-before.json')
db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',protected['id']],text=True,timeout=15))[0]
assert dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==protected
failure=read(P/'preservation/result.json');assert failure['status']=='failed-bounded-image-preservation'and failure['failureCode']=='IMAGE_PRESERVATION_INTERRUPTED'
recovery=P/'preservation/stopped-reservation-recovery';proof=read(recovery/'RECOVERY_PLAN.json');done=read(recovery/'result.json')
assert proof['reservationId']==done['reservationId']=='a382937d-93ed-4a6f-b5cf-906b69ba917c'and len(proof['observations'])==3
assert not done['automaticWorkloadAcceptance']and done['originalQuotaFailurePreserved']
archive=Path(done['archivedLease'])
for n in ['owner','retained-run']:
 original=recovery/f'original-{n}.json'
 assert sha(original)==sha(archive/'lease'/f'{n}.json')
 assert 'sha256:'+sha(original)==proof['originalPreimages'][str(C/'active-run'/f'{n}.json')]
originalRequest=recovery/'original-request.json'
assert 'sha256:'+sha(originalRequest)==proof['originalPreimages'][str(C/'scheduler/requests'/f"{done['reservationId']}.json")]
current=read(C/'scheduler/requests'/f"{done['reservationId']}.json")
assert current['state']=='finished'and current['leaseReleaseCompleted']and current['manualStoppedRecovery']['automaticWorkloadAcceptance']is False
assert (P/'preservation/workspace.dmg.gz').stat().st_size==314956905
review=dict(status='independently-accepted-byte-identical-sparse-recovery',images=rows,allFrozenInputsRehashed=len(F['inputs']),fixtureControls=3,totalLogicalImageBytesRehashed=sum(x['logicalBytes']for x in rows),totalAllocationReductionBytes=3470786560,allOriginalImagesAndLogicalBytesPreserved=True,filesDeleted=0,unrelatedServicesInterrupted=0,unrelatedDatabaseStartIdentityUnchanged=True,canonicalReservation=result['requestId'],canonicalReservationReleased=True,maximumJobGrowthBytes=536870912,machineGrowthCeilingBytes=4000000000,reserveBytes=500000000,retentionCeilingBytes=100000000000,accountingRulesChanged=False,installedGuardChanged=False,parallelActivated=False,failedArchiveAndPartialBytesPreserved=True,failedArchiveExactRecoveryNotClaimed=True,onlyStoppedArchiveReservationManuallyRecovered=True,partialArchiveBytes=314956905,priorDeletionProposalNotExecuted=True,frozenManifestSha256=sha(B/'frozen.json'),reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with(B/'independent-review.json').open('x')as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in review.items()if k!='images'}))
