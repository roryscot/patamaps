from pathlib import Path
import json,hashlib,subprocess,plistlib,re,sys,stat,time,datetime
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/idle-workspace-maintenance-20261105';C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds');D='/Applications/Docker.app/Contents/Resources/bin/docker'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
r=read(B/'receipt.json');assert r['status']=='passed-delegated-nondeleting-maintenance'and len(r['images'])==3 and r['databaseReady']and r['dockerReady']
assert all(r[k]==0 for k in['filesDeleted','imagesDeleted','containersDeleted','volumesDeleted'])
assert r['quiescentDatabaseObservedImmediatelyBeforeStop']and 0<r['stopRequestToVerifiedReadinessSeconds']<600
assert read(B/'supervisor-exit.json')['exitCode']==1
stderr=(B/'supervisor.stderr').read_text();assert 'TimeoutError: timed out'in stderr and 'query.py'in stderr
for row in r['commands']:
 assert row['exitCode']==0
 for stream in ['stdout','stderr']:assert sha(B/(row['prefix']+'.'+stream))==row[stream+'Digest']
attachments=plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil','info','-plist'],timeout=20)).get('images',[])
rows=[];files=0;entries=0
for original,actual in zip(F['images'],r['images']):
 assert original['id']==actual['id']
 p=Path(actual['image']);s=p.lstat()
 assert dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mode=stat.S_IMODE(s.st_mode),uid=s.st_uid)==original['identity']==actual['identity']
 assert stat.S_ISREG(s.st_mode)and s.st_nlink==1 and sha(p)==actual['closedImageDigest']
 assert not any(x.get('image-path')==str(p)for x in attachments)
 before=read(B/(actual['id']+'-before.json'));restored=read(B/(actual['id']+'-readonly.json'))
 assert before==restored and len(before)==actual['entries']and sum(x['kind']=='file'for x in before.values())==actual['files']
 requestFile=C/'scheduler/requests'/(actual['id']+'.json');assert sha(requestFile)==original['originalRequestDigest']and read(requestFile)['state']=='finished'
 assert actual['allGuestBytesModesOwnersInodesMtimesMatched']and actual['readonlyCycleImageBytesIdentical']and actual['normalFinalClosure']and actual['backingImagePreserved']
 files+=actual['files'];entries+=actual['entries'];rows.append(dict(id=actual['id'],imageDigest=sha(p),imageIdentityPreserved=True,guestFiles=actual['files'],guestEntries=actual['entries'],readonlyRecoveryMatched=True,closed=True))
db=json.loads(subprocess.check_output([D,'inspect',F['database']['id']],text=True,timeout=15))[0]
config=dict(id=db['Id'],name=db['Name'],restartPolicy=db['HostConfig']['RestartPolicy'],ports=db['NetworkSettings']['Ports'],mounts=[{k:m.get(k)for k in['Type','Name','Source','Destination','RW']}for m in db['Mounts']])
assert config==F['database']['configuration']and db['State']['Running']
assert subprocess.run([D,'exec',db['Id'],'pg_isready'],capture_output=True,timeout=15).returncode==0
sql='SELECT system_identifier::text FROM pg_control_system();';shell='export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$1"'
assert subprocess.check_output([D,'exec',db['Id'],'sh','-c',shell,'private-independent-identity',sql],text=True,timeout=20).strip()==F['database']['clusterId']
assert subprocess.check_output([D,'ps','-q','--no-trunc'],text=True,timeout=15).split()==[db['Id']]
beforeUsage=F['ownedVolumeUsage'];PY=R/'.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3';began=time.monotonic()
doc=json.loads(subprocess.check_output([str(PY),'-I','-S','-B',str(R/'.tools/guarded-job-volume-accounting-20261104/query.py'),str(R)],text=True,timeout=5.5));querySeconds=time.monotonic()-began
volumes=sorted([dict(name=x['Name'],bytes=x['UsageData']['Size'])for x in doc['Volumes']if x.get('Labels',{}).get('buildctl.project')==str(R)],key=lambda x:x['name'])
assert dict(bytes=sum(x['bytes']for x in volumes),count=len(volumes),volumes=volumes)==beforeUsage
stream=(B/'supervisor.stdout').read_text()+stderr;ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
guard=read(C/'runs'/ids[0]/'run.json');request=read(C/'scheduler/requests'/f"{r['reservationId']}.json")
assert guard['completed']and guard['exitCode']==0 and guard['filesDeleted']==0 and guard['freeBytesAtStart']-guard['minimumFreeBytesObserved']<=1000000000
assert request['state']=='finished'and request['leaseReleaseCompleted']and request['limits']['diskBytes']==1000000000 and request['enforcement']=='native-exclusive'
sys.path.insert(0,str(R/'scripts'));import native_inspection_guard as kernel
for pid in[request['owner']['pid'],request['processGroup']]:assert kernel.process_identity(pid)is None and not kernel.group_live(pid)
out=dict(status='independently-verified-maintenance-effects-with-preserved-postcheck-timeout',sourceRevision=F['sourceRevision'],images=rows,guestFilesCompared=files,guestEntriesCompared=entries,allBackingImageBytesRehashed=True,originalImageIdentitiesPreserved=True,allThreeViewsClosed=True,sameDatabaseContainerAndConfiguration=True,sameDatabaseClusterAndNamedDataVolume=True,databaseReady=True,dockerReady=True,onlyOriginalDatabaseRunning=True,stopRequestToVerifiedReadinessSeconds=r['stopRequestToVerifiedReadinessSeconds'],workerExitCode=0,canonicalGuardExitCode=0,originalControllerExitCode=1,originalControllerFailure='Post-restart Docker statistics query timed out; failure/exit retained.',unchangedReadOnlyStatisticsCheckNowPassed=True,lateStatisticsQuerySeconds=querySeconds,allOwnedVolumeNamesAndSizesUnchanged=True,serviceOperationsRepeated=False,canonicalReservation=r['reservationId'],canonicalReservationReleased=True,maximumRunGrowthBytes=1000000000,machineGrowthCeilingBytes=4000000000,reserveBytes=500000000,retentionCeilingBytes=100000000000,allFrozenInputsRehashed=len(F['inputs']),allObservedOwnedGroupsStopped=True,filesDeleted=0,imagesDeleted=0,containersDeleted=0,volumesDeleted=0,benchmarkRun=False,installedGuardChanged=False,parallelActivated=False,frozenManifestDigest=sha(B/'frozen.json'),reviewerDigest=sha(__file__),reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with(B/'independent-review.json').open('x')as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in out.items()if k!='images'}))
