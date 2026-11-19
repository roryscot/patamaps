from pathlib import Path
import ast,json,hashlib
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
D=R/'.tools/owner-auth-endpoint-20261029/services-one-extension-proposal-20261030'
F=json.loads((D/'frozen.json').read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
for p,h in F['inputs'].items():assert sha(p)==h,p
fn=next(n for n in ast.parse((R/'scripts/bench_axum_retained.py').read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='validate_ownership')
scope={'ROOT':R};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<original-saved-validator>','exec'),scope)
rows=[]
for p in sorted(D.glob('ownership-probe-*.stdout.private')):
 proof=json.loads(p.read_text());row={'file':p.name,'rawStdoutDigest':sha(p)}
 assert proof['id']=='6777725c-f925-4cd5-b866-59384c40af8b'
 try:scope['validate_ownership'](proof,'functional',R);row['accepted']=True
 except AssertionError as e:row.update(accepted=False,refusal=str(e))
 for key in ['heartbeatStale','ownerAlive','ownerIdentityVerified','ownerIsAncestor','cancellationRequested','otherActiveReservations']:row[key]=proof[key]
 stages=[]
 for line in p.with_name(p.name.replace('.stdout.private','.stderr.private')).read_text().splitlines():
  try:
   v=json.loads(line)
   if set(v)=={'stage','atMs'}:stages.append(v)
  except json.JSONDecodeError:pass
 assert len(stages)==16 and stages[-1]['stage']=='proof-output-after'
 row['all16StagesCompleted']=True
 row['stageWindowMs']=stages[-1]['atMs']-stages[0]['atMs']
 rows.append(row)
assert len(rows)==3 and [x['accepted'] for x in rows]==[False,False,True]
assert [x['heartbeatStale'] for x in rows]==[True,True,False]
a=json.loads((D/'receipt.json').read_text())
assert a['failureType']=='OSError'and a['failure']=='[Errno 48] Address already in use'and a['servicesStarted']==0 and a['cases']==[]
assert not any((D/n).exists()for n in ['container.json','database','run','service-config.private.json','database-env.private'])
v=dict(status='saved-ownership-and-port-refusal-reviewed',probes=rows,existingFreshHeartbeatWaitExercised=True,lastSavedOwnershipProofAccepted=True,ownershipTimeoutReproduced=False,applicationBlockedBeforeServices=True,addressErrorNumber=48,conflictingPortObserved=18766,applicationServicesStarted=0,databaseCreated=False,credentialsGenerated=False,migrationsRun=False,authenticationCasesRun=0,browserCasesRun=0,additionalLiveOwnershipProbesRun=0,reviewerDigest=sha(__file__))
with(D/'ownership-and-port-review.json').open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))
