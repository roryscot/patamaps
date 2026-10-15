import hashlib,json,os,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
assert subprocess.check_output(['uname','-m'],text=True).strip()=='x86_64'
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('intel-rustup-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
work=ROOT/'.tools/intel-bootstrap'/out.name;work.mkdir()
report={'status':'running','host':'x86_64-apple-darwin','commands':[],'deleted':[],'shellProfilesModified':False};receipt=out/'receipt.json'
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
def save():receipt.write_text(json.dumps(report,indent=2)+'\n')
def run(label,args):
 with (out/(label+'.stdout.log')).open('wb') as stdout,(out/(label+'.stderr.log')).open('wb') as stderr:
  result=subprocess.run([str(v) for v in args],cwd=ROOT,stdout=stdout,stderr=stderr)
 report['commands'].append({'label':label,'argv':[str(v) for v in args],'exitCode':result.returncode});save();print(json.dumps({'step':label,'exitCode':result.returncode}),flush=True)
 assert result.returncode==0,label
save()
try:
 url='https://static.rust-lang.org/rustup/dist/x86_64-apple-darwin/rustup-init'
 binary=work/'rustup-init';checksum=work/'rustup-init.sha256'
 run('installer-download',['/usr/bin/curl','--fail','--location','--proto','=https','--tlsv1.2','--output',binary,url])
 run('checksum-download',['/usr/bin/curl','--fail','--location','--proto','=https','--tlsv1.2','--output',checksum,url+'.sha256'])
 expected=checksum.read_text().split()[0];assert re.fullmatch('[0-9a-f]{64}',expected)
 actual=hashlib.sha256(binary.read_bytes()).hexdigest();assert actual==expected
 binary.chmod(0o755)
 assert not (Path.home()/'.cargo/bin/rustup').exists()
 report.update(installerUrl=url,installerDigest='sha256:'+actual);save()
 run('rustup-install',[binary,'-y','--no-modify-path','--default-toolchain','none','--profile','minimal'])
 run('installed-rustup-version',[Path.home()/'.cargo/bin/rustup','--version'])
 report.update(status='passed',completedAtUtc=datetime.now(timezone.utc).isoformat())
except BaseException as error:report.update(status='failed',error=str(error));raise
finally:save();print(json.dumps({'status':report['status'],'receipt':str(receipt)}),flush=True)
