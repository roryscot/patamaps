from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
ROOT=Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014')
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('scientific-alignment-focused-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
commands=[]
report={'status':'running','commands':commands,'baseRevision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'scope':'Native scientific source-alignment controls and Rust lint/format/source integrity. Newly strengthened Linux-only precommit assertions are not executed on macOS.','deleted':[]}
def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
env['SDKROOT']=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
cargo=str(Path.home()/'.cargo/bin/cargo')
def run(label,argv):
    started=time.monotonic();result=subprocess.run([str(x) for x in argv],cwd=ROOT,env=env,capture_output=True)
    item={'label':label,'argv':[str(x) for x in argv],'exitCode':result.returncode,'elapsedSeconds':time.monotonic()-started}
    for stream in ['stdout','stderr']:
        p=out/(label+'.'+stream+'.log');p.write_bytes(getattr(result,stream));item[stream]={'path':p.relative_to(ROOT).as_posix(),'digest':sha(p)}
    commands.append(item);save();print(json.dumps({'check':label,'exitCode':result.returncode}),flush=True)
    assert result.returncode==0,label+': inspect retained logs'
try:
    run('format',[cargo,'fmt','--all'])
    files=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'crates').rglob('*.rs')),*sorted((ROOT/'crates').rglob('Cargo.toml'))]
    inventory=[{'path':p.relative_to(ROOT).as_posix(),'digest':sha(p)} for p in files]
    report.update(sourceInventory=inventory,engines=identities(ROOT));save()
    run('scientific-crate-tests',[cargo,'test','--locked','--offline','-p','patamaps-scientific','--test','crate'])
    run('scientific-clippy',[cargo,'clippy','--locked','--offline','-p','patamaps-scientific','--all-targets','--','-D','warnings'])
    run('source-integrity',[sys.executable,'-B',ROOT/'scripts/test_source_integrity.py',ROOT/'.tools/reference/metamap-399747a4ad05','--output',out/'reference-integrity.json'])
    for x in inventory:assert sha(ROOT/x['path'])==x['digest'],x['path']
    report.update(status='passed',sourceUnchanged=True,completedAtUtc=datetime.now(timezone.utc).isoformat())
except BaseException as error:
    report.update(status='failed',error=type(error).__name__+': '+str(error));raise
finally:
    save();print(json.dumps({'status':report['status'],'receipt':str(out.relative_to(ROOT))+'/receipt.json'}),flush=True)
