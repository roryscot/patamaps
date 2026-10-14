import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
out=root/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('reporting-focused-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir();(out/'driver.py').write_bytes(Path(__file__).read_bytes())
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk'}
cargo='/Users/admin/.cargo/bin/cargo';r={'status':'running','commands':[],'deleted':[]};receipt=out/'receipt.json'
def save():receipt.write_text(json.dumps(r,indent=2)+'\n')
save()
try:
 for label,args in [('format',['fmt','--all']),('workspace-inspection',['test','--locked','--offline','-p','patamaps-workspace','-p','patamaps-inspect','--','--test-threads=1']),('build-cli',['build','--locked','--offline','-p','patamaps-cli']),('clippy',['clippy','--workspace','--all-targets','--locked','--offline','--','-D','warnings'])]:
  with (out/(label+'.stdout.log')).open('wb') as stdout,(out/(label+'.stderr.log')).open('wb') as stderr:
   result=subprocess.run([cargo,*args],cwd=root,env=env,stdout=stdout,stderr=stderr)
  r['commands'].append({'label':label,'argv':[cargo,*args],'exitCode':result.returncode});save();print(json.dumps({'check':label,'exitCode':result.returncode}),flush=True)
  if result.returncode:raise RuntimeError(label+' failed: '+str(out))
 r['status']='passed'
except BaseException as e:r.update(status='failed',error=str(e));raise
finally:save();print(json.dumps({'status':r['status'],'receipt':str(receipt.relative_to(root))}),flush=True)
