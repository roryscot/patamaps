from pathlib import Path
import json,hashlib,subprocess,re,sys,datetime
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/native-guard-fair-queue-controls-20261104'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
result=read(B/'result.json');assert result['status']=='passed-native-fairness-and-fallback-controls'and result['failure']is None and len(result['rows'])==4
assert all(x['passed']for x in result['rows'])and result['frozenInputsMatched']and result['elapsedMs']<=300000
assert read(B/'supervisor-exit.json')['exitCode']==0
sys.path.insert(0,str(R/'.tools/native-guard-candidate-parent-watch-20261104/engine'));import native_inspection_guard as kernel
allGroups=set();rows=[]
for group,count in [('simultaneous',2),('fair-followup',3)]:
 directory=B/group;requests=[read(p)for p in(directory/'lease/scheduler/requests').glob('*.json')]
 assert len(requests)==count and all(r['state']=='finished'and r['leaseReleaseCompleted']for r in requests)
 assert not(directory/'lease/active-run').exists()
 for r in requests:
  assert r['enforcement']=='native-exclusive'and r['exclusive']and r['limits']['diskBytes']==67108864
  assert not r.get('manualStoppedRecovery')
  p=read(directory/(r['label']+'.payload.json'))
  assert p['pid']==r['processGroup']and p['parentPid']==r['owner']['pid']
  allGroups.update([p['pid'],p['parentPid']])
  assert Date if False else True
 ordered=sorted(requests,key=lambda r:r['startedAt'])
 assert all(a['finishedAt']<=b['startedAt']for a,b in zip(ordered,ordered[1:]))
 if group=='simultaneous':
  proof=read(directory/'simultaneous-observation.json');during=proof['requests']
  assert len(during)==2 and sum(r['state']=='running'for r in during)==1 and sum(r['state']=='queued'for r in during)==1
  assert proof['owner']['requestId']==next(r['id']for r in during if r['state']=='running')
  rows.append(dict(case=group,accepted=True,actualProcesses=2,simultaneousRequests=2,maximumNativeWriters=1,queuedPayloadStartedOnlyAfterFirstRelease=True,requestIds=[r['id']for r in ordered]))
 else:
  assert [r['label']for r in ordered]==['a1','b1','a2']
  mapping={r['label']:r for r in requests}
  assert mapping['a1']['owner']==mapping['a2']['owner']and mapping['a1']['project']==mapping['a2']['project']!=mapping['b1']['project']
  assert mapping['a2']['sequence']>mapping['b1']['sequence']and mapping['a2']['id']!=mapping['a1']['id']
  proof=read(directory/'fairness-observation.json');during=proof['requests'];m={r['label']:r for r in during}
  assert m['a1']['state']=='finished'and m['b1']['state']=='running'and m['a2']['state']=='queued'
  assert proof['owner']['requestId']==m['b1']['id']
  rows.append(dict(case=group,accepted=True,grantOrder=['a1','b1','a2'],sameOwnerFollowupCreatedFreshRequest=True,otherProjectWaiterAdmittedBeforeFollowup=True,requestIds=[r['id']for r in ordered]))
