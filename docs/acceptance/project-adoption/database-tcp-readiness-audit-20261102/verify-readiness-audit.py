from pathlib import Path
import json,hashlib,subprocess
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
A=R/'.tools/owner-db-readiness-audit-20261102'
B=R/'.tools/owner-auth-endpoint-20261029'
O=B/'services-db-startup-trace-proposal-20261030'
N=B/'services-db-tcp-readiness-proposal-20261102'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=read(A/'review.json')
assert sha(A/'docker-entrypoint.private.sh')==a['entrypointSha256']
lines=(A/'docker-entrypoint.private.sh').read_text().splitlines()
for row in a['entrypointExcerpts']:assert lines[row['line']-1].strip()==row['code']
assert a['normalizedConfigurationEqual']and a['identityFilesEqual']and not a['observedFalsePositiveReproduced']
for row in a['containers']:
 x=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',row['containerId']],text=True,timeout=20))[0]
 assert x['Id']==row['containerId']and x['Image']==row['imageId']and not x['State']['Running']and x['State']['Pid']==0
 env=dict(v.split('=',1)for v in x['Config']['Env']if'='in v)
 assert not env.get('PGHOST')and not env.get('PGHOSTADDR')
assert sha(O/'frozen.json')=='e4a8936a0c62da5186208a3f87a621b3ae7fa842b58897c0740607b734bd4fad'
assert sha(N/'frozen.json')=='1fe5c34365a928d11c2c3a9be8fbf27a1fd944f0f0afa6d1bcfcaf1528ba17f2'
F=read(N/'frozen.json')
assert len(F['inputs'])==423
for p,h in F['inputs'].items():assert 'sha256:'+sha(p)==h,p
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=F['owner'],text=True).strip()==F['ownerCommit']
for d in [O,N]:
 assert not any((d/n).exists()for n in['APPROVAL.json','receipt.json','supervisor.json','database','run'])
v=dict(status='read-only-audit-and-preparation-verified',sourceArtifactsMatched=True,ownedContainersStillStopped=True,hostEnvironmentOverridesAbsent=True,supersededProposalUnmodifiedAndUnexecuted=True,all423PreparedBindingsMatched=True,originalOwnerCommitMatched=True,preparedProposalFrozenSha256=sha(N/'frozen.json'),applicationExecutionAuthorized=False,applicationOrDatabaseRunsExecuted=0,liveFalsePositiveReproductionExecuted=False,databaseExitRootCauseKnown=False,reviewerSha256=sha(__file__))
with(A/'verification-final.json').open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))
