from pathlib import Path
import json,hashlib,subprocess,datetime,re,sys,stat
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/native-guard-normal-seal-full-controls-20261105';W=B/'worker'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return 'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
a=read(B/'shared-crash-review.json');worker=read(W/'pilot-result.json')
assert a['status']=='passed-twelve-staged-native-cases-single-output' and worker['failure'] is None and len(worker['rows'])==5
assert read(B/'supervisor-exit.json')['exitCode']==0
assert all(a[k] for k in ['allObservedRegisteredGroupsStopped','allFrozenInputsStillMatched','allProtectedSelectedStateStillMatched','protectedDatabaseStartIdentityUnchanged','trustedObserverSurvivedOwnerDeath','observerGroupStopped'])
assert a['phaseElapsedSeconds']<=600 and a['parentDeathToObserverStopMs']<=60000
assert a['controlledParentExitCode']==-9 and a['observerExitCodeNotDirectlyObserved'] is True and a['runtimeCopies']==1 and a['bridgeControlsPassed']==28
expected=['normal-engine','cancel-unchanged','controller-crash','guardian-crash','owner-parent-death']
assert [x['name'] for x in worker['rows']]==expected
sys.path.insert(0,str(R/'.tools/native-guard-candidate-normal-seal-20261105/engine'))
import native_inspection_guard as kernel
injection=read(B/'active-parent-death-injection.json');observer=injection['observer'];owner=injection['owner']
assert observer['parentPid']==owner['pid'] and owner['pgid']==owner['pid'] and observer['pgid']==observer['pid']
assert kernel.process_identity(owner['pid']) is None and not kernel.group_live(owner['pid'])
assert kernel.process_identity(observer['pid']) is None and not kernel.group_live(observer['pid'])
rows=[];allIds=set()
for name,row in zip(expected,worker['rows']):
 assert row['name']==name and row['reservationReleased'] and row['channelClosed'] and row['injectionFailure'] is None
 lease=W/(name+'-lease');requests=list((lease/'scheduler/requests').glob('*.json'));records=list((lease/'runs').glob('*/run.json'))
 assert len(requests)==len(records)==1
 request=read(requests[0]);guard=read(records[0]);stop=guard['registeredNativeStop'];control=read(W/name/'supervisor-status.json')
 assert request['id']==row['reservation'] and request['state']=='finished' and request['leaseReleaseCompleted']
 assert request['exclusive'] and request['enforcement']=='native-exclusive' and request['limits']['diskBytes']==536870912
 assert request['project']==str(W/'test-project') and not request.get('manualStoppedRecovery') and not request.get('legacyRecoveryProof')
 assert not (lease/'active-run').exists()
 assert guard['exitCode']==row['code'] and guard['completed']==(name=='normal-engine')
 assert stop['safeToRelease'] and stop['observerFailure'] is None and stop['dataStreamsClosed']
 assert stop['ownership']['ownershipKnown'] and stop['ownership']['allRegisteredStopped'] and stop['ownership']['channelClosed']
 assert stop['ownership']['protocolFailure'] is None and stop['ownership']['probeError'] is None
 assert guard['existingContainerUncertainty'] is False and guard['containersAtStart']['known'] and guard['containersAtStart']['ids']==guard['containersAtEnd']['ids']
 assert guard['freeBytesAtStart']-guard['minimumFreeBytesObserved']<=536870912
 assert guard['nativeCommandOwner']['pid']==owner['pid']
 ids=[control['controllerIdentity']]
 for call in control['calls']:
  assert call['registrationKnown'] is True
  ids.extend(call[k] for k in ['guardianIdentity','nativeIdentity'] if call.get(k))
 for value in ids:
  allIds.add(value['pid']);assert kernel.process_identity(value['pid']) is None and not kernel.group_live(value['pgid'])
 if name=='normal-engine':
  assert row['code']==0 and stop['normalCompletionSealed']is True
  assert all(call['finished']and call['controlComplete']and call['nextSequence']==6 and call['innerCount']==3 for call in control['calls'])
 else:
  assert stop['normalCompletionSealed']is False
 if name=='normal-engine':pass
 elif name=='owner-parent-death':
  assert row['code']==75 and guard['stopReason']=='Storage guard: native command owner parent stopped; stopping registered inspection'
 else:
  fault=read(W/name/'fault-injection.json');assert fault['nativeLiveIdentityConfirmed'] and row['cancelToReleaseMs']<=60000
  assert row['code']==75 if name=='cancel-unchanged' else row['code']!=0
  if name=='controller-crash':assert stop['controllerSignal']=='SIGKILL'
 cleanup=read(W/name/'independent-cleanup.json');assert cleanup['confirmed']
 rows.append(dict(name=name,operationExitCode=row['code'],automaticReservationReleaseAccepted=True,reservationId=request['id'],sourceParentOwnerBound=True,registeredGroupsStopped=len(ids),privateChannelClosed=True,allDataStreamsClosed=True,sourceRuntimeBindingUnchanged=True,requestDigest=sha(requests[0]),guardRecordDigest=sha(records[0]),actionToReleaseMs=row['cancelToReleaseMs']))
