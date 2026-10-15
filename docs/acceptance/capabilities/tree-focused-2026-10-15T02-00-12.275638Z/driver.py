from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,os,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded,node_runtime
ensure_guarded()
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
out=ROOT/'docs/acceptance/capabilities'/('tree-focused-'+stamp);out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
work=Path(tempfile.mkdtemp(prefix='tree-focused-',dir=ROOT/'.tools/capabilities'))
env={**os.environ,'PATH':str(Path.home()/'.cargo/bin')+':/usr/bin:/bin','CARGO_TARGET_DIR':str(ROOT/'target'), 'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
env['SDKROOT']=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
commands=[];report={'status':'running','retainedWork':work.relative_to(ROOT).as_posix(),'scope':'Focused real Rust API/CLI emission and standalone TypeScript execution; no installed package claim.','commands':commands,'deleted':[]}
def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(label,args,cwd=work,expected=(0,)):
    r=subprocess.run([str(x) for x in args],cwd=cwd,env=env,capture_output=True)
    item={'label':label,'argv':[str(x) for x in args],'exitCode':r.returncode,'expectedExitCodes':list(expected)}
    for name in ['stdout','stderr']:
        raw=getattr(r,name);p=out/(label+'.'+name+'.log');p.write_bytes(raw)
        item[name]={'path':p.relative_to(ROOT).as_posix(),'digest':sha(raw)}
    commands.append(item);save();print(json.dumps({'check':label,'exitCode':r.returncode}),flush=True)
    assert r.returncode in expected,label
    return r.stdout.decode()
try:
    cargo=Path.home()/'.cargo/bin/cargo'
    run('format',[cargo,'fmt','--all'],ROOT)
    run('consumer-format',[Path.home()/'.cargo/bin/rustfmt','--edition','2024','scripts/capabilities/consumers/typed_tree.rs'],ROOT)
    run('build-cli',[cargo,'build','--locked','--offline','-p','patamaps-cli'],ROOT)
    for name in ['src/bin','typed-fixtures']:(work/name).mkdir(parents=True)
    for name in ['graph','pack','request','policy','projection-spec']:
        (work/'typed-fixtures'/(name+'.json')).write_bytes((ROOT/'fixtures/laws'/(name+'.json')).read_bytes())
    (work/'typed-fixtures/core.json').write_bytes((ROOT/'relation-packs/core.json').read_bytes())
    source=ROOT/'scripts/capabilities/consumers/typed_tree.rs'
    (work/'src/bin/typed_tree.rs').write_bytes(source.read_bytes())
    manifest='[workspace]\n[package]\nname="patamaps-checked-tree-focus"\nversion="0.0.0"\nedition="2024"\n[dependencies]\nserde_json="1"\n'
    for name in ['patamaps-contracts','patamaps-core','patamaps-projection']:
        manifest+=name+'={path='+json.dumps(str(ROOT/'crates'/name))+'}\n'
    (work/'Cargo.toml').write_text(manifest)
    result=json.loads(run('native-emission',[cargo,'run','--offline','--quiet','--bin','typed_tree']))
    inputs=result['acceptedCapture']['inputs']
    for name,value in [('graph',inputs['graph']),('policy',inputs['policy']),('spec',inputs['projectionSpecs'][0]),('pack',inputs['packs'][0]),('context',inputs['context'])]:
        (work/(name+'.json')).write_text(json.dumps(value)+'\n')
    cli=ROOT/'target/debug/patamaps'
    actual=run('cli-emission',[cli,'path-tree','graph.json','policy.json','spec.json','--relation-pack','pack.json','--context','context.json','--as-of',inputs['evaluatedAt'],'--format','typescript','--export','nativeTree'])
    assert actual==(work/'native_tree.mts').read_text()
    text=(ROOT/'scripts/capabilities/install.py').read_text()
    values={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(text).body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id.startswith('TYPED_TREE_')}
    (work/'typed_runtime.mts').write_text(values['TYPED_TREE_RUNTIME'].replace('@@NATIVE_UNICODE_PATH@@',json.dumps(result['unicodePath'])))
    (work/'typed_invalid.mts').write_text(values['TYPED_TREE_INVALID'])
    tsc=Path(os.environ['PATAMAPS_REFERENCE'])/'node_modules/typescript/lib/tsc.js'
    base=[node_runtime(),tsc,'--strict','--target','ES2022','--module','NodeNext','--moduleResolution','NodeNext']
    run('typescript-build',base+['--outDir','dist','typed_runtime.mts'])
    runtime=json.loads(run('typescript-runtime',[node_runtime(),work/'dist/typed_runtime.mjs']))
    refused=run('false-literal-refusal',base+['--noEmit','typed_invalid.mts'],expected=(1,2))
    assert 'TS2322' in refused and 'not assignable' in refused
    report.update(status='passed',typescriptRuntime=runtime,consumerDigest=sha(source.read_bytes()),acceptanceDriverDigest=sha(text.encode()))
except BaseException as e:
    report.update(status='failed',error=type(e).__name__+': '+str(e));raise
finally:
    save();print(json.dumps({'status':report['status'],'receipt':str(out/'receipt.json')}),flush=True)
