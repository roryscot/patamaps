"""Exclusive Intel measurements of the previously qualified real Axum workspace."""
import argparse,copy,hashlib,json,os,platform,re,shutil,stat,statistics,subprocess,sys,time
from pathlib import Path
from bench_phases import measured
from bench_axum_build import probe_suffix,PHASES
from project_watch import stop

ROOT=Path(__file__).resolve().parent.parent
SOURCE_COMMIT='fc78d5bcdb276bd6fb53cf2db55e91757eabb469'
CONTROL=Path('/Users/admin/Documents/Codex/storage-safeguards')
NODE='/Users/admin/.nvm/versions/node/v22.23.3/bin/node'
SUPERVISORS=[CONTROL/'buildctl.mjs',CONTROL/'resource-executor.mjs',CONTROL/'engine/scripts/guarded-run.mjs']
SCRIPTS=['bench_axum_retained.py','bench_axum_build.py','bench_phases.py','project_watch.py']
CONTROL_ROOT=Path('.patamaps-measure')
PROBE='fn main() { println!("{}", axum::PATAMAPS_MEASURED_EDIT); }\n'
BUDGETS=dict(coldSeconds=900,warmMedianSeconds=30,warmMaximumSeconds=60,editSeconds=180,peakRssBytes=3*1024**3,workAllocatedBytes=2000000000)

def sha(path):
 with Path(path).open('rb') as source:return 'sha256:'+hashlib.file_digest(source,'sha256').hexdigest()

def write(path,value):
 with Path(path).open('x') as target:json.dump(value,target,indent=2);target.write('\n')

def checkpoint(path,value):
 # Only this coordinator's new receipt is updated; old attempts/files are retained.
 Path(path).write_text(json.dumps(value,indent=2)+'\n')

def footprint(root):
 total=dict(entries=0,files=0,symlinks=0,logicalFileBytes=0,allocatedBytes=0,hardlinkAliases=0);seen=set();pending=[Path(root)]
 while pending:
  p=pending.pop();s=p.lstat();total['entries']+=1
  assert total['entries']<=200000,'MEASUREMENT_FOOTPRINT_ENTRIES'
  key=(s.st_dev,s.st_ino)
  if key not in seen:total['allocatedBytes']+=s.st_blocks*512;seen.add(key)
  else:total['hardlinkAliases']+=1
  if stat.S_ISLNK(s.st_mode):total['symlinks']+=1
  elif stat.S_ISDIR(s.st_mode):pending.extend(p.iterdir())
  else:
   assert stat.S_ISREG(s.st_mode),'MEASUREMENT_FOOTPRINT_SPECIAL'
   total['files']+=1;total['logicalFileBytes']+=s.st_size
 return total

def validate_ownership(proof,phase,root=ROOT):
 assert proof['phase']==phase and proof['ownerAlive'] is True and proof['ownerIdentityVerified'] is True and proof['ownerIsAncestor'] is True,'MEASUREMENT_OWNER'
 assert proof['heartbeatStale'] is False and proof['cancellationRequested'] is False,'MEASUREMENT_HEARTBEAT_OR_CANCELLATION'
 assert proof['state']=='running' and proof['project']==str(root.resolve()) and proof['enforcement']=='native-exclusive' and proof['exclusive'] is True,'MEASUREMENT_RESERVATION'
 assert proof['otherActiveReservations']==0,'MEASUREMENT_CONCURRENT_RESERVATION'
 if phase=='benchmark':
  assert proof['runningContainers']==0,'MEASUREMENT_UNRESERVED_CONTAINER'
  reserve=proof['interactiveReserve'];machine=proof['machine']
  assert machine['cpu']>=reserve['cpu']+2 and proof['memoryPressureLevel']==1 and proof['memoryPressureCapacityEstimateBytes']>=reserve['memoryBytes'] and machine['freeDiskBytes']>=reserve['diskBytes'],'MEASUREMENT_INTERACTIVE_HEADROOM'
 return proof

