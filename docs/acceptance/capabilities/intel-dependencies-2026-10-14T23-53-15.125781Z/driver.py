import argparse,hashlib,json,os,platform,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--cwd',type=Path,default=ROOT);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();args=a.command[1:] if a.command[:1]==['--'] else a.command;assert args
assert platform.machine()=='x86_64'
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('intel-'+a.label+'-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir();(out/'driver.py').write_bytes(Path(__file__).read_bytes())
env={**os.environ,'PATH':str(Path.home()/'.cargo/bin')+':'+str(Path.home()/'.nvm/versions/node/v22.23.3/bin')+':/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','PATAMAPS_PARITY_NODE':str(Path.home()/'.nvm/versions/node/v22.23.3/bin/node'),'PYTHONDONTWRITEBYTECODE':'1','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
report={'status':'running','host':{'architecture':platform.machine(),'platform':platform.platform()},'argv':args,'cwd':str(a.cwd),'sourceRevision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'deleted':[]};receipt=out/'receipt.json'
def save():receipt.write_text(json.dumps(report,indent=2)+'\n')
save()
try:
 with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:result=subprocess.run(args,cwd=a.cwd,env=env,stdout=stdout,stderr=stderr)
 report.update(status='passed' if result.returncode==0 else 'failed',exitCode=result.returncode,logs={name:{'path':str(out/name),'digest':'sha256:'+hashlib.sha256((out/name).read_bytes()).hexdigest()} for name in ['stdout.log','stderr.log']},completedAtUtc=datetime.now(timezone.utc).isoformat());save();assert result.returncode==0,args
finally:save();print(json.dumps({'status':report['status'],'receipt':str(receipt)}),flush=True)