negativeReviews=[];allids=set();negativeExpected=['lost-terminal','missing','malformed','truncated','lost','unsealed-survivor','binding-mutation']
assert[x['mode']for x in worker['negativeRows']]==negativeExpected
for mode,row in zip(negativeExpected,worker['negativeRows']):
 root=W/mode;lease=W/(mode+'-lease')
 requests=list((lease/'scheduler/requests').glob('*.json'));assert len(requests)==1
 request=read(requests[0]);owner=read(lease/'active-run/owner.json');guard=read(lease/'active-run/retained-run.json');status=read(root/'supervisor-status.json');raw=read(root/'raw-evidence.json')
 assert request['id']==row['reservation']==owner['requestId']
 assert request['state']=='needs-review'and request['leaseReleaseCompleted']is False
 assert request['enforcement']=='native-exclusive'and request['exclusive']and request['limits']['diskBytes']==536870912
 assert not request.get('manualStoppedRecovery')and not request.get('legacyRecoveryProof')
 assert guard['exitCode']==75 and guard['completed']is False and guard['registeredNativeStop']['safeToRelease']is False
 assert row['accepted']and not row['manualRecovery']and not row['releaseCompleted']and row['state']=='needs-review'
 assert raw['rawEnd']and raw['rawBytes']<=65536 and raw['actualExit']==row['actualControllerExit']
 assert status['channelClosed']and status['controllerOutcome']==row['actualControllerExit']
 frames=raw['rawFrames'];ids={v['pid']:v for v in raw['identities']}
 assert status['controllerIdentity']['pid']in ids
 groups=set(ids)
 for frame in frames:
  assert frame['controllerPid']==status['controllerIdentity']['pid']
  for k in ['guardianIdentity','nativeIdentity']:
   if frame.get(k):assert frame[k]['pid']in ids
  record=frame.get('record',{})
  if record.get('pid'):groups.add(record['pid'])
 if mode!='binding-mutation':
  assert raw['actualExit']==dict(code=0,signal=None)and len(frames)==6
  assert[frame['sequence']for frame in frames]==list(range(6))
  assert frames[-1]['event']=='inspection-finished'and frames[-1]['controlComplete']and frames[-1]['cleanup']['confirmed']
 else:
  assert raw['actualExit']['code']==75 and raw['actualExit']['signal']is None and len(frames)==3
  assert raw['mutation']['observedWhileGuardianLive']and raw['mutation']['changedDigest']!=raw['mutation']['originalDigest']
  assert status['failure']=='inspection-closure-changed: source'
  assert guard['registeredNativeStop']['failure']=='inspection-closure-changed: source'
 if mode=='lost-terminal':
  assert status['failure']is None and len(status['calls'])==1
  call=status['calls'][0];assert call['registrationKnown']and not call['finished']and not call['controlComplete']and call['nextSequence']==5
  assert guard['registeredNativeStop']['normalCompletionSealed']is False
 elif mode=='missing':assert status['failure']=='missing-launch-records'and status['calls']==[]
 elif mode=='malformed':assert status['failure']=='outer-frame-schema'
 elif mode=='truncated':assert status['failure']=='partial-control-record'
 elif mode in ['lost','unsealed-survivor']:
  assert status['failure']is None and len(status['calls'])==1 and not status['calls'][0]['registrationKnown']
 if mode=='unsealed-survivor':
  sentinel=raw['realSurvivor'];assert sentinel['kind']=='artificial-unconfined-readonly-sleep-sentinel'and sentinel['startedAfterActualGuardianLaunch']
  assert sentinel['identity']['pid']in ids and sentinel['identity']['parentPid']==request['owner']['pid']
  assert row['heldWhileSentinelLive']is True
 stops=read(root/'independent-stop.json');assert len(stops)==len(ids)and all(x['stopped']and x['groupStopped']for x in stops)
 for pid in groups:
  assert kernel.process_identity(pid)is None and not kernel.group_live(pid)
 allids.update(groups)
 negativeReviews.append(dict(mode=mode,reservationId=request['id'],actualControllerExitCode=raw['actualExit']['code'],guardFailedExitCode=75,reservationHeldAsRequired=True,releaseCompleted=False,protocolFailure=status['failure'],realSurvivorHeld=mode=='unsealed-survivor',liveGuardianBindingMutationRefused=mode=='binding-mutation',independentStoppedGroups=len(groups),manualRecoveryUsed=False,requestDigest=sha(requests[0]),retainedGuardDigest=sha(lease/'active-run/retained-run.json'),rawControlDigest=sha(root/'raw-evidence.json')))