LEASE_PROBE=r'''
import { inheritedLease } from '/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs';
import { Scheduler, processIdentity, nativeFinalizationPending } from '/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import { execFileSync } from 'node:child_process';
import { MacDocker } from '/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs';
const lease=inheritedLease();if(!lease)throw Error('MEASUREMENT_LIVE_PARENT_REQUIRED');
const s=new Scheduler(process.env.WARGAME_STORAGE_LEASE_DIR).status();
const r=s.requests.find(x=>x.id===lease.requestId);if(!r)throw Error('MEASUREMENT_REQUEST_REQUIRED');
let p=process.ppid,ancestor=false;for(let n=0;n<64&&p>1;n++){if(p===lease.pid){ancestor=true;break;}p=Number(execFileSync('/bin/ps',['-p',String(p),'-o','ppid='],{encoding:'utf8'}).trim());}
const pressure=Number(execFileSync('/usr/sbin/sysctl',['-n','kern.memorystatus_vm_pressure_level'],{encoding:'utf8',timeout:15000}).trim());
const memory=execFileSync('/usr/bin/memory_pressure',['-Q'],{encoding:'utf8',timeout:15000}).match(/System-wide memory free percentage:\s*(\d+)%/);if(!memory)throw Error('MEASUREMENT_MEMORY_TELEMETRY');
const percent=Number(memory[1]);if(percent<0||percent>100)throw Error('MEASUREMENT_MEMORY_TELEMETRY');
const ids=new MacDocker().running();
process.stdout.write(JSON.stringify({id:r.id,ownerPid:lease.pid,phase:r.phase,state:r.state,project:r.project,
 ownerAlive:r.ownerAlive,ownerIdentityVerified:r.owner.identity===processIdentity(lease.pid),ownerIsAncestor:ancestor,
 exclusive:r.exclusive,enforcement:r.enforcement,resourceLimits:r.limits,nativeResourceCapsEnforced:false,heartbeatStale:r.heartbeatStale,cancellationRequested:r.cancellationRequested,
 memoryPressureLevel:pressure,memoryPressureFreePercentage:percent,memoryPressureCapacityEstimateBytes:Math.floor(Math.max(0,percent-1)*s.machine.memoryBytes/100),otherActiveReservations:s.requests.filter(x=>x.id!==r.id&&(['running','needs-review'].includes(x.state)||nativeFinalizationPending(x))).length,
 runningContainers:ids.length,interactiveReserve:s.interactiveReserve,machine:s.machine}));
'''

def live_ownership(phase):
 assert platform.system()=='Darwin' and platform.machine()=='x86_64','MEASUREMENT_INTEL_ONLY'
 assert os.environ.get('BUILDCTL_PHASE','functional')==phase,'MEASUREMENT_PARENT_PHASE'
 try:proof=json.loads(subprocess.check_output([NODE,'--input-type=module','-e',LEASE_PROBE],stderr=subprocess.PIPE,timeout=30))
 except (subprocess.CalledProcessError,subprocess.TimeoutExpired):raise ValueError('MEASUREMENT_OWNERSHIP_UNAVAILABLE') from None
 return validate_ownership(proof,phase)

def capture_configs(capture,candidate):
 inputs={x['receipt']['path']:x for x in capture['inputs']};result={}
 for name in ['workspace.json','policy.json','package-projection.json']:
  item=inputs[name];raw=(candidate/name).read_bytes()
  assert raw==item['content'].encode() and sha(candidate/name)==item['receipt']['digest'] and len(raw)==item['receipt']['byteLength'],'MEASUREMENT_PRIOR_CONFIGURATION'
  result[name]=raw
 return result

