from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return 'sha256:'+h.hexdigest()
pointer=json.loads((ROOT/'.tools/capabilities/current.json').read_text())
installed=ROOT/pointer['installedReceipt'];assert sha(installed)==pointer['installedReceiptDigest']
record=json.loads(installed.read_bytes());assert record['status']=='passed'
work=ROOT/record['retainedWork'];source,=(work/'source').iterdir()
inventory=json.loads((source/'source-inventory.json').read_bytes())
assert sha(source/'source-inventory.json')==record['distribution']['sourceInventoryDigest']
for item in inventory:assert sha(source/item['path'])==item['digest'],item['path']
destination=work/'installation-release';assert destination.is_dir();assert not (destination/'bin/patamaps').exists()
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('installed-release-resume-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
env={**os.environ,'CARGO_TARGET_DIR':str(ROOT/'target/package-test'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_RELEASE_DEBUG':'0'}
env['SDKROOT']=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
argv=[str(Path.home()/'.cargo/bin/cargo'),'install','--path',str(source/'crates/patamaps-cli'),'--locked','--offline','--root',str(destination)]
report={'status':'running','scope':'Optimized CLI independently installed from the same fully inventoried source package as the passed development installation. No registry publication or production activation.','sourceInstallation':installed.relative_to(ROOT).as_posix(),'sourceInstallationDigest':sha(installed),'sourceInventoryDigest':record['distribution']['sourceInventoryDigest'],'source':source.relative_to(ROOT).as_posix(),'binary':(destination/'bin/patamaps').relative_to(ROOT).as_posix(),'buildProfile':'release','resumedFrom':'docs/acceptance/capabilities/installed-release-2026-10-15T03-40-32.572563Z/receipt.json','originalDriverDigest':'sha256:28a2c63b87cf3c5143176df62e7375bd586c9cbf5f76b413da609ca3ef7beaa2','sdk':env['SDKROOT'],'developerDirectory':env.get('DEVELOPER_DIR'),'argv':argv,'deleted':[]}
def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
save()
try:
    with (out/'install.stdout.log').open('wb') as stdout,(out/'install.stderr.log').open('wb') as stderr:
        result=subprocess.run(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
    report['exitCode']=result.returncode
    assert result.returncode==0,'inspect retained release installation logs'
    cli=destination/'bin/patamaps';raw=subprocess.check_output([cli,'engine'],env={'PATH':'/usr/bin:/bin'})
    (out/'engine.json').write_bytes(raw);assert json.loads(raw)==record['engines']
    for item in inventory:assert sha(source/item['path'])==item['digest'],item['path']
    report.update(status='passed',engines=record['engines'],binaryDigest=sha(cli),sourceUnchanged=True,completedAtUtc=datetime.now(timezone.utc).isoformat())
except BaseException as e:
    report.update(status='failed',error=type(e).__name__+': '+str(e));raise
finally:
    report['logs']={name:sha(out/name) for name in ['install.stdout.log','install.stderr.log'] if (out/name).exists()}
    save();print(json.dumps({'status':report['status'],'receipt':str(out/'receipt.json')}),flush=True)