assert (B/'output-alias').is_symlink()and(B/'output-alias').resolve()==B/'output-contract'
node='/Users/admin/.nvm/versions/node/v22.23.3/bin/node'
js="""import{canonical,outputConflict,admission}from'file:///Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-candidate-parent-watch-20261104/engine/buildctl.mjs';const B='/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-fair-queue-controls-20261104';const make=(out,instances=[])=>({outputs:[canonical(out)],instances,exclusive:true,phase:'functional',limits:{cpu:1,memoryBytes:1000000,diskBytes:1000000}});const cap={cpu:4,memoryBytes:4000000,diskBytes:4000000};console.log(JSON.stringify({alias:admission(make(B+'/output-alias/nested'),[make(B+'/output-contract')],cap,{}),instance:outputConflict(make(B+'/o1',['owned-instance']),make(B+'/o2',['owned-instance'])),benchmark:admission({...make(B+'/o3'),phase:'benchmark'},[make(B+'/o4')],cap,{})}));"""
actual=json.loads(subprocess.check_output([node,'--input-type=module','-e',js],text=True,timeout=15))
assert actual==dict(alias='shared output or application instance',instance=True,benchmark='exclusive work')
rows.append(dict(case='actual-canonical-output-alias-instance-benchmark-contract',accepted=True,independentlyRepeatedDecisions=3,actualParallelConflictWorkloadClaimed=False))
directory=B/'ordinary-cancel';requests=[read(p)for p in(directory/'lease/scheduler/requests').glob('*.json')];assert len(requests)==1
request=requests[0];owner=read(directory/'lease/active-run/owner.json');guard=read(directory/'lease/active-run/retained-run.json')
assert request['state']=='needs-review'and request['leaseReleaseCompleted']is False and request['id']==owner['requestId']
assert guard['completed']is False and guard['exitCode']==75 and guard['existingContainerUncertainty']is True and 'registeredNativeStop'not in guard
assert guard['containersAtStart']['ids']==guard['containersAtEnd']['ids']==[F['protectedDatabaseId']]and guard['newSurvivingContainers']==[]
payload=read(directory/'a1.payload.json');assert payload['pid']==request['processGroup']and payload['parentPid']==request['owner']['pid']
allGroups.update([payload['pid'],payload['parentPid']])
assert result['rows'][-1]['elapsedMs']<=60000
assert not request.get('manualStoppedRecovery')
rows.append(dict(case='ordinary-unregistered-cancellation',accepted=True,reservationId=request['id'],payloadGroupStopped=True,existingContainerUncertaintyPreserved=True,holdPreserved=True,manualRecoveryUsed=False,requestDigest=sha(directory/'lease/scheduler/requests'/f"{request['id']}.json")))
for pid in allGroups:assert kernel.process_identity(pid)is None and not kernel.group_live(pid)
assert all(x['stopped']and x['groupStopped']for x in read(B/'independent-stop.json'))
C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds');stream=(B/'supervisor.stdout').read_text()+(B/'supervisor.stderr').read_text()
ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
outer=read(C/'runs'/ids[0]/'run.json');assert outer['completed']and outer['exitCode']==0 and outer['freeBytesAtStart']-outer['minimumFreeBytesObserved']<=268435456
meta=read(B/'supervisor.json');matches=[read(p)for p in(C/'scheduler/requests').glob('*.json')if read(p)['owner']['pid']==meta['pid']and read(p)['createdAt']>=meta['startedAtUtc']]
assert len(matches)==1 and matches[0]['state']=='finished'and matches[0]['leaseReleaseCompleted']and matches[0]['limits']['diskBytes']==268435456
protected=read(R/'.tools/native-guard-shared-runtime-log-scope-20261104/protected-service-before.json')
db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',protected['id']],text=True,timeout=15))[0]
assert dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==protected
assert sha('/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs')=='sha256:3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0'
review=dict(status='independently-accepted-four-native-fairness-fallback-groups',cases=rows,allFrozenInputsRehashed=len(F['inputs']),independentlyStoppedGroups=len(allGroups),positiveRequestsAutomaticallyReleased=5,negativeOrdinaryHoldPreserved=True,canonicalOuterReservation=matches[0]['id'],canonicalOuterReleased=True,outerAllowanceBytes=268435456,innerAllowanceBytes=67108864,sourceBindings=F['inputs'],frozenManifestDigest=sha(B/'frozen.json'),unrelatedDatabaseIdentityUnchanged=True,filesDeleted=0,installedGuardChanged=False,parallelActivated=False,scope='Actual native-exclusive fairness and fallback; output/instance/benchmark decisions are independently repeated function contracts, not a claim of real concurrent parallel output execution.',reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with(B/'independent-review.json').open('x')as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in review.items()if k not in ['cases','sourceBindings']}))
