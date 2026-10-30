from pathlib import Path
import json,hashlib,re,datetime,subprocess,ast
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
D=R/'.tools/owner-status-investigation-20261030/prepared-guarded-diagnostic'
C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
expected='fad8a8f0458b5e07b0b73520eab76f5fd8168644dd2569849d57cce524589059'
assert sha(D/'frozen.json')==expected
F=read(D/'frozen.json')
for p,h in F['bindings'].items():assert sha(p)==h,p
approval=read(D/'APPROVAL.json')
assert approval['frozenManifestSha256']==expected
assert approval['humanAnswer']=='Approve one traced diagnostic only'
assert approval['maximumAdditionalDiagnosticRuns']==1 and approval['applicationRunsAuthorized']==0
m=read(D/'supervisor.json');ex=read(D/'supervisor-exit.json')
requests=[read(p) for p in (C/'scheduler/requests').glob('*.json')]
matched=[r for r in requests if r['owner']['pid']==m['pid'] and r['project']==str(R) and datetime.datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'))>=datetime.datetime.fromisoformat(m['startedAtUtc'])]
assert len(matched)==1
r=matched[0]
assert r['state']=='finished' and r.get('leaseReleaseCompleted') is True
assert r['exclusive'] is True and r['enforcement']=='native-exclusive'
assert r['limits']['diskBytes']==4000000000
stream=(D/'supervisor.stdout').read_text()+(D/'supervisor.stderr').read_text()
ids=re.findall(r'Storage guard record: '+re.escape(str(C))+r'/runs/([0-9a-f-]{36})/run[.]json',stream)
assert len(ids)==1,ids
gp=C/'runs'/ids[0]/'run.json';g=read(gp)
assert r['startedAt']<=g['startedAt']<=g['finishedAt']<=r['finishedAt']
assert g['root']==str(R) and g['label']==r['label']=='patamaps' and g['filesDeleted']==0
assert ex['exitCode']==g['exitCode']
receipt=read(D/'receipt.json') if (D/'receipt.json').exists() else None
v=dict(status='independently-reviewed-one-shot-ownership-diagnostic',sourceRevision='03ccfec538f0bacf214b69a0664af40ecbd3bdb4',frozenManifestSha256=expected,allFrozenBindingsRehashed=True,approvedAdditionalDiagnosticRuns=1,applicationRunsAuthorized=0,reservationId=r['id'],reservationFinished=True,leaseReleased=True,nativeExclusive=True,guardId=ids[0],guardRecordSha256=sha(gp),guardCompleted=g['completed'],supervisorExitCode=ex['exitCode'],guardExitCode=g['exitCode'],servicesStarted=0,apiRequestsExecuted=0,browserProjectsExecuted=0,filesDeleted=0,policyChanged=False,applicationAcceptance=False,fullGoalComplete=False)
if receipt:
 assert receipt['servicesStarted']==receipt['apiRequests']==0 and receipt['applicationAcceptance'] is False
 assert receipt['elapsedSeconds']<60
 raw=(D/'probe.stderr.private').read_text()
 stages=[]
 for line in raw.splitlines():
  try:
   item=json.loads(line)
   if set(item)=={'stage','atMs'}:stages.append(item)
  except json.JSONDecodeError:pass
 assert stages==receipt['stages']
 assert all(isinstance(k,str) and isinstance(b,bool) for k,b in receipt['environmentPresenceOnly'].items())
 v.update(driverExecuted=True,probeTimedOut=receipt['timeout'],probeExitCode=receipt['exitCode'],probeElapsedSeconds=receipt['elapsedSeconds'],stages=stages,lastReachedStage=stages[-1]['stage'] if stages else None,rawReceiptSha256=sha(D/'receipt.json'),rawProbeStdoutSha256=sha(D/'probe.stdout.private'),rawProbeStderrSha256=sha(D/'probe.stderr.private'),environmentPresenceOnly=receipt['environmentPresenceOnly'])
 if receipt['timeout']:assert ex['exitCode']==124
 else:assert receipt['exitCode']==ex['exitCode']
else:
 assert ex['exitCode']!=0
 v.update(driverExecuted=False,guardStopReason=g.get('stopReason'),probeOutcome='no-receipt-preserve-admission-or-controller-failure')
prior=R/'.tools/owner-auth-endpoint-20261029/services-repair2-20261030'
pf=read(prior/'frozen.json')
for p,h in pf['inputs'].items():assert 'sha256:'+sha(p)==h,p
for row in read(prior/'prior-admission-preimages.json'):assert 'sha256:'+sha(row['path'])==row['digest']
v.update(previousAuthenticationInputsMatched=True,previousFailurePreimagesMatched=True)
old=read(prior/'protected-service-before.json')
db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect','advocates-local-advocates-db-1'],text=True,timeout=20))[0]
current=dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])
assert current==old
v['protectedDatabaseStartIdentityMatchesPreviousAuthReview']=True
try:
 subprocess.run(['/bin/kill','-0',str(m['pid'])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
 v['supervisorPidStillExists']=True
except subprocess.CalledProcessError:v['supervisorPidStillExists']=False
v['reviewerSha256']=sha(__file__)
with (D/'independent-review.json').open('x') as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))
