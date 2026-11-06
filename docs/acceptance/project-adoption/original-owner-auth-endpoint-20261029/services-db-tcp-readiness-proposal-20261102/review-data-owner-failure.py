from pathlib import Path
import json,hashlib,tarfile
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
B=R/'.tools/owner-auth-endpoint-20261029'
D=B/'services-db-tcp-readiness-proposal-20261102'
N=B/'services-data-owner-proposal-20261102'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
a=read(D/'receipt.json')
assert a['failure']=='OWNED_POSTGRES_EXITED_BEFORE_READY'and a['servicesStarted']==1 and not a.get('databaseTcpReadinessAccepted',False)and a['cases']==[]
raw=(D/'postgres-startup.stdout.private').read_text()
assert 'FATAL:  data directory "/var/lib/postgresql/data" has wrong ownership'in raw
review=read(R/'docs/acceptance/project-adoption/original-owner-auth-endpoint-20261029/services-db-tcp-readiness-proposal-20261102/review.json')
assert review['ownedContainerInspectedStopped']and review['startupAttachmentAndWorkerGroupStopped']and review['leaseReleased']and review['testPortsHaveNoListeners']
assert not any((D/'run'/n).exists()for n in ['controls-migrate.json','migrate.stdout','seed.stdout','server.stdout'])
F=read(N/'frozen.json')
assert sha(N/'frozen.json')=='sha256:99ac212622b370b39a5f3dc4eac7cd4a5c9d037fcc3b21352a76627d0075afac'
assert len(F['inputs'])==425
for p,h in F['inputs'].items():assert sha(p)==h,p
with tarfile.open(N/'empty-data-owner.tar','r:')as t:
 m=t.getmembers();assert len(m)==1 and m[0].name=='.'and m[0].isdir()and m[0].uid==501 and m[0].gid==20 and m[0].mode==0o700 and m[0].size==0 and not m[0].pax_headers
assert not any((N/n).exists()for n in ['APPROVAL.json','receipt.json','supervisor.json','database','run'])
ownership=read(D/'ownership-postmortem.json')
v=dict(status='captured-data-owner-failure-and-candidate-preparation-verified',failureCondition='PostgreSQL refused owned data-directory ownership',failureInThisRunEstablished=True,underlyingUIDProjectionMechanismVerified=False,archiveMetadataProvesProcessStat=False,archiveRootUidObserved=ownership['containerArchiveRoot']['uid'],hostRootUidObserved=ownership['hostRoot']['uid'],workloadConfiguredUid=501,originalMigrationsExecuted=False,httpAuthenticationCasesExecuted=0,browserCasesExecuted=0,ownedContainerAndAttachmentStopped=True,allTestPortsClosed=True,reservationReleased=True,sourceStartupStdoutDigest=sha(D/'postgres-startup.stdout.private'),candidateManifestSha256=sha(N/'frozen.json')[7:],candidateAll425BindingsMatched=True,metadataTarIsSingleEmptyDirectory=True,candidateMetadataOperationApplied=False,candidateRuntimeOwnershipGuardExecuted=False,automaticPhaseRetriesExecuted=0,readOnlyInspectionAdapterNote='First Python xattr call unavailable; macOS xattr CLI used instead, no application reexecution',reviewerDigest=sha(__file__))
with(D/'ownership-failure-review.json').open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))
