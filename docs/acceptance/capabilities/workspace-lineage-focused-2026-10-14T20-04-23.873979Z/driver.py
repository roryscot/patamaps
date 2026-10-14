import hashlib, json, os, platform, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
cargo=Path('/Users/admin/.cargo/bin/cargo')
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk'}
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
out=ROOT/'docs/acceptance/capabilities'/('workspace-lineage-focused-'+stamp)
out.mkdir(exist_ok=False)
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
commands=[]
report={'status':'running','commands':commands,'deleted':[],'host':platform.platform(),'sourceRevision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workingTree':'workspace lineage changes','scope':'Formatting, native workspace lineage/process/retention controls, private checked type, CLI build, and Clippy. Installed and Linux refresh remains separate.'}
receipt=out/'receipt.json'
def save():receipt.write_text(json.dumps(report,indent=2)+'\n')
def run(label,args):
 with (out/(label+'.stdout.log')).open('wb') as stdout,(out/(label+'.stderr.log')).open('wb') as stderr:
  r=subprocess.run([str(cargo),*args],cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
 commands.append({'label':label,'argv':[str(cargo),*args],'exitCode':r.returncode})
 save();print(json.dumps({'check':label,'exitCode':r.returncode}),flush=True)
 if r.returncode:raise RuntimeError(label+' failed; retained logs at '+str(out))
def inventory():
 return [{'path':str(p.relative_to(ROOT)),'digest':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'crates').rglob('*')) if p.is_file()]
save()
try:
 run('format',['fmt','--all'])
 report['sourceInventory']=inventory();save()
 run('workspace-tests',['test','--locked','--offline','-p','patamaps-workspace','--','--test-threads=1'])
 run('build-cli',['build','--locked','--offline','-p','patamaps-cli'])
 run('clippy',['clippy','--workspace','--all-targets','--locked','--offline','--','-D','warnings'])
 assert inventory()==report['sourceInventory'],'Source changed during verification'
 report.update(status='passed',sourceUnchanged=True,completedAtUtc=datetime.now(timezone.utc).isoformat())
except BaseException as e:
 report.update(status='failed',error=type(e).__name__+': '+str(e));raise
finally:
 save();print(json.dumps({'status':report['status'],'receipt':str(receipt.relative_to(ROOT))}),flush=True)
