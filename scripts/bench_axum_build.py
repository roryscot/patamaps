"""Trusted qualification command: real Axum libraries/tests and an observable edit."""
import argparse,hashlib,json,os,re,shutil,stat,subprocess,sys,time
from pathlib import Path
from project_watch import stop

PHASES=('cold','edit-1','edit-2','edit-3')
LIBRARIES=('libaxum.rlib','libaxum_core.rlib','libaxum_extra.rlib','libaxum_macros.dylib')
MAX_LOG=16*1024**2

def sha(path):
 with Path(path).open('rb') as source:return 'sha256:'+hashlib.file_digest(source,'sha256').hexdigest()

def write(path,value):
 with Path(path).open('x') as target:json.dump(value,target,indent=2);target.write('\n')

def probe_suffix(value):
 assert value in PHASES,'MEASUREMENT_PHASE'
 return '\n#[doc(hidden)]\npub const PATAMAPS_MEASURED_EDIT: &str = '+json.dumps(value)+';\n'

def test_summaries(text):
 rows=[dict(passed=int(p),failed=int(f),ignored=int(i)) for p,f,i in re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored',text)]
 assert len(rows)==4 and sorted(r['passed'] for r in rows)==[5,15,16,423] and all(r['failed']==r['ignored']==0 for r in rows) and 'test result: FAILED' not in text,'MEASURED_UPSTREAM_TESTS'
 return rows

def artifact_rows(bundle):
 result={}
 for name in [*LIBRARIES,'consumer']:
  path=bundle/name;s=path.lstat()
  assert stat.S_ISREG(s.st_mode) and s.st_size>0,'MEASURED_BUNDLE_FILE'
  result[name]=dict(digest=sha(path),bytes=s.st_size,mode=stat.S_IMODE(s.st_mode))
 return result

def validate_bundle(bundle,config):
 lineage=json.loads((bundle/'lineage.json').read_bytes())
 assert set(p.name for p in bundle.iterdir())=={*LIBRARIES,'consumer','lineage.json'},'MEASURED_BUNDLE_MEMBERS'
 assert lineage['profile']=='patamaps-axum-measured-bundle-1' and lineage['phase']==config['phase'],'MEASURED_BUNDLE_PHASE'
 assert artifact_rows(bundle)==lineage['artifacts'],'MEASURED_BUNDLE_CHANGED'
 assert lineage['sourceLibDigest']==sha(Path('axum/src/lib.rs')),'MEASURED_SOURCE_CHANGED'
 return lineage

def validate_config(config):
 assert set(config)=={'profile','phase','cargo','cargoDigest','rustc','rustcDigest','target','workRoot','platform'},'MEASUREMENT_CONFIG_KEYS'
 assert config['profile']=='patamaps-axum-measurement-build-1' and config['phase'] in PHASES,'MEASUREMENT_CONFIG'
 assert config['platform']=='x86_64-apple-darwin','MEASUREMENT_PLATFORM'
 assert Path(config['target']).is_absolute() and Path(config['target']).parent==Path(config['workRoot']) and Path(config['target']).name=='cargo-target','MEASUREMENT_TARGET'
 for name in ['cargo','rustc']:
  assert Path(config[name]).is_absolute() and re.fullmatch('sha256:[0-9a-f]{64}',config[name+'Digest']),'MEASUREMENT_TOOL'
  assert sha(config[name])==config[name+'Digest'],'MEASUREMENT_TOOL_CHANGED'
 assert os.environ.get('CARGO_TARGET_DIR')==config['target'],'MEASUREMENT_TARGET_ENVIRONMENT'
 expected=dict(CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='2',CARGO_PROFILE_DEV_DEBUG='0',CARGO_PROFILE_TEST_DEBUG='0',CARGO_INCREMENTAL='0',RUST_TEST_THREADS='1')
 assert all(os.environ.get(k)==v for k,v in expected.items()),'MEASUREMENT_FROZEN_CARGO_ENVIRONMENT'
 assert Path('axum/src/lib.rs').read_text().endswith(probe_suffix(config['phase'])),'MEASUREMENT_SOURCE_OVERLAY'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
 config=json.loads(args.config.read_bytes());validate_config(config)
 bundle=Path('bundle');private=Path('.measurement-private')
 private.mkdir(mode=0o700,exist_ok=args.verify)
 assert private.is_dir() and not private.is_symlink(),'MEASURED_PRIVATE_LOG_DIRECTORY'
 def run(label,argv):
  began=time.monotonic()
  with (private/(label+'.stdout')).open('xb') as stdout,(private/(label+'.stderr')).open('xb') as stderr:
   child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('project_watch.py')),'__guard',*map(str,argv)],stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
   try:
    while child.poll() is None:
     assert time.monotonic()-began<900,'MEASURED_CHILD_DEADLINE'
     assert max(os.fstat(stdout.fileno()).st_size,os.fstat(stderr.fileno()).st_size)<=MAX_LOG,'MEASURED_CHILD_LOG_BOUND'
     time.sleep(.05)
    assert child.returncode==0,'MEASURED_CHILD_FAILED'
   finally:stop(child)
  assert max((private/(label+'.stdout')).stat().st_size,(private/(label+'.stderr')).stat().st_size)<=MAX_LOG,'MEASURED_CHILD_LOG_BOUND'
  return (private/(label+'.stdout')).read_text()
 common=['--workspace','--lib','--locked','--offline','--features','axum/ws','--target',config['platform']]
 if args.verify:
  before=validate_bundle(bundle,config)
  rows=test_summaries(run('upstream-tests',[config['cargo'],'test',*common]))
  observed=run('verified-consumer',[bundle.resolve()/'consumer']).strip();assert observed==config['phase'],'MEASURED_CONSUMER_VALUE'
  assert validate_bundle(bundle,config)==before,'MEASURED_VERIFICATION_CHANGED_BUNDLE'
  write(private/'verification.json',dict(status='passed-measured-axum-verification',tests=rows,consumerValue=observed,bundleUnchanged=True))
  result=dict(status='verified-measured-axum-build',testSummaries=rows,upstreamTestsPassed=459,consumerValue=observed,bundleUnchanged=True)
 else:
  bundle.mkdir()
  run('upstream-build',[config['cargo'],'build',*common])
  target=Path(config['target'])/config['platform']/'debug'
  for name in LIBRARIES:
   source=target/name;assert source.is_file() and not source.is_symlink(),'MEASURED_LIBRARY_OUTPUT'
   shutil.copy2(source,bundle/name)
  run('consumer-compile',[config['rustc'],'--edition','2021',str(Path(__file__).with_name('measurement-consumer.rs')),'--extern','axum='+str((bundle/'libaxum.rlib').resolve()),'-L','dependency='+str(target/'deps'),'-o',str((bundle/'consumer').resolve())])
  observed=run('built-consumer',[bundle.resolve()/'consumer']).strip();assert observed==config['phase'],'MEASURED_CONSUMER_VALUE'
  write(bundle/'lineage.json',dict(profile='patamaps-axum-measured-bundle-1',phase=config['phase'],sourceLibDigest=sha('axum/src/lib.rs'),tools={name:config[name+'Digest'] for name in ['cargo','rustc']},artifacts=artifact_rows(bundle)))
  result=dict(status='built-measured-axum-libraries',consumerValue=observed,selectedLibraryFiles=4)
 validate_config(config)
 print(json.dumps(result))

if __name__=='__main__':main()
