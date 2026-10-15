from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
original=ROOT/'docs/acceptance/capabilities/compiler-2026-10-15T02-01-50.627814Z/lifecycle.json'
data=json.loads(original.read_bytes())
saved=next(Path(c['argv'][2]) for c in data['commands'] if len(c['argv'])>2 and c['argv'][1]=='replay')
assert saved.resolve().is_relative_to(ROOT/'.tools/capabilities')
raw=saved.read_bytes();embedded=json.dumps(data['capture'],indent=2).encode()+b'\n'
assert json.loads(raw)!=data['capture']
pointer=json.loads((ROOT/'.tools/capabilities/current.json').read_bytes())
installed=ROOT/pointer['installedReceipt'];record=json.loads(installed.read_bytes())
assert record['status']=='passed' and sha(installed.read_bytes())==pointer['installedReceiptDigest']
cli=ROOT/record['retainedWork']/'installation/bin/patamaps'
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('lifecycle-report-integrity-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
commands=[]
for label,payload,expected in [('preserved-original',raw,0),('mutated-inline',embedded,1)]:
    source=out/(label+'.capture.json');source.write_bytes(payload)
    argv=[str(cli),'replay',str(source)];r=subprocess.run(argv,capture_output=True)
    item={'label':label,'argv':argv,'exitCode':r.returncode,'expectedExitCode':expected}
    for stream in ['stdout','stderr']:
        p=out/(label+'.'+stream+'.log');p.write_bytes(getattr(r,stream))
        item[stream]={'path':p.relative_to(ROOT).as_posix(),'digest':sha(p.read_bytes())}
    commands.append(item)
    assert r.returncode==expected,item
assert saved.read_bytes()==raw
report={'status':'confirmed-reporting-defect-original-preserved','recordedAtUtc':datetime.now(timezone.utc).isoformat(),
 'sourceReport':{'path':original.relative_to(ROOT).as_posix(),'digest':sha(original.read_bytes())},
 'savedOriginal':{'path':saved.relative_to(ROOT).as_posix(),'digest':sha(raw),'replay':'verified'},
 'inlineCapture':'refused by native replay; its input policy was mutated by the Python test fixture after the valid saved capture was replayed',
 'requiredFix':{'path':'scripts/test_lifecycle_pure.py','change':'Clone captured inputs before modifying the independent rejected-candidate fixture; assert original saved/embedded capture equality and execute the selected returned repair capture.','status':'not-yet-applied'},
 'commands':commands,'engines':record['engines'],'scope':'Defect in a test report copy, not a demonstrated native replay/admission bypass. Prior raw report and actual command logs remain unchanged.','deleted':[]}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'receipt':str(out/'receipt.json'),'preservedOriginalReplays':True,'inlineCaptureCorrectlyRefused':True}))
