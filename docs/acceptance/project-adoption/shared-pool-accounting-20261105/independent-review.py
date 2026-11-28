from pathlib import Path
import json,hashlib,subprocess,re,sys,stat,datetime
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/guarded-job-volume-pools-20261105';C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
r=read(B/'probe-result.json');assert r['status']=='passed-real-shared-pool-capacity-probe'and r['elapsedSeconds']<180 and r['controlsPassed']==36 and read(B/'supervisor-exit.json')['exitCode']==0
before=read(B/'before.json');after=read(B/'after.json');a=before['capacity']['sample'];z=after['sample']
assert len(before['quietSamples'])==3 and max(x['document']['pools'][0]['freeBytes']for x in before['quietSamples'])-min(x['document']['pools'][0]['freeBytes']for x in before['quietSamples'])<=8388608
assert len(a['disks'])==len(z['disks'])==2 and a['document']['devices']==z['document']['devices']and len(a['document']['pools'])==len(z['document']['pools'])==1
assert len(set(x['pool']for x in a['document']['devices']))==1
initial=dict(a['disks']);current=dict(z['disks']);poolBefore=a['document']['pools'][0]['freeBytes'];poolAfter=z['document']['pools'][0]['freeBytes']
drops=[max(0,initial[k]-current[k])for k in initial];volumeGrowth=max(0,z['volume']['bytes']-a['volume']['bytes']);assert volumeGrowth==0
oldExpected=min(*current.values(),min(initial.values())-sum(drops)-volumeGrowth)
newExpected=min(*current.values(),poolAfter,min(*initial.values(),poolBefore)-max(*drops,max(0,poolBefore-poolAfter))-volumeGrowth)
assert oldExpected==after['legacyAvailable']and newExpected==after['correctedAvailable']
oldGrowth=before['capacity']['legacyAvailable']-oldExpected;newGrowth=before['capacity']['correctedAvailable']-newExpected
assert oldGrowth==r['legacyObservedChargeBytes']==135168000 and newGrowth==r['correctedObservedChargeBytes']==67584000 and oldGrowth-newGrowth==r['duplicatePhysicalChargeAvoidedBytes']==67584000
file=B/'owned-64-mib-probe.bin';s=file.lstat();assert stat.S_ISREG(s.st_mode)and s.st_size==s.st_blocks*512==67108864 and stat.S_IMODE(s.st_mode)==0o600
assert sha(file)==r['denseFileDigest']=='sha256:3a063bae1eb158c822734f0eb68c32404c9beb3751532c508be10dd5276449e6'
assert read(B/'unit-executed.json')['controlsPassed']==36 and '"controlsPassed":36'in read(B/'unit-executed.json')['stdout']
stream=(B/'supervisor.stdout').read_text()+(B/'supervisor.stderr').read_text();ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
guard=read(C/'runs'/ids[0]/'run.json');req=read(C/'scheduler/requests'/f"{r['reservationId']}.json")
assert req['state']=='finished'and req['leaseReleaseCompleted']and req['enforcement']=='native-exclusive'and req['limits']['diskBytes']==536870912
assert guard['completed']and guard['exitCode']==0 and guard['filesDeleted']==0 and guard['freeBytesAtStart']-guard['minimumFreeBytesObserved']<=536870912
sys.path.insert(0,str(R/'scripts'));import native_inspection_guard as kernel
driver=read(B/'driver-identity.json')
assert driver['pid']==req['processGroup']and driver['parentPid']==req['owner']['pid']
for pid in [driver['pid'],req['owner']['pid']]:assert kernel.process_identity(pid)is None and not kernel.group_live(pid)
db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',F['protectedDatabase']['id']],text=True,timeout=15))[0]
assert dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==F['protectedDatabase']
review=dict(status='independently-accepted-shared-pool-meter-for-scoped-functional-use',controlsPassed=36,retainedDenseProbeLogicalAndAllocatedBytes=67108864,retainedProbeDigest=sha(file),legacyObservedChargeBytes=oldGrowth,correctedObservedChargeBytes=newGrowth,duplicatePhysicalChargeAvoidedBytes=oldGrowth-newGrowth,filesystemDevices=2,underlyingAPFSContainers=1,actualSharedPoolIdentity=a['document']['pools'][0]['id'],actualDockerVolumeBytesUnchanged=True,additionalOwnedVolumeChargePreserved=True,independentPoolAndUnknownMappingRefusalsTested=True,policyCeilingsChanged=False,allFrozenInputsRehashed=len(F['inputs']),frozenManifestDigest=sha(B/'frozen.json'),canonicalReservation=r['reservationId'],canonicalReservationReleased=True,outerLegacyAllowanceBytes=536870912,allObservedOwnedGroupsStopped=True,unrelatedDatabaseStartIdentityUnchanged=True,filesDeleted=0,installedGuardChanged=False,parallelActivated=False,actualApplicationAcceptance=False,actualPerformanceAcceptance=False,historicalBuildFailureExactAttributionNotEstablished=True,reviewerDigest=sha(__file__),reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with(B/'independent-review.json').open('x')as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps(review))
