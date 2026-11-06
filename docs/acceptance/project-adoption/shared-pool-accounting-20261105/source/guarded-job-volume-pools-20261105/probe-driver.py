from pathlib import Path
import os,json,subprocess,sys,signal
B=Path(__file__).resolve().parent
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
sys.path.insert(0,str(R/'scripts'));import native_inspection_guard as kernel
identity=kernel.process_identity(os.getpid())
assert identity and identity['parentPid']==int(os.environ['WARGAME_STORAGE_OWNER_PID'])==os.getppid()
with(B/'driver-identity.json').open('x')as f:json.dump(identity,f)
p=subprocess.Popen(['/Users/admin/.nvm/versions/node/v22.23.3/bin/node',str(B/'probe.mjs')])
try:code=p.wait(timeout=180)
except BaseException:
 if p.poll()is None:p.terminate()
 try:p.wait(timeout=6)
 except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
 raise
raise SystemExit(code if code>=0 else 128-code)
