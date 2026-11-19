"""Closed staged native inspection entrypoint; no caller code or profiles."""
from pathlib import Path
import hashlib,json,os,select,stat,subprocess,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(HERE))

def need(value,message):
 if not value:raise ValueError(message)
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  while chunk:=stream.read(1048576):h.update(chunk)
 return h.hexdigest()
def pairs(rows):
 value={}
 for key,item in rows:
  need(key not in value,'Duplicate JSON key');value[key]=item
 return value
def read(path):return json.loads(Path(path).read_text(),object_pairs_hook=pairs)
def canonical(value,directory=False):
 need(isinstance(value,str) and Path(value).is_absolute(),'Absolute path required')
 p=Path(value);need(p.resolve(strict=True)==p,'Canonical path required')
 need(p.is_dir() if directory else p.is_file(),'Wrong path type')
 return str(p)
def main():
 import native_inspection_guard as live
 if len(sys.argv)==3 and sys.argv[1]=='--probe':
  ids=json.loads(sys.argv[2])
  need(isinstance(ids,list) and 0<len(ids)<=64 and len(set(ids))==len(ids) and all(type(x)is int and x>1 for x in ids),'Probe shape')
  print(json.dumps(dict(identities={str(x):live.process_identity(x) for x in ids},
   groupsStopped={str(x):not live.group_live(x) for x in ids})))
  return 0
 if len(sys.argv)==3 and sys.argv[1]=='--stop':
  identities=json.loads(sys.argv[2])
  need(isinstance(identities,list) and 0<len(identities)<=49,'Stop shape')
  for identity in identities:
   need(isinstance(identity,dict) and set(identity)=={'pid','parentPid','pgid','startSeconds','startMicroseconds'} and
    all(type(x)is int for x in identity.values()) and identity['pid']>1 and identity['pid']==identity['pgid'],'Stop identity')
  outcomes=[live.stop_registered(identity,.2) for identity in identities]
  value=dict(confirmed=all(outcomes))
  print(json.dumps(value));return 0 if value['confirmed'] else 75
 need(len(sys.argv)==5 and sys.argv[1]=='--invocation' and sys.argv[3]=='--sha','Closed invocation required')
 invocation_path=Path(canonical(sys.argv[2]));need(digest(invocation_path)==sys.argv[4],'Invocation changed')
 invocation=read(invocation_path)
 need(isinstance(invocation,dict) and set(invocation)=={'version','operation','runRoot','inputs','expectedParent','manifestSha256'},'Invocation shape')
 need(invocation['version']==1 and type(invocation['expectedParent'])is int and os.getppid()==invocation['expectedParent'],'Controller parent changed')
 need(digest(ROOT/'registration.json')==invocation['manifestSha256'],'Registration changed')
 manifest=read(ROOT/'registration.json')
 need(manifest['kind']=='patamaps-staged-native-registration-v1','Registration kind')
 need(digest(HERE/'native_registered_controller.py')==manifest['controllerSha256'],'Controller changed')
 run=Path(canonical(invocation['runRoot'],True))
 need(invocation_path.parent==run and stat.S_IMODE(run.stat().st_mode)==0o700 and run.stat().st_uid==os.getuid(),'Private invocation root required')
 need(ROOT not in run.parents and run not in ROOT.parents and run!=ROOT,'Writable alias of registration')
 inputs=invocation['inputs'];operation=invocation['operation']
 need(isinstance(inputs,dict),'Input shape')
 native=ROOT/'native/patamaps';need(digest(native)==manifest['nativeSha256'],'Native changed')
 if operation=='engine':
  need(inputs=={},'Engine input shape');args=['engine'];lock=None
 else:
  required={'plan','source','context','preparation'}|({'state'} if operation=='unchanged-build' else set())
  need(operation in ['input-key','unchanged-build'] and set(inputs)==required,'Operation/input shape')
  for key,value in inputs.items():canonical(value,key in ['source','state'])
  args=['project-build-input-key' if operation=='input-key' else 'project-build',inputs['plan'],'--source',inputs['source'],'--context',inputs['context'],'--preparation',inputs['preparation']]
  lock=None
  if operation=='unchanged-build':
   args+=['--state',inputs['state']];lock=Path(inputs['state'])/'driver.lock'
 # Private acknowledgement prevents a fast controller exit before its actual
 # kernel identity and private receiver have been bound by the supervisor.
 for fd in [3,4]:os.set_inheritable(fd,False)
 need(bool(select.select([4],[],[],30)[0]) and os.read(4,2)==b'1','Supervisor acknowledgement missing')
 os.close(4)
 need(os.getppid()==invocation['expectedParent'],'Supervisor died before launch')
 jobs=run/'jobs';jobs.mkdir(mode=0o700)
 runner=live.InspectionRunner(jobs,run,strict=True,driver_lock=lock,lifecycle_fd=3,stop_grace=.5)
 result=runner([str(native),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900 if operation=='unchanged-build' else 60,check=False)
 need(digest(invocation_path)==sys.argv[4] and digest(ROOT/'registration.json')==invocation['manifestSha256'],'Invocation/binding changed after stop')
 sys.stdout.buffer.write(result.stdout);sys.stdout.buffer.flush()
 sys.stderr.buffer.write(result.stderr);sys.stderr.buffer.flush()
 os.close(3)
 return result.returncode
if __name__=='__main__':
 try:code=main()
 except BaseException as error:
  print(type(error).__name__+': '+str(error),file=sys.stderr);code=75
 sys.exit(code)
