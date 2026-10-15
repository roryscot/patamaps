from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
ROOT=Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return 'sha256:'+h.hexdigest()
compiler=ROOT/'docs/acceptance/capabilities/compiler-2026-10-15T02-01-50.627814Z/receipt.json'
installed=max((ROOT/'docs/acceptance/capabilities').glob('installed-resume-*/receipt.json'),key=lambda p:p.stat().st_mtime)
c=json.loads(compiler.read_bytes());i=json.loads(installed.read_bytes())
assert c['status']==i['status']=='passed'
assert c['engines']==i['engines']
for entry in c['sourceInventory']:assert sha(ROOT/entry['path'])==entry['digest'],entry['path']
work=ROOT/i['retainedWork'];source,=(work/'source').iterdir()
inventory=json.loads((source/'source-inventory.json').read_bytes())
assert sha(source/'source-inventory.json')==i['distribution']['sourceInventoryDigest']
roots=('crates/','vendor/','fixtures/','relation-packs/','schemas/','scripts/','sdk/','adapters/','examples/')
fixed={'Cargo.toml','Cargo.lock','rust-toolchain.toml','.cargo/config.toml'}
def selected(name):return name in fixed or name.startswith(roots)
bound=[entry for entry in inventory if selected(entry['path'])]
for entry in bound:
    assert sha(ROOT/entry['path'])==entry['digest'],entry['path']
    assert (ROOT/entry['path']).stat().st_size==entry['bytes']
listed=subprocess.check_output(['git','-C',ROOT,'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
current={p for p in listed if p and selected(p) and (ROOT/p).is_file()}
assert current=={entry['path'] for entry in bound}, sorted(current.symmetric_difference({entry['path'] for entry in bound}))[:20]
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
out=ROOT/'docs/acceptance/capabilities'/('intel-tree-checkpoint-'+stamp);out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
pointer=ROOT/'.tools/capabilities/current.json'
saved=pointer.with_name('current.before-checked-tree-'+stamp+'.json')
with saved.open('xb') as f:f.write(pointer.read_bytes())
report={'status':'compiler-and-installed-intel-verified','recordedAtUtc':datetime.now(timezone.utc).isoformat(),
 'baseCommit':subprocess.check_output(['git','-C',ROOT,'rev-parse','HEAD'],text=True).strip(),
 'workingSource':'Uncommitted checked-tree TypeScript emitter, CLI and installed typed consumers; exact current implementation inputs match the retained package.',
 'compilerReceipt':compiler.relative_to(ROOT).as_posix(),'compilerReceiptDigest':sha(compiler),
 'installedReceipt':installed.relative_to(ROOT).as_posix(),'installedReceiptDigest':sha(installed),
 'engines':i['engines'],'matchedCompilerInputs':len(c['sourceInventory']),'matchedInstalledInputs':bound,
 'nativeArchiveScope':'Archive digest and package binary/source bindings checked; independent installed Rust compilation is recorded separately. No independent binary rebuild determinism claim.',
 'phasedInstallation':{'packagePreparation':i['resumedFrom'],'packagePreparationDigest':i['resumedFromDigest'],'allOriginalConsumerAssertionsRetained':True,'supervisorGrowthBytesPerRun':2000000000},
 'commandLocalDeveloperDirectory':'/Library/Developer/CommandLineTools','agentChangedGlobalDeveloperSelection':False,'agentAcceptedXcodeTerms':False,
 'previousPointer':saved.relative_to(ROOT).as_posix(),'productionActivation':'not-requested','registryPublication':'not-requested','requiredLinuxAcceptance':'pending for this changed production source','goalComplete':False,'deleted':[]}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
pointer.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'checkpoint':str(out/'receipt.json'),'compiler':str(compiler),'installed':str(installed),'matchedInstalledInputs':len(bound)}))
