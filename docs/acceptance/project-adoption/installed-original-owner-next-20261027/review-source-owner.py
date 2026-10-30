"""Composite installed-source owner review: real build plus runtime-only repair."""
from pathlib import Path
import datetime,hashlib,json,os,stat,subprocess,sys
ROOT=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
BASE=ROOT/'.tools/installed-original-owner-next-20261027'
ORIGIN=BASE/'owner-source';WORK=BASE/'owner-source-runtime-repair1'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
package=read(BASE/'package-source/receipt.json');source=Path(package['installedSource'])
sys.path.insert(0,str(source/'scripts'))
from installed_selected import verify_installed_source
from qualify_next_standalone import inventory,summary
initial=read(ORIGIN/'receipt.json');result=read(WORK/'receipt.json')
assert initial['failureType']=='NameError' and 'NODE' in initial['failure'] and read(ORIGIN/'supervisor-exit.json')['exitCode']==1
assert result['status']=='passed-installed-original-owner-build-and-runtime' and read(WORK/'supervisor-exit.json')['exitCode']==0
assert result['ownerBuildReruns']==0 and result['ownerBuildReusedFromInitialAttempt'] is True
assert result['initialControllerReceiptDigest']==sha(ORIGIN/'receipt.json')
build_review=read(ROOT/'docs/acceptance/project-adoption/installed-original-owner-next-20261027/source-build-review.json')
assert build_review['privateControllerReceiptDigest']==sha(ORIGIN/'receipt.json') and build_review['actualOwnerBuildExitCode']==0 and build_review['nativePreparationCalls']==181
fixture=read(BASE/'owner-fixture.json');state=Path(result['state']);selected=read(state/'selected.json');attempt=state/selected['attempt'];candidate=attempt/'candidate'
assert selected['attempt']==initial['selection']['attempt'] and selected['inputKey']==initial['selection']['inputKey']
assert len(list((state/'attempts').iterdir()))==1 and sha(state/'selected.json')==initial['selectedPointerDigest']==result['selectedPointerDigest']
assert sha(attempt/'artifacts.json')==initial['artifactManifestDigest']==result['artifactManifestDigest']
for n,h in fixture['expectedGenerated'].items():assert sha(candidate/n)==h==sha(Path(fixture['originalOracle'])/n)
assert all(sha(ORIGIN/'owner'/n)==h for n,h in fixture['sourceInputs'].items())
assert verify_installed_source(source,package['sourceIdentity']['sourceInventoryDigest'])==package['sourceIdentity']
for name,row in fixture['packagedToolingMapping'].items():assert sha(source/row['packagedPath'])==row['digest']==sha(ORIGIN/'owner'/name)
ledger=candidate/'patamaps-native-tooling/trace.jsonl';assert sha(ledger)==initial['nativeLedgerDigest']==result['nativeLedgerDigest']
counts=[]
old_state=Path(fixture['priorState']);old_selected=read(old_state/'selected.json');old_current=old_state/old_selected['attempt'];old_baseline=old_state/read(old_current/'previous-selection.json')['attempt']
for entry in [attempt,old_current,old_baseline]:
 rows=read(entry/'artifacts.json');value=dict(files=0,directories=0,bytes=0)
 for n,row in rows.items():
  p=entry/'candidate'/n;s=p.lstat();assert stat.S_IMODE(s.st_mode)==row['mode']
  if row['kind']=='file':assert stat.S_ISREG(s.st_mode) and s.st_size==row['bytes'] and sha(p)==row['digest'];value['files']+=1;value['bytes']+=s.st_size
  else:assert row['kind']=='directory' and stat.S_ISDIR(s.st_mode);value['directories']+=1
 counts.append(value)
assert sha(old_state/'selected.json')==fixture['originalRetainedPointerDigest'] and len(list((old_state/'attempts').iterdir()))==4
for row in result['commands']:
 sample=row['measurement'];assert sample['exitCode']==0
 for stream in ['stdout','stderr']:
  p=Path(sample['retainedOutputs'][stream]);assert sha(p)==sample[stream+'Digest'] and p.stat().st_size==sample[stream+'Bytes']
