from pathlib import Path
import json,hashlib,ast
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
D=R/'.tools/owner-auth-endpoint-20261029/services-localhost-profile-proposal-20261030'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=read(D/'frozen.json')
for p,h in F['inputs'].items():assert sha(p)==h,p
a=read(D/'receipt.json');review=read(R/'docs/acceptance/project-adoption/original-owner-auth-endpoint-20261029/services-localhost-profile-proposal-20261030/review.json')
assert a['profileSyntaxExitCode']==0 and a['profileSyntaxStdoutBytes']==a['profileSyntaxStderrBytes']==0
assert a['failure']=='OWNED_POSTGRES_NOT_READY' and a['servicesStarted']==1 and a['cases']==[]
assert review['ownedContainerInspectedStopped']and review['testPortsHaveNoListeners']and review['leaseReleased']
post=read(D/'database-readiness-postmortem.json')
assert post['state']['ExitCode']==1 and post['state']['OOMKilled']is False and post['state']['Error']==''
assert not any((D/'run'/n).exists()for n in ['controls-migrate.json','migrate.stdout','seed.stdout','server.stdout'])
fn=next(n for n in ast.parse((R/'scripts/bench_axum_retained.py').read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='validate_ownership')
scope={'ROOT':R};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<saved-original-validator>','exec'),scope)
proofs=[]
for p in sorted(D.glob('ownership-probe-*.stdout.private')):
 row={'file':p.name,'rawDigest':sha(p)}
 try:scope['validate_ownership'](read(p),'functional',R);row['accepted']=True
 except AssertionError as e:row.update(accepted=False,refusal=str(e))
 proofs.append(row)
assert proofs and proofs[-1]['accepted']
v=dict(status='saved-corrected-profile-and-database-exit-verified',profileSyntaxCheckAccepted=True,profilePrecheckBeforeDatabaseSatisfied=True,savedOwnershipProofs=proofs,originalOwnershipValidatorPassedAtRun=True,databaseStartupExitedBeforeReadiness=True,databaseExitCode=1,databaseOOMKilled=False,dockerEngineErrorRecorded=False,databaseStartupRootCauseKnown=False,startupOutputAvailable=False,readinessPollOutputsAvailable=False,originalMigrationsExecuted=False,seedExecuted=False,apiStarted=False,httpAuthenticationCasesExecuted=0,browserCasesExecuted=0,ownedContainerStopped=True,ownedDataPreserved=True,allTestPortsClosed=True,reservationReleased=True,additionalLiveOwnershipOrDatabaseTestsExecuted=0,reviewerDigest=sha(__file__))
with(D/'readiness-failure-review.json').open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))
