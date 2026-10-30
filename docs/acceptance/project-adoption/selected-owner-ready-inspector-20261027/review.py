"""Independent review of retained ready-inspector process controls."""
from pathlib import Path
import ast,datetime,hashlib,json,subprocess
ROOT=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
PRIVATE=ROOT/'.tools/browser-lifecycle-preparation-20261027'
WORK=PRIVATE/'retry1';cases=WORK/'controls-run'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
launch=read(WORK/'launch.json');initial=read(PRIVATE/'launch.json')
assert read(WORK/'supervisor-exit.json')['exitCode']==0
assert read(PRIVATE/'supervisor-exit.json')['exitCode']==75 and not (PRIVATE/'controls-run').exists()
assert sha(PRIVATE/'selected_next_http_probe.mjs')==launch['probeDigest']==initial['probeDigest']
assert sha(PRIVATE/'test_selected_next_ready_inspector.py')==launch['testDriverDigest']==initial['testDriverDigest']
assert sha(ROOT/'scripts/selected_next_http_probe.mjs')==read(PRIVATE/'preparation.json')['baselineDigest']
expected={
 'test_default_seven_cases_are_unchanged':(0,None,False),
 'test_invalid_inspector_refuses_before_server_or_outputs':(1,None,False),
 'test_inspector_requests_the_live_owned_server':(0,None,True),
 'test_inspector_failure_stops_owned_server':(1,'OWNER_INSPECTOR_TEST_FAILURE',False),
 'test_reappeared_producer_refuses_after_inspector':(1,'OWNER_PRODUCER_REAPPEARED',False),
 'test_sigterm_during_inspector_stops_owned_server':(1,'OWNER_PROBE_CANCELLED',False)}
tree=ast.parse((PRIVATE/'test_selected_next_ready_inspector.py').read_text())
methods={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
assert methods==set(expected) and {p.name for p in cases.iterdir()}==set(expected)
stderr=(WORK/'supervisor.stderr').read_text()
assert 'Ran 6 tests' in stderr and '\nOK\n' in stderr and 'skipped' not in stderr.lower()
for name in expected:assert name+' (' in stderr
outcomes=[];servers=0;http_cases=0
for name,(exit_code,failure,inspected) in expected.items():
 case=cases/name;result=read(case/'exit.json')
 assert result==dict(exitCode=exit_code,timedOut=False)
 assert (case/'driver.stdout').stat().st_size<16384 and (case/'driver.stderr').stat().st_size<65536
 if name=='test_invalid_inspector_refuses_before_server_or_outputs':
  assert all(not (case/p).exists() for p in ['app/started.marker','http.json','server-process.json','server.stdout'])
  assert 'OWNER_PROBE_INSPECTOR' in (case/'driver.stderr').read_text()
  outcomes.append(dict(control=name,passed=True,driverExitCode=exit_code,beforeEffectsRefusal=True));continue
 report=read(case/'http.json');process=read(case/'server-process.json')
 assert process['closed'] and report['serverStopped']
 assert subprocess.run(['/bin/ps','-p',str(process['pid']),'-o','pid='],capture_output=True).returncode!=0
 assert [r['status'] for r in report['cases']]==[200,200,403,404,200,200,404]
 assert bool(report.get('readyInspectionCompleted'))==inspected
 assert report['status']==('failed' if failure else 'passed-current-owner-edited-runtime-http')
 if failure:assert failure in report['failureCodes']
 if inspected:assert read(case/'http.json.inspection.json')['ready']
 outcomes.append(dict(control=name,passed=True,driverExitCode=exit_code,ownedServerReapedAndPidAbsent=True,fixtureHttpCases=7,inspectionCompleted=inspected,expectedFailureCode=failure))
 servers+=1;http_cases+=7
guard_path=Path((WORK/'supervisor.stdout').read_text().split('Storage guard record: ')[-1].strip())
guard=read(guard_path);assert guard['completed'] and guard['exitCode']==0
node='/Users/admin/.nvm/versions/node/v22.23.3/bin/node'
status=json.loads(subprocess.check_output([node,'/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs','status'],cwd=ROOT,text=True))
request_id=(WORK/'supervisor.stderr').read_text().split('Build reservation queued: ')[1].split(';')[0]
request=next(x for x in status['requests'] if x['id']==request_id);assert request['state']=='finished'
recovery=ROOT/'.tools/idle-workspace-review-20261027/approved-recovery'
record=read(recovery/'receipt.json')
assert record['status']=='passed-approved-nondeleting-storage-recovery' and read(recovery/'exit.json')['exitCode']==0
assert record['fullReadonlyRecoveryComparisonPassed'] and record['recoveredInventoryEntriesVerified']==205145 and record['recoveredFilesVerified']==183991
assert record['imageClosedAndPreserved'] and record['databaseReady'] and record['originalDatabaseConfigurationPreserved']
assert record['filesDeleted']==record['containersDeleted']==record['imagesDeleted']==record['volumesDeleted']==0
cap=read(recovery/'canonical-capacity-check.stdout')
assert cap['retainedAllocatedBytesUpperBound']+cap['policy']['maximumRunGrowthBytes']<=cap['policy']['maximumRetainedBytes']
result=dict(status='passed-reviewed-selected-owner-ready-inspector-controls',observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 sourceRevisionBeforeImplementation=launch['sourceRevision'],baselineProbeDigest=read(PRIVATE/'preparation.json')['baselineDigest'],proposedProbeDigest=launch['probeDigest'],
 controlDriverDigest=launch['testDriverDigest'],controlsPassed=6,controls=outcomes,fixtureHttpCasesPassed=http_cases,ownedServersReapedAndAbsent=servers,
 exactNodeVersion=subprocess.check_output([node,'-p','process.version'],text=True).strip(),defaultResultSchemaPreserved=True,
 initialAdmissionExitCode=75,retrySupervisorExitCode=0,reservationId=request_id,reservationFinishedAndReleased=True,
 guardRecordDigest=sha(guard_path),privateRetryStdoutDigest=sha(WORK/'supervisor.stdout'),privateRetryStderrDigest=sha(WORK/'supervisor.stderr'),
 nondeletingRecovery=dict(fullFileAndMetadataComparisonPassed=True,entriesVerified=205145,filesVerified=183991,imageClosedAndPreserved=True,originalUnrelatedServiceReadyAndConfigurationPreserved=True,privateReceiptDigest=sha(recovery/'receipt.json')),
 retainedAllocatedBytesBeforeControls=cap['retainedAllocatedBytesUpperBound'],maximumRetainedBytes=cap['policy']['maximumRetainedBytes'],reservedGrowthBytes=cap['policy']['maximumRunGrowthBytes'],
 filesDeleted=0,policyChanged=False,realOwnerBrowserAccepted=False,realBackendAuthenticationAccepted=False,installedHelperAccepted=False,performanceAccepted=False,fullGoalAccepted=False)
target=ROOT/'docs/acceptance/project-adoption/selected-owner-ready-inspector-20261027'
target.mkdir(exist_ok=True);p=target/'receipt.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(status=result['status'],controlsPassed=6,fixtureHttpCasesPassed=http_cases,realBrowserPending=True)))