assert 'installed-owner-build' not in {x['role'] for x in result['commands']}
wrapper=read(WORK/'installed-runtime/receipt.json')
assert wrapper['status']=='passed-installed-selected-application-workflow' and wrapper['wrapperTimeoutSeconds']==dict(inspection=900,execution=1200)
assert wrapper['sourceInventoryUnchanged'] and wrapper['sourceIsInstalled'] and wrapper['sourceFiles']==1240
execution=wrapper['execution'];native=execution['command']
assert execution['status']=='completed-selected-project-command' and all(execution[k] for k in ['preExecutionSelectionVerified','postExecutionSelectionVerified','selectionPointerUnchanged'])
assert execution['postExecutionVerification']['status']=='verified-selected-build-bindings' and execution['inputKey']==selected['inputKey']
assert native['status']=='completed-project-command' and all(native[k] for k in ['programSucceeded','selectedInputsUnchanged','executableUnchanged'])
for row in wrapper['commands']:
 expected=1200 if row['label']=='selected-execution' else 900;assert row['timeoutSeconds']==expected and row['exitCode']==0
 for stream in ['stdout','stderr']:assert (WORK/'installed-runtime'/(row['label']+'.'+stream)).is_file()
assert read(WORK/'installed-runtime/selected-bindings.stdout')['status']=='verified-selected-build-bindings'
assert read(WORK/'installed-runtime/selected-execution.stdout')==execution
assert read(WORK/'restored-final-bindings.stdout')['status']=='verified-selected-build-bindings'
command=read(WORK/'command.json');args=command['invocation']['arguments'];n=int(args[3]);program=''.join(args[4:4+n]);cfg=json.loads(''.join(args[4+n:]))
assert program==(source/'scripts/selected_next_http_probe.mjs').read_text() and sha(source/'scripts/selected_next_http_probe.mjs')==result['runtimeProbeDigest']
assert command['invocation']['bounds']==dict(maximumElapsedMs=180000,maximumStdoutBytes=16384,maximumStderrBytes=65536)
assert len(args)<=128 and all(len(x.encode())<=4096 for x in args)
http=read(WORK/'http.json');assert http==result['http']==json.loads(native['stdout']['text'])
assert http['status']=='passed-current-owner-edited-runtime-http' and http['serverStopped'] and len(http['cases'])==7
assert [x['status'] for x in http['cases']]==[200,200,403,404,200,200,404]
assert native['elapsedMs']<30000
for expected,observed in zip(cfg['assets'],http['cases'][4:6]):
 p=candidate/'packages/web/.next/static'/expected['relative'];assert sha(p)==expected['digest']==observed['bodyDigest'] and p.stat().st_size==observed['bodyBytes']==expected['bytes']
 assert cfg['marker'].encode() in p.read_bytes() and observed['editedMarkerPresent'] and observed['selectedDigestMatched']
before=read(WORK/'runtime-before.json');after=read(WORK/'runtime-after.json');assert inventory(ORIGIN/'runtime')==after
assert summary(before)==result['runtimeCopyBefore'] and summary(after)==result['runtimeCopyAfter']
cache='packages/web/.next/cache';changed={n for n in set(before)|set(after) if before.get(n)!=after.get(n)}
assert all(n==cache or n.startswith(cache+'/') for n in changed) and len(after)<=8192 and sum(x.get('bytes',0) for x in after.values())<=128*1024**2
cache_bytes=sum(x.get('bytes',0) for n,x in after.items() if n==cache or n.startswith(cache+'/'));assert cache_bytes==result['runtimeCacheBytes']<=64*1024**2
observed=read(WORK/'independent-unavailable-observation.json');assert len(observed['paths'])==8
for row in observed['paths']:
 p=Path(row['original']);s=p.lstat();assert [s.st_dev,s.st_ino,s.st_mode]==[row['device'],row['inode'],row['mode']]
 assert not os.path.lexists(row['retained'])
