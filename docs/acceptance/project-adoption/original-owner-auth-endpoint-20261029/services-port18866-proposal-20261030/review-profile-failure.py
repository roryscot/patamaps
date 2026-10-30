from pathlib import Path
import json,hashlib,ast,os
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
D=R/'.tools/owner-auth-endpoint-20261029/services-port18866-proposal-20261030'
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=json.loads((D/'frozen.json').read_text())
for p,h in F['inputs'].items():assert sha(p)==h,p
source=ast.parse((R/'scripts/bench_axum_retained.py').read_text())
fn=next(n for n in source.body if isinstance(n,ast.FunctionDef)and n.name=='validate_ownership')
scope={'ROOT':R};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<saved-original-validator>','exec'),scope)
rows=[]
for p in sorted(D.glob('ownership-probe-*.stdout.private')):
 proof=json.loads(p.read_text());row={'file':p.name,'rawStdoutDigest':sha(p)}
 assert proof['id']=='8ed098c4-e093-4050-9086-1473983cc97d'
 try:scope['validate_ownership'](proof,'functional',R);row['accepted']=True
 except AssertionError as e:row.update(accepted=False,refusal=str(e))
 row.update(heartbeatStale=proof['heartbeatStale'],ownerIdentityVerified=proof['ownerIdentityVerified'],ownerIsAncestor=proof['ownerIsAncestor'],cancellationRequested=proof['cancellationRequested'],otherActiveReservations=proof['otherActiveReservations'])
 rows.append(row)
assert rows and rows[-1]['accepted'] is True
a=json.loads((D/'receipt.json').read_text())
assert a['failure']=='ORIGINAL_OWNER_MIGRATE_FAILED'and a['servicesStarted']==1 and a['migrateExitCode']==65 and a['cases']==[]
raw=(D/'run/migrate.stderr').read_text()
assert raw.startswith('sandbox-exec: host must be * or localhost in network address\n')
assert not any((D/'run'/n).exists()for n in ['controls-migrate.json','seed-result.json','server.stdout','seed.stdout'])
allocated=0;count=0
for folder,dirs,files in os.walk(D/'database'):
 for name in files:
  p=Path(folder)/name
  if not p.is_symlink():allocated+=p.stat().st_blocks*512;count+=1
assert allocated<=536870912 and count<=16384
v=dict(status='saved-ownership-and-profile-parser-failure-verified',savedProofs=rows,originalOwnershipValidatorPassedAtRun=True,additionalOwnershipProbesExecuted=0,isolationProfileRejectedBeforePython=True,originalMigrationsExecuted=False,seedExecuted=False,apiStarted=False,authenticationCasesExecuted=0,browserCasesExecuted=0,rawMigrationStderrDigest=sha(D/'run/migrate.stderr'),ownedDatabaseDataAllocatedBytesAtReview=allocated,ownedDatabaseFilesAtReview=count,dataPeakClaimed=False,ownedDataPreserved=True,newPreparedProfileNotExecuted=True,reviewerDigest=sha(__file__))
with(D/'profile-failure-review.json').open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))
