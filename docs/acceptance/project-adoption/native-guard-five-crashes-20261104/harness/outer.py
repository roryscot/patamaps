from pathlib import Path
import os,sys,json,subprocess,hashlib,time,signal,datetime,resource
B=Path(__file__).resolve().parent
W=B/'worker'
E=Path('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-candidate-parent-watch-20261104/engine')
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
sys.path.insert(0,str(E))
import native_inspection_guard as kernel
def read(p):return json.loads(Path(p).read_text())
def sha(p):return 'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):
 with p.open('x') as output:json.dump(value,output,indent=2);output.write('\n')
 p.chmod(384)
began=time.monotonic()
F=read(B/'frozen.json')
assert all(sha(p)==h for p,h in F['inputs'].items()),'CRASH_SUITE_INPUT_CHANGED'
# Harness log bounds are observed below; do not impose them on the pinned archive extractor.
def interrupted(signum,frame):raise RuntimeError('CRASH_SUITE_INTERRUPTED')
signal.signal(signal.SIGTERM,interrupted)
signal.signal(signal.SIGINT,interrupted)
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(RuntimeError('CRASH_SUITE_600_SECOND_DEADLINE')))
signal.alarm(600)
report=dict(status='running-shared-runtime-crashes',filesDeleted=0,installedGuardChanged=False,parallelActivated=False,fullTenCaseSuiteAccepted=False,startedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
owner=None;observer=None;injection=None;observerSurvived=False;failure=None
def identities():
 found={}
 for path in W.glob('*/supervisor-status.json'):
  status=read(path)
  values=[status['controllerIdentity']]
  for call in status['calls']:values.extend(call.get(k) for k in ['guardianIdentity','nativeIdentity'] if call.get(k))
  for value in values:found[value['pid']]=value
 return found
def cleanup():
 outcomes=[]
 for value in identities().values():
  ok=kernel.stop_registered(value,.2)
  outcomes.append(dict(pid=value['pid'],stopped=bool(ok),groupStopped=not kernel.group_live(value['pid'])))
 if owner is not None and owner.poll() is None:
  value=kernel.process_identity(owner.pid)
  if value and value['parentPid']==os.getpid():os.kill(owner.pid,signal.SIGTERM)
 if observer and kernel.group_live(observer['pid']):
  value=kernel.process_identity(observer['pid'])
  if value and all(value[k]==observer[k] for k in ['pid','pgid','startSeconds','startMicroseconds']):kernel.stop_registered(value,.2)
 return outcomes
try:
 with (B/'preflight.stdout').open('xb') as out,(B/'preflight.stderr').open('xb') as err:
  code=subprocess.run(['/Users/admin/.nvm/versions/node/v22.23.3/bin/node','--test','--test-reporter=tap',str(B/'test_bridge.mjs')],stdout=out,stderr=err,timeout=20).returncode
 text=(B/'preflight.stdout').read_text()
 assert code==0 and '# tests 14' in text and '# fail 0' in text and '# skipped 0' in text,'CRASH_SUITE_BRIDGE_CONTROLS_FAILED'
 for p,h in F['expectedProtectedState'].items():assert sha(p)==('sha256:'+h if not h.startswith('sha256:') else h)
 env=dict(os.environ)
 with (B/'owner.stdout').open('xb') as out,(B/'owner.stderr').open('xb') as err:
  owner=subprocess.Popen([sys.executable,'-I','-S','-B',str(W/'owner.py')],env=env,stdout=out,stderr=err,start_new_session=True)
 deadline=time.monotonic()+500
 while time.monotonic()<deadline:
  for log in [B/'preflight.stdout',B/'preflight.stderr',B/'owner.stdout',B/'owner.stderr',W/'driver.stdout',W/'driver.stderr']:
   if log.exists() and log.stat().st_size>4194304:raise RuntimeError('CRASH_SUITE_HARNESS_LOG_BOUND')
  meta=W/'owner-process.json';result=W/'pilot-result.json';status=W/'owner-parent-death/supervisor-status.json'
  if meta.exists():
   record=read(meta)
   assert record['ownerPid']==owner.pid and record['ownerParentPid']==os.getpid(),'OWNER_PROCESS_LINEAGE_CHANGED'
   actual=kernel.process_identity(record['childPid'])
   if actual and not observer:
    assert actual['parentPid']==owner.pid and actual['pgid']==record['childGroup']==record['childPid'],'OBSERVER_INITIAL_LINEAGE_CHANGED'
    observer=actual
  if not injection and status.exists() and observer:
   current=read(status)
   call=next((c for c in current['calls'] if c.get('registrationKnown') and c.get('nativeIdentity')),None)
   if call:
    parent=kernel.process_identity(owner.pid);child=kernel.process_identity(observer['pid']);native=kernel.process_identity(call['nativeIdentity']['pid'])
    if parent and parent['parentPid']==os.getpid() and child and child['parentPid']==owner.pid and native==call['nativeIdentity']:
     injection=dict(atMs=int(time.time()*1000),atMonotonic=time.monotonic(),owner=parent,observer=child,native=native)
     save(B/'active-parent-death-injection.json',injection)
     os.kill(owner.pid,signal.SIGKILL)
  if injection:
   assert time.monotonic()-injection['atMonotonic']<=60,'ACTIVE_PARENT_DEATH_RELEASE_EXCEEDED_60_SECONDS'
   actual=kernel.process_identity(observer['pid'])
   if actual and all(actual[k]==observer[k] for k in ['pid','pgid','startSeconds','startMicroseconds']) and actual['parentPid']!=owner.pid:observerSurvived=True
  if result.exists():
   value=read(result)
   if value['failure']:raise RuntimeError(value['failure']['code'])
   if observer and not kernel.group_live(observer['pgid']):
    assert injection and observerSurvived and owner.wait(timeout=5)==-signal.SIGKILL,'SURVIVING_TRUSTED_OBSERVER_NOT_PROVED'
    expected=['normal-engine','cancel-unchanged','controller-crash','guardian-crash','owner-parent-death']
    assert [x['name'] for x in value['rows']]==expected
    assert all(x['reservationReleased'] and x['channelClosed'] for x in value['rows'])
    assert value['rows'][0]['code']==0 and value['rows'][1]['code']==75 and value['rows'][2]['code']!=0 and value['rows'][3]['code']!=0 and value['rows'][4]['code']==75
    report.update(status='passed-five-staged-native-shared-runtime-cases',cases=value['rows'],parentDeathToObserverStopMs=round((time.monotonic()-injection['atMonotonic'])*1000),trustedObserverSurvivedOwnerDeath=True,controlledParentExitCode=-signal.SIGKILL,observerGroupStopped=True,observerExitCodeNotDirectlyObserved=True,bridgeControlsPassed=14,runtimeCopies=1)
    break
  if owner.poll() is not None and not injection:raise RuntimeError('OWNER_EXITED_BEFORE_PARENT_DEATH_CASE')
  time.sleep(.02)
 else:raise RuntimeError('CRASH_SUITE_PHASE_DEADLINE')
except BaseException as error:
 failure=type(error).__name__;message=str(error)
 report.update(status='failed-staged-native-shared-runtime-cases',failureType=failure,failureCode=message if message and all(c.isupper() or c.isdigit() or c=='_' for c in message) else 'PRIVATE_DIAGNOSTIC_REQUIRED')
finally:
 signal.alarm(0)
 outcomes=cleanup()
 report['independentOwnedProcessStop']=outcomes
 report['allObservedRegisteredGroupsStopped']=all(x['stopped'] and x['groupStopped'] for x in outcomes)
 if owner is not None:
  try:owner.wait(timeout=5)
  except subprocess.TimeoutExpired:report['ownerStopUnconfirmed']=True
 # A cancellation failure must keep the canonical outer reservation conservative.
 if not report['allObservedRegisteredGroupsStopped'] or report.get('ownerStopUnconfirmed'):
  parent=int(os.environ.get('WARGAME_STORAGE_OWNER_PID','0'))
  if parent>1 and parent==os.getppid():os.kill(parent,signal.SIGTERM)
  report['canonicalStopRequestedForUncertainty']=True
 protected=read(B/'protected-service-before.json')
 db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',protected['id']],text=True,timeout=15))[0]
 report['protectedDatabaseStartIdentityUnchanged']=dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==protected
 report['allFrozenInputsStillMatched']=all(sha(p)==h for p,h in F['inputs'].items())
 report['allProtectedSelectedStateStillMatched']=all(sha(p)==('sha256:'+h if not h.startswith('sha256:') else h) for p,h in F['expectedProtectedState'].items())
 report['finishedAtUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 report['phaseElapsedSeconds']=time.monotonic()-began
 save(B/'shared-crash-review.json',report)
if failure or report['status']!='passed-five-staged-native-shared-runtime-cases' or not all(report[k] for k in ['allObservedRegisteredGroupsStopped','protectedDatabaseStartIdentityUnchanged','allFrozenInputsStillMatched','allProtectedSelectedStateStillMatched']):raise SystemExit(1)