def make_plan(prior,work,cli,cargo,rustc,inputs):
 plan=copy.deepcopy(prior);owner=work/'owner';tools=work/'tools'
 workspace=plan['workspace'];source=workspace['sources'][0]
 assert len(workspace['sources'])==1 and source['config']['features']==['axum/ws'] and source['config']['defaultFeatures'] is True and source['config']['view']=='resolved' and source['config']['platform']=='x86_64-apple-darwin','MEASUREMENT_PRIOR_PROFILE'
 source['invocation']['executable']=str(tools/'configured-provider')
 source['config'].update(cargo=str(cargo),rustc=str(rustc),cargoDigest=sha(cargo),rustcDigest=sha(rustc))
 settings=plan['project']['nonsecretConfiguration']
 settings.update(path=str(cargo.resolve().parent)+':/usr/bin:/bin',rustc=str(rustc),cargoHome=source['config']['cargoHome'],
  offline='true',jobs='2',debug='0',incremental='0',testThreads='1',home=str(work/'home'),tmp=str(work/'tmp'),targetDir=str(work/'cargo-target'),dontWriteBytecode='1')
 refs=dict(PATH='path',RUSTC='rustc',CARGO_HOME='cargoHome',HOME='home',TMPDIR='tmp',CARGO_TARGET_DIR='targetDir',CARGO_NET_OFFLINE='offline',CARGO_BUILD_JOBS='jobs',CARGO_PROFILE_DEV_DEBUG='debug',CARGO_PROFILE_TEST_DEBUG='debug',CARGO_INCREMENTAL='incremental',RUST_TEST_THREADS='testThreads',PYTHONDONTWRITEBYTECODE='dontWriteBytecode')
 code=[str(CONTROL_ROOT/n) for n in ['measurement-build.py','project_watch.py','measurement-consumer.rs','measurement.json']]
 def command(verify):
  return dict(profile='patamaps-project-command-1',workingDirectory='.',environmentReferences=refs,
   invocation=dict(executable=sys.executable,arguments=['-B',str(CONTROL_ROOT/'measurement-build.py'),'--config',str(CONTROL_ROOT/'measurement.json'),*(['--verify'] if verify else [])],codeInputs=code,bounds=dict(maximumElapsedMs=900000,maximumStdoutBytes=65536,maximumStderrBytes=65536)))
 plan['project']['inputs']=sorted(set(inputs)|set(code))
 plan['project']['components'].append(dict(id='measurement-control',kind='configuration',root=str(CONTROL_ROOT),entrypoints=code))
 plan.update(maximumRetainedAttempts=8,buildSteps=[command(False)],verificationSteps=[command(True)],outputs=[dict(path='bundle',kind='tree'),dict(path='generated/cargo-packages.json',kind='file')])
 return plan

def inspect_selection(state,expected,old_pointer=None,warm=False):
 pointer=(state/'selected.json').read_bytes();selected=json.loads(pointer);relative=Path(selected['attempt'])
 assert not relative.is_absolute() and len(relative.parts)==2 and relative.parts[0]=='attempts' and '..' not in relative.parts,'MEASUREMENT_ATTEMPT_PATH'
 attempt=state/relative;candidate=attempt/'candidate'
 assert candidate.resolve().is_relative_to(state.resolve()),'MEASUREMENT_ATTEMPT_PATH'
 lineage=json.loads((candidate/'bundle/lineage.json').read_bytes())
 assert set(lineage['artifacts'])=={'libaxum.rlib','libaxum_core.rlib','libaxum_extra.rlib','libaxum_macros.dylib','consumer'},'MEASUREMENT_SELECTED_MEMBERS'
 assert lineage['phase']==expected,'MEASUREMENT_SELECTED_EDIT'
 for name,row in lineage['artifacts'].items():
  p=candidate/'bundle'/name
  assert not p.is_symlink() and sha(p)==row['digest'] and p.stat().st_size==row['bytes'] and stat.S_IMODE(p.stat().st_mode)==row['mode'],'MEASUREMENT_SELECTED_ARTIFACT'
 verification=json.loads((attempt/'verify-001.json').read_bytes())
 assert verification['status']=='completed-project-command' and all(verification[k] is True for k in ['programSucceeded','selectedInputsUnchanged','executableUnchanged']),'MEASUREMENT_VERIFICATION_COMMAND'
 actual=json.loads(verification['stdout']['text'])
 assert actual['status']=='verified-measured-axum-build' and actual['upstreamTestsPassed']==459 and actual['consumerValue']==expected and actual['bundleUnchanged'] is True,'MEASUREMENT_SELECTED_CORRECTNESS'
 rows=actual['testSummaries'];assert len(rows)==4 and sorted(r['passed'] for r in rows)==[5,15,16,423] and all(r['failed']==r['ignored']==0 for r in rows),'MEASUREMENT_SELECTED_TEST_COUNTS'
 observation=json.loads((candidate/'generated/cargo-packages.json').read_bytes())
 assert sorted(e['subject']['attributes']['name'] for e in observation['entries'])==['axum','axum-core','axum-extra','axum-macros'],'MEASUREMENT_FOUR_PACKAGES'
 if warm:assert pointer==old_pointer,'MEASUREMENT_NOOP_POINTER'
 elif old_pointer is not None:assert selected['inputKey']!=json.loads(old_pointer)['inputKey'] and selected['attempt']!=json.loads(old_pointer)['attempt'],'MEASUREMENT_EDIT_SELECTION'
 return pointer,dict(attempt=selected['attempt'],inputKey=selected['inputKey'],pointerDigest='sha256:'+hashlib.sha256(pointer).hexdigest(),artifactDigests={k:v['digest'] for k,v in lineage['artifacts'].items()},consumerValue=expected,upstreamTestsPassed=459,testSummaries=actual['testSummaries'])