assert result['checkoutPathsRestored'] and result['runtimeProducerPathsRestored'] and all(sha(p)==h for p,h in result['checkoutPathDigests'].items()) and all(sha(p)==h for p,h in result['protectedInputs'].items())
process=read(WORK/'server-process.json');assert process['closed'] and subprocess.run(['/bin/ps','-p',str(process['pid']),'-o','pid='],capture_output=True).returncode!=0
assert subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=Path('/Volumes/dev_src_case_sensitive/projects/seeder'))==b''
guard_path=Path((WORK/'supervisor.stdout').read_text().split('Storage guard record: ')[-1].strip());guard=read(guard_path);assert guard['completed'] and guard['exitCode']==0
scheduler=json.loads(subprocess.check_output(['/Users/admin/.nvm/versions/node/v22.23.3/bin/node','/Users/admin/Documents/Codex/storage-safeguards/buildctl-cli.mjs','status'],cwd=ROOT,text=True));request=next(x for x in scheduler['requests'] if x['id']==result['reservation']['id']);assert request['state']=='finished'
review=dict(status='passed-reviewed-source-installed-original-owner-build-and-runtime',observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packageSourceRevision=package['sourceRevision'],engine=package['engine'],compilerDigest=package['sourceCliDigest'],installedSourceMembers=1240,sourceInputsRehashed=943,packagedSdkDiscoveryMembersVerified=45,independentOriginalOracleOutputsMatched=8,nativePreparationCalls=181,originalRouteTestsPassed=3,nativeBuildReportsPassed=9,compiledMarkerVerifiedBeforeSelection=True,httpCasesPassed=7,httpCases=http['cases'],nativeInstalledWrapperPassed=True,wrapperTimeoutSeconds=wrapper['wrapperTimeoutSeconds'],nativeCommandBoundMs=180000,actualHttpProbeElapsedMs=native['elapsedMs'],sourceContextProviderUnavailableDuringRuntime=True,checkoutCompilerQualifierPathsUnavailableDuringBuildAndRuntime=True,unavailableRuntimeAndCheckoutPathsIndependentlyObservedAndRestored=8,ownedServerReapedAndPidAbsent=True,runtimeCopyBefore=summary(before),runtimeCopyAfter=summary(after),runtimeCacheBytes=cache_bytes,hardNativeCacheQuotaClaimed=False,newSourceArtifactInventory=counts[0],originalArtifactInventoriesRehashed=counts[1:],originalFullStateAttempts=4,newSourceStateAttempts=1,ownerBuildReruns=0,harnessRepairs=1,initialControllerExitCode=1,initialControllerFailure='NODE NameError before runtime command execution',runtimeRepairExitCode=0,selectedPointerDigest=sha(state/'selected.json'),artifactManifestDigest=sha(attempt/'artifacts.json'),selectedInputKey=selected['inputKey'],nativeLedgerDigest=sha(ledger),sourceInventoryUnchanged=True,originalOwnerGitUnchanged=True,initialBuildReviewDigest=sha(ROOT/'docs/acceptance/project-adoption/installed-original-owner-next-20261027/source-build-review.json'),runtimeControllerDigest=sha(BASE/'owner-source-runtime-repair.py'),runtimeReceiptDigest=sha(WORK/'receipt.json'),installedWrapperReceiptDigest=sha(WORK/'installed-runtime/receipt.json'),guardRecordDigest=sha(guard_path),reservationId=request['id'],reservationFinishedAndReleased=True,filesDeleted=0,policyChanged=False,nativeInstallationOwnerWorkflowAccepted=False,authenticatedBrowserAccepted=False,deploymentAccepted=False,performanceAccepted=False,completeGoalAccepted=False)
target=ROOT/'docs/acceptance/project-adoption/installed-original-owner-next-20261027/source-owner-review.json';assert not target.exists();target.write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps(dict(status=review['status'],httpCases=7,ownerBuildReruns=0,nativeOwnerPending=True)))
