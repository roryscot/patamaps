import hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014')
sys.path.insert(0, str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
out = ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('scientific-partial-source-external-probe-%Y-%m-%dT%H-%M-%S.%fZ')
out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
source = ROOT/'.tools/intel-bootstrap/scientific-partial-source-probe-v2-20261015.rs'
(out/'probe.rs').write_bytes(source.read_bytes())
work = Path(tempfile.mkdtemp(prefix='scientific-partial-probe-', dir=ROOT/'.tools/capabilities'))
(work/'src').mkdir()
(work/'src/main.rs').write_bytes(source.read_bytes())
manifest = '[workspace]\n[package]\nname="scientific-partial-source-probe"\nversion="0.0.0"\nedition="2024"\n[dependencies]\nserde="1"\nserde_json="1"\n'
for name in ['contracts','core','projection','scientific']:
    manifest += 'patamaps-'+name+'={path='+json.dumps(str(ROOT/'crates'/('patamaps-'+name)))+'}\n'
(work/'Cargo.toml').write_text(manifest)
(work/'Cargo.lock').write_bytes((ROOT/'Cargo.lock').read_bytes())
paths = [ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'crates').rglob('*.rs')),*sorted((ROOT/'crates').rglob('Cargo.toml'))]
inventory = [{'path':p.relative_to(ROOT).as_posix(),'digest':sha(p)} for p in paths]
fixture = ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv'
argv = [str(Path.home()/'.cargo/bin/cargo'),'run','--offline','--quiet','--manifest-path',str(work/'Cargo.toml'),'--',str(fixture)]
report = {'status':'running','sourceRevision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'engines':identities(ROOT),'sourceInventory':inventory,'fixture':{'path':fixture.relative_to(ROOT).as_posix(),'digest':sha(fixture)},'retainedWork':work.relative_to(ROOT).as_posix(),'argv':argv,'scope':'Synthetic raw-document row changes with genuine retained TSV bytes. Checks source alignment, not scientific truth or authentication. No production activation.','deleted':[]}
def save(): (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
save()
try:
    env = {**os.environ,'CARGO_TARGET_DIR':str(ROOT/'target'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
    env['SDKROOT'] = subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
    result = subprocess.run(argv,cwd=work,env=env,capture_output=True)
    report['exitCode'] = result.returncode
    for stream in ['stdout','stderr']:
        p=out/(stream+'.log');p.write_bytes(getattr(result,stream));report[stream]={'path':p.relative_to(ROOT).as_posix(),'digest':sha(p)}
    assert result.returncode==0,'inspect retained logs'
    observations = json.loads(result.stdout)
    cases = observations['cases']
    assert len(cases)==3
    assert cases[0]['accepted'] and cases[0]['verificationAccepted'], 'Genuine partial positive control failed'
    assert not cases[1]['accepted'], 'Altered complete negative control failed'
    hypothesis = cases[2]['accepted'] and cases[2]['verificationAccepted']
    forged = work/'altered-partial.crate.json'
    if forged.exists(): (out/forged.name).write_bytes(forged.read_bytes())
    for item in inventory: assert sha(ROOT/item['path'])==item['digest'],item['path']
    report.update(status='controls-passed',observations=observations,partialPayloadAlignmentBypassObserved=hypothesis,sourceUnchanged=True,completedAtUtc=datetime.now(timezone.utc).isoformat())
except BaseException as error:
    report.update(status='failed',error=type(error).__name__+': '+str(error));raise
finally:
    save();print(json.dumps({'status':report['status'],'receipt':str(out.relative_to(ROOT))+'/receipt.json','partialPayloadAlignmentBypassObserved':report.get('partialPayloadAlignmentBypassObserved')}),flush=True)