def require_result(result,warm):
 if warm:assert result['status']=='unchanged-project-build' and result['verification']=='not-repeated' and result['cacheHits']==0,'MEASUREMENT_NOOP_SEMANTICS'
 else:assert result['status']=='selected-project-build' and result['verification']=='commands-executed','MEASUREMENT_BUILD_SELECTION'

def phase_schedule():
 return [('cold','cold',900),*[(f'warm-{i}','cold',60) for i in range(1,4)],*[(p,p,180) for p in PHASES[1:]]]

def guarded(argv):return [sys.executable,'-B',str(ROOT/'scripts/project_watch.py'),'__guard',*map(str,argv)]

def prepare(args):
 proof=live_ownership('functional');work=args.work.resolve();assert work.is_relative_to(ROOT/'.tools') and not work.exists(),'MEASUREMENT_NEW_COUNTED_ROOT'
 prior=args.prior.resolve();prepared=json.loads((prior/'receipt.json').read_bytes());accepted=json.loads((prior/'build.receipt.json').read_bytes())
 assert prepared['sourceCommit']==accepted['sourceCommit']==SOURCE_COMMIT and accepted['status']=='passed-actual-rust-retained-build-scope' and accepted['upstreamLibraryTests']['passed']==459,'MEASUREMENT_PRIOR_ACCEPTANCE'
 cli=args.cli.resolve(strict=True);historical=args.prior_compiler.resolve(strict=True)
 assert sha(historical)==prepared['compilerDigest'],'MEASUREMENT_PRIOR_COMPILER'
 work.mkdir(mode=0o700);(work/'prepare-logs').mkdir();(work/'tools').mkdir();(work/'samples').mkdir();(work/'edits').mkdir()
 def native(label,argv):
  sample,raw=measured(guarded(argv),ROOT,dict(os.environ),retained=work/'prepare-logs'/label,deadline=120,cleanup=stop)
  assert sample['exitCode']==0,'MEASUREMENT_PREPARATION_COMMAND'
  return json.loads(raw)
 engine=native('current-engine',[cli,'engine']);sys.path.insert(0,str(ROOT/'scripts/parity'));from identity import identities
 assert engine==dict(schemaVersion='0.1.0',documentType='executor-description',**identities(ROOT)),'MEASUREMENT_CURRENT_ENGINE'
 state=Path(accepted['state']);before=(state/'selected.json').read_bytes()
 assert native('historical-bindings',[historical,'project-build-verify',state])['status']=='verified-selected-build-bindings'
 candidate=state/json.loads(before)['attempt']/'candidate';capture_path=candidate.parent/'candidate-capture.json'
 configs=capture_configs(json.loads(capture_path.read_bytes()),candidate)
 binding=json.loads((prior/'binding.json').read_bytes());snapshot=Path(binding['snapshot']);manifest=json.loads((snapshot/'manifest.json').read_bytes())
 assert manifest['digest']==binding['digest']==prepared['contextDigest'],'MEASUREMENT_PRIOR_SNAPSHOT'
 assert native('snapshot-verify',[cli,'project-context-verify',snapshot])['digest']==binding['digest']
 native('snapshot-stage',[cli,'project-context-stage',snapshot,'--destination',work/'owner'])
 owner=work/'owner'
 for name,raw in configs.items():
  with (owner/name).open('xb') as target:target.write(raw)
 lib=owner/'axum/src/lib.rs';base=lib.read_text();assert 'PATAMAPS_MEASURED_EDIT' not in base
 shutil.copy2(lib,work/'unmodified-axum-lib.rs');lib.write_text(base+probe_suffix('cold'))
 tools=work/'tools';shutil.copy2(cli,tools/'configured-provider');cli=tools/'configured-provider'
 old_plan=json.loads((candidate.parent/'plan.json').read_bytes());source_config=old_plan['workspace']['sources'][0]['config']
 for name in ['cargo','rustc']:(tools/('configured-'+name)).symlink_to(Path(source_config[name]).resolve(strict=True))
 cargo,rustc=[tools/('configured-'+n) for n in ['cargo','rustc']]
 assert sha(cargo)==source_config['cargoDigest'] and sha(rustc)==source_config['rustcDigest'],'MEASUREMENT_ORIGINAL_TOOLCHAIN'
 version=subprocess.check_output([rustc,'-vV'],text=True);assert 'rustc 1.99.0' in version and 'host: x86_64-apple-darwin' in version,'MEASUREMENT_TOOLCHAIN'
 for name in ['home','tmp']:(work/name).mkdir()
 controls=owner/CONTROL_ROOT;controls.mkdir()
 shutil.copy2(ROOT/'scripts/bench_axum_build.py',controls/'measurement-build.py');shutil.copy2(ROOT/'scripts/project_watch.py',controls/'project_watch.py')
 (controls/'measurement-consumer.rs').write_text(PROBE)
 config=dict(profile='patamaps-axum-measurement-build-1',phase='cold',cargo=str(cargo),cargoDigest=sha(cargo),rustc=str(rustc),rustcDigest=sha(rustc),target=str(work/'cargo-target'),workRoot=str(work),platform='x86_64-apple-darwin')
 write(controls/'measurement.json',config)
 plan=make_plan(old_plan,work,cli,cargo,rustc,old_plan['project']['inputs'])
 (owner/'workspace.json').write_text(json.dumps(plan['workspace'],indent=2)+'\n')
 write(work/'plan.json',plan)
 binding.update(overlays={'axum/src/lib.rs':manifest['entries']['axum/src/lib.rs']['digest']},writablePaths=['target','bundle','.measurement-private'])
 write(work/'binding.json',binding)
 assert native('prepared-input-key',[cli,'project-build-input-key',work/'plan.json','--source',owner,'--context',work/'binding.json'])['inputKey']
 assert (state/'selected.json').read_bytes()==before and not (work/'cargo-target').exists() and not (work/'state').exists()
 protected={str(snapshot/'manifest.json'):sha(snapshot/'manifest.json'),str(state/'selected.json'):sha(state/'selected.json'),str(capture_path):sha(capture_path)}
 record=dict(status='prepared-real-axum-measurements',sourceCommit=SOURCE_COMMIT,sourceRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),cli=str(cli),cliDigest=sha(cli),engine=engine,prior= str(prior),priorState=str(state),snapshot=str(snapshot),snapshotDigest=binding['digest'],protectedInputs=protected,supervisorDigests={str(p):sha(p) for p in SUPERVISORS},coordinatorDigests={name:sha(ROOT/'scripts'/name) for name in SCRIPTS},planDigest=sha(work/'plan.json'),bindingDigest=sha(work/'binding.json'),ownerInputs={name:sha(owner/name) for name in plan['project']['inputs']},sourceFiles=prepared['sourceFiles'],originalSelectedTextInputs=prepared['selectedTextInputs'],measuredTextInputs=len(plan['project']['inputs']),toolchain=version,preparationReservation=proof,budgets=BUDGETS,filesDeleted=0,nativeBenchmarkRun=False)
 write(work/'preparation.json',record);print(json.dumps(dict(status=record['status'],work=str(work),measuredTextInputs=record['measuredTextInputs'])))