reg=W/'stage/registration';manifest=read(reg/'registration.json')
assert manifest['kind']=='patamaps-staged-native-registration-v1' and manifest['automaticReservationReleaseQualified'] is False
counts={}
for base,entries in manifest['inventory'].items():
 counts[base]={}
 for entry in entries:
  p=reg/base/entry['path'];s=p.lstat()
  assert s.st_uid==entry['uid'] and s.st_dev==entry['dev'] and s.st_ino==entry['ino'] and s.st_nlink==entry['nlink']
  assert stat.S_IMODE(s.st_mode)==entry['mode']
  kind=entry['kind'];counts[base][kind]=counts[base].get(kind,0)+1
  if kind=='file':assert p.is_file() and sha(p)[7:]==entry['sha256'] and s.st_size==entry['size']
  elif kind=='symlink':assert p.is_symlink() and str(p.readlink())==entry['target'] and p.resolve().is_relative_to(reg/base)
  else:assert kind=='directory' and p.is_dir()
assert len(manifest['inventory']['runtime'])==1807 and len(manifest['dependencies'])==10
assert counts['runtime']=={'directory':155,'file':1643,'symlink':9}
assert all(sha(p)[7:]==h for p,h in manifest['systemBindings'].items())
fixture=read(W/'inputs.json');assert all(sha(p)==('sha256:'+h if not h.startswith('sha256:') else h) for p,h in fixture['expectedState'].items())
text=(W/'driver.stdout').read_text();decoder=json.JSONDecoder();engines=[]
for index,ch in enumerate(text):
 if ch=='{':
  try:value,_=decoder.raw_decode(text[index:])
  except ValueError:continue
  if isinstance(value,dict) and value.get('documentType')=='executor-description':engines.append(value)
assert len(engines)==7 and all(value==fixture['engine']for value in engines)
caseOutputCounts={}
for case in negativeExpected+expected:
 begin='QUALIFIED_CASE_BEGIN '+case+'\n';end='QUALIFIED_CASE_END '+case+'\n'
 assert text.count(begin)==text.count(end)==1
 section=text.split(begin,1)[1].split(end,1)[0];found=[]
 for index,ch in enumerate(section):
  if ch=='{':
   try:value,_=decoder.raw_decode(section[index:])
   except ValueError:continue
   if isinstance(value,dict)and value.get('documentType')=='executor-description':found.append(value)
 expectedCount=1 if case in negativeExpected[:-1]+['normal-engine']else 0
 assert len(found)==expectedCount and all(value==fixture['engine']for value in found)
 caseOutputCounts[case]=len(found)
C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds');stream=(B/'supervisor.stdout').read_text()+(B/'supervisor.stderr').read_text()
ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
outerGuard=read(C/'runs'/ids[0]/'run.json');assert outerGuard['completed'] and outerGuard['exitCode']==0 and outerGuard['root']==str(R)
assert outerGuard['freeBytesAtStart']-outerGuard['minimumFreeBytesObserved']<=1000000000
meta=read(B/'supervisor.json')
requests=[read(p) for p in (C/'scheduler/requests').glob('*.json')]
matched=[x for x in requests if x['owner']['pid']==meta['pid'] and x['createdAt']>=meta['startedAtUtc']]
assert len(matched)==1 and matched[0]['state']=='finished' and matched[0]['leaseReleaseCompleted'] and matched[0]['limits']['diskBytes']==1000000000
assert sha('/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs')==F['installedGuardDigest']=='sha256:3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0'
protected=read(B/'protected-service-before.json');db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',protected['id']],text=True))[0]
assert dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==protected
review=dict(status='independently-accepted-twelve-staged-native-cases',cases=rows,negativeCases=negativeReviews,bridgeControlsPassed=28,allFrozenInputsRehashed=len(F['inputs']),negativeStoppedGroups=len(allids),engineDocuments=caseOutputCounts,sevenNegativeReservationsHeld=True,normalSuccessRequiresFinalSeal=True,independentlyStoppedRegisteredIdentities=len(allIds),controlledParentKilledBySigkill=True,independentObserverSurvivedParentDeath=True,observerGroupIndependentlyStopped=True,observerExitCodeNotDirectlyObserved=True,parentDeathToObserverStopMs=a['parentDeathToObserverStopMs'],phaseElapsedSeconds=a['phaseElapsedSeconds'],oneRuntimeReused=True,qualifiedRuntimeCounts=counts['runtime'],privateMachOObjects=10,allRuntimeFileModesAndKernelFileIdentitiesReverified=True,allSystemBindingsRehashed=True,engineOutputIndependentlyMatched=True,allProtectedSelectedStateRehashed=True,protectedDatabaseStartIdentityUnchanged=True,canonicalOuterRequest=matched[0]['id'],canonicalOuterReservationReleased=True,outerJobGrowthBytes=1000000000,innerJobGrowthBytes=536870912,installedGuardUnchanged=True,installedGuardDigest=F['installedGuardDigest'],fullTenCaseSuiteAccepted=False,parallelActivated=False,trustActivated=False,filesDeleted=0,sourceBindings=F['inputs'],frozenManifestSha256=sha(B/'frozen.json'),reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with (B/'independent-review.json').open('x') as out:json.dump(review,out,indent=2);out.write('\n')
print(json.dumps({k:v for k,v in review.items() if k not in ['cases','negativeCases','sourceBindings']}))
