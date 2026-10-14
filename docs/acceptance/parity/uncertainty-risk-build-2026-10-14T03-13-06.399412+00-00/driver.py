from pathlib import Path
import json,os,sys,subprocess
root=Path.cwd();out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
rows=[]
for item in json.loads((out/'config.json').read_text())['commands']:
 print('Starting '+item['label'],flush=True)
 with (out/(item['label']+'.stdout.log')).open('x') as stdout,(out/(item['label']+'.stderr.log')).open('x') as stderr:r=subprocess.run(item['command'],cwd=root,env=env,stdout=stdout,stderr=stderr)
 rows.append({**item,'exitCode':r.returncode});(out/'receipt.json').write_text(json.dumps({'status':'failed' if r.returncode else 'running','commands':rows},indent=2)+'\n');print(item['label']+' '+str(r.returncode),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
(out/'receipt.json').write_text(json.dumps({'status':'passed','commands':rows},indent=2)+'\n')
