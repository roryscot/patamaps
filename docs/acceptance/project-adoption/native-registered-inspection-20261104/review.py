from pathlib import Path
import json,hashlib
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/native-registered-inspection-20261028/retry-proposal-1';D=B/'ownership-change-recovery-20261104';P=R/'docs/acceptance/project-adoption/native-registered-inspection-20261104'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=read(B/'result.json');assert result['status']=='failed'and result['testExitCode']==1
assert read(B/'supervisor-exit.json')['exitCode']==75
tap=(B/'tests.stdout').read_text()
assert '# pass 1\n'in tap and '# fail 1\n'in tap and '# cancelled 0\n'in tap
assert 'PROJECT_CONTEXT: Explicit retained context refused'in tap and 'actual: 2'in tap
for name,h in result['sourceBindings'].items():assert sha(R/name)==h
supply=read(B/'inputs.json')
for path,h in supply['expectedState'].items():assert sha(path)==h
assert sorted(p.name for p in(Path(supply['inputs']['state'])/'attempts').iterdir())==['1793122875791456000-6699']
proof=read(D/'review-1/stop-proof.json');recovery=read(D/'recovery-result.json')
assert len(proof['observations'])==2 and all(o['ownedProcessesStopped']and o['canonicalGroupStopConfirmed']and o['unclassifiedProjectProcesses']==0 and o['protectedDatabaseUnchanged']for o in proof['observations'])
assert proof['registeredChannelsClosed']and recovery['failedSupervisorExitCode']==75
request=read('/Users/admin/Documents/Codex/.storage-control/heavy-builds/scheduler/requests/df47f504-2503-45cc-9f44-f7f02d6bc2b8.json')
assert request['state']=='finished'and request['leaseReleaseCompleted']and request['exitCode']==75
assert request['operatorRecovery']==recovery
assert sha(D/'request.original.json')==proof['originalRequestSha256']==recovery['originalRequestSha256']
assert sha(D/'review-1/stop-proof.json')==recovery['stopProofSha256']
assert sha('/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs')=='3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0'
value=dict(status='verified-failed-native-registration-attempt-and-reviewed-stop-recovery',ownerAuthorization='2026-11-04 autonomous continuation',scopeSha256=sha(B/'scope.json'),testSourceSha256=result['sourceBindings']['scripts/test_native_inspection_registration.mjs'],testsPassed=1,testsFailed=1,testsCancelled=0,nativeExitCode=2,nativeFailureCode='PROJECT_CONTEXT',supervisorExitCode=75,supervisorFinalizationError='Storage lease ownership changed',originalGuardRunRecordUnavailable=True,missingLeaseRootCauseUnknown=True,registrationAccepted=False,automaticReleaseAccepted=False,originalApplicationBuildsRun=0,oldSelectedStatePreimagesRehashed=len(supply['expectedState']),oldBuildAttemptDirectoryUnchanged=True,artifactContentsIndependentlyRehashedThisReview=False,sourceBindingsMatched=True,ownedPidsConfirmedStopped=len(proof['ownedPids']),ownedGroupsConfirmedStopped=len(proof['ownedGroups']),registeredControlChannelClosed=True,reviewedStopObservations=2,preexistingSignedSystemProcessesClassified=proof['observations'][0]['preexistingSystemProcesses'],protectedDatabaseIdentityUnchangedAtBothObservations=True,compatibilityLeaseWasMissingBeforeRecovery=True,reservationRecoveredAfterStopReview=True,failedExit75Preserved=True,installedGuardUnchanged=True,filesDeleted=0,servicesInterrupted=0,resourcePolicyChanged=False,parallelActivated=False,fullGoalComplete=False,rawRecords={'testOutputSha256':sha(B/'tests.stdout'),'coordinatorResultSha256':sha(B/'result.json'),'stopProofSha256':sha(D/'review-1/stop-proof.json'),'recoveryRecordSha256':sha(D/'recovery-result.json')},reviewerSha256=sha(__file__))
P.mkdir()
with(P/'review.json').open('x')as out:json.dump(value,out,indent=2);out.write('\n')
for source,name in [(Path(__file__),'review.py'),(B/'retry.patch','retry.patch'),(B/'scope.json','scope.json'),(B/'run.proposed.py','coordinator.py'),(B/'APPROVAL.json','authorization.json'),(D/'RECOVERY_PLAN.md','recovery-plan.md'),(D/'audit-v2.py','stop-audit.py'),(D/'recover.mjs','recover.mjs')]:
 with(P/name).open('xb')as out:out.write(source.read_bytes())
print(json.dumps({k:value[k]for k in ['status','testsPassed','testsFailed','testsCancelled','nativeFailureCode','supervisorExitCode','reservationRecoveredAfterStopReview','filesDeleted']}))