def run(args):
 work=args.work.resolve();assert work.is_relative_to(ROOT/'.tools'),'MEASUREMENT_COUNTED_ROOT'
 prepared=json.loads((work/'preparation.json').read_bytes());assert prepared['status']=='prepared-real-axum-measurements' and prepared['budgets']==BUDGETS
 assert not (work/'state').exists() and not (work/'cargo-target').exists(),'MEASUREMENT_COLD_TARGET_ALREADY_USED'
 for name,digest in prepared['supervisorDigests'].items():assert sha(Path(name))==digest,'MEASUREMENT_SUPERVISOR_CHANGED'
 for name,digest in prepared['coordinatorDigests'].items():assert sha(ROOT/'scripts'/name)==digest,'MEASUREMENT_COORDINATOR_CHANGED'
 cli=Path(prepared['cli']);assert sha(cli)==prepared['cliDigest'] and sha(work/'plan.json')==prepared['planDigest'] and sha(work/'binding.json')==prepared['bindingDigest']
 owner=work/'owner';lib=owner/'axum/src/lib.rs';config_path=owner/CONTROL_ROOT/'measurement.json'
 assert all(sha(owner/n)==d for n,d in prepared['ownerInputs'].items()),'MEASUREMENT_OWNER_CHANGED'
 proof=live_ownership('benchmark');last_check=0;proofs=[]
 report=dict(status='running',preparationDigest=sha(work/'preparation.json'),sourceCommit=SOURCE_COMMIT,engine=prepared['engine'],budgets=BUDGETS,initialReservation=proof,samples=[],calibration=[],filesDeleted=0,completeDependencyClosure=False,performanceAdvantageClaimed=False,actualBenchmarkAccepted=False)
 output=args.output.resolve();assert output.is_relative_to(work) and not output.exists(),'MEASUREMENT_COUNTED_OUTPUT';output.mkdir(parents=True);receipt=output/'receipt.json'
 def save():checkpoint(receipt,report)
 def monitor(force=False):
  nonlocal last_check
  if force or time.monotonic()-last_check>=2:
   p=live_ownership('benchmark');assert p['id']==proof['id'],'MEASUREMENT_RESERVATION_CHANGED';proofs.append(p);last_check=time.monotonic()
 def observe_disk():
  observed=footprint(work);assert observed['allocatedBytes']<=BUDGETS['workAllocatedBytes'],'MEASUREMENT_WORK_DISK_BUDGET';return observed
 def one(label,argv,deadline):
  monitor(True);before=observe_disk()
  sample,raw=measured(guarded(argv),ROOT,dict(os.environ),retained=work/'samples'/label,deadline=deadline,monitor=monitor,cleanup=stop)
  monitor(True);after=observe_disk()
  assert sample['exitCode']==0,'MEASUREMENT_PROGRAM_FAILED'
  assert sample['peakRssBytes']<=BUDGETS['peakRssBytes'],'MEASUREMENT_MEMORY_BUDGET'
  assert sample['wallNanoseconds']<=deadline*1000000000,'MEASUREMENT_WALL_BUDGET'
  return sample,raw,before,after
 originals={}
 save()
 try:
  for mib in [0,64]:
   source='b=bytearray('+str(mib)+'*1024*1024);b[::4096]=b"1"*len(b[::4096]);print(len(b))'
   sample,raw,_,_=one('rss-'+str(mib),[sys.executable,'-B','-c',source],30)
   assert int(raw)==mib*1024**2;report['calibration'].append(dict(allocatedMiB=mib,**sample));save()
  delta=report['calibration'][1]['peakRssBytes']-report['calibration'][0]['peakRssBytes'];assert 48*1024**2<delta<96*1024**2,'MEASUREMENT_RSS_CALIBRATION'
  state=work/'state';pointer=None
  phases=phase_schedule()
  for label,value,deadline in phases:
   warm=label.startswith('warm-')
   if label.startswith('edit-'):
    retained=work/'edits'/label;retained.mkdir()
    lib.rename(retained/'lib.original.rs');originals.setdefault(lib,retained/'lib.original.rs')
    config_path.rename(retained/'config.original.json');originals.setdefault(config_path,retained/'config.original.json')
    with lib.open('x') as target:target.write((work/'unmodified-axum-lib.rs').read_text()+probe_suffix(value))
    config=json.loads((retained/'config.original.json').read_bytes());config['phase']=value;write(config_path,config)
   report['activePhase']=label;save()
   old_attempts=sorted(p.name for p in (state/'attempts').iterdir()) if state.exists() else []
   sample,raw,before,after=one(label,[cli,'project-build',work/'plan.json','--source',owner,'--state',state,'--context',work/'binding.json'],deadline)
   result=json.loads(raw);require_result(result,warm)
   new_pointer,selected=inspect_selection(state,value,pointer,warm)
   if warm:assert old_attempts==sorted(p.name for p in (state/'attempts').iterdir()),'MEASUREMENT_NOOP_NEW_ATTEMPT'
   pointer=new_pointer
   report['samples'].append(dict(phase=label,measurement=sample,beforeDisk=before,afterDisk=after,selected=selected,noOpVerificationNotRepeated=warm));save()
  warm_times=[s['measurement']['wallNanoseconds']/1e9 for s in report['samples'] if s['phase'].startswith('warm-')]
  assert len(warm_times)==3 and statistics.median(warm_times)<=BUDGETS['warmMedianSeconds'],'MEASUREMENT_WARM_MEDIAN'
  sample,raw,before,after=one('selected-bindings',[cli,'project-build-verify',state],120)
  assert json.loads(raw)['status']=='verified-selected-build-bindings','MEASUREMENT_FINAL_BINDINGS'
  report.update(status='passed-real-axum-retained-measurements',measurementGatesPassed=True,independentReviewRequired=True,actualBenchmarkAccepted=False,warmMedianSeconds=statistics.median(warm_times),finalBindingVerification=dict(measurement=sample,beforeDisk=before,afterDisk=after))
 except BaseException as error:
  report.update(status='failed',actualBenchmarkAccepted=False,failureType=type(error).__name__,failureCodes=sorted(set(re.findall(r'\bMEASURE(?:MENT|D)_[A-Z_]+\b',str(error)))));raise
 finally:
  if originals:
   final=work/'edits/final-retained';final.mkdir()
   for path,original in originals.items():
    if path.exists():path.rename(final/('lib.final.rs' if path==lib else 'config.final.json'))
    original.rename(path)
  restored=all(sha(owner/n)==d for n,d in prepared['ownerInputs'].items())
  protected=all(sha(Path(p))==d for p,d in prepared['protectedInputs'].items())
  tools=sha(cli)==prepared['cliDigest'] and all(sha(ROOT/'scripts'/n)==d for n,d in prepared['coordinatorDigests'].items()) and all(sha(Path(n))==d for n,d in prepared['supervisorDigests'].items())
  report.update(originalInputsUnchanged=protected,derivedOwnerRestored=restored,protectedOriginalRecordsUnchanged=protected,coordinatorAndCompilerUnchanged=tools,ownershipProofs=proofs)
  if not(restored and protected and tools):report.update(status='failed',actualBenchmarkAccepted=False,failureType='RestorationOrToolIdentity')
  save()
 assert report.get('measurementGatesPassed') is True and report['status']=='passed-real-axum-retained-measurements'
 print(json.dumps(dict(status=report['status'],samples=len(report['samples']),output=str(output))))

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
 a=sub.add_parser('prepare');a.add_argument('--work',type=Path,required=True);a.add_argument('--prior',type=Path,required=True);a.add_argument('--cli',type=Path,required=True);a.add_argument('--prior-compiler',type=Path,required=True)
 a=sub.add_parser('run');a.add_argument('--work',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
 args=p.parse_args();(prepare if args.mode=='prepare' else run)(args)

if __name__=='__main__':main()
