"""Narrow consumer-owned build, outside the correspondence compiler.

Explicit module maps bind owned local bytes. Rustc resolves real exports/types.
All files are staged; callers publish only a successful returned candidate. No
trust, approval, protected active pointer or production path is read or written.
"""
import hashlib,json,os,re,shutil,subprocess
from pathlib import Path
class BuildError(Exception):
    def __init__(self,code,details):self.code=code;self.details=details;super().__init__(f'{code}: {details}')
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def call(argv,cwd,env=None):
    r=subprocess.run([str(v) for v in argv],cwd=cwd,env=env,capture_output=True,text=True,timeout=90)
    if r.returncode:
        try:issues=json.loads(r.stdout)['issues']
        except (ValueError,KeyError):raise BuildError('NATIVE_BUILD_FAILED',r.stderr or r.stdout)
        raise BuildError(issues[0]['code'],issues)
    return r.stdout
def build(root,cli,stage,context,generation_override=None):
    root=root.resolve();stage.mkdir();native_env={**os.environ,'PATH':'/usr/bin:/bin','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0'}
    # Read authored control inputs once and stage those exact bytes. These
    # receipts describe this consumer build; they do not attest a complete
    # compiler/toolchain dependency closure or confer deployment authority.
    inputs={name:(root/name).read_bytes() for name in ['sources.json','policy.json','projection.json','Cargo.toml','Cargo.lock','src/main.rs']}
    config=json.loads(inputs['sources.json']);graphs=[];module_files={}
    for source in config['sources']:
        graph_path=(root/source['path']).resolve(strict=True)
        if not graph_path.is_relative_to(root):raise BuildError('NATIVE_LOCATOR_OUTSIDE_OWNER',source['path'])
        raw_graph=graph_path.read_bytes();g=json.loads(raw_graph);graphs.append((source,g));inputs[source['path']]=raw_graph
        owner=(root/source['ownedDirectory']).resolve(strict=True)
        if not owner.is_relative_to(root):raise BuildError('NATIVE_LOCATOR_OUTSIDE_OWNER',source['ownedDirectory'])
        for e in g['entities']:
            rust=[l for l in e.get('locators',[]) if l['uri'].startswith('rust:')]
            if not rust:continue
            if len(rust)!=1:raise BuildError('INVALID_NATIVE_LOCATOR',e['id'])
            match=re.fullmatch(r'rust:crate::([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z_][A-Za-z0-9_]*)',rust[0]['uri'])
            if not match or match[1] not in config['modules']:raise BuildError('INVALID_NATIVE_LOCATOR',rust[0]['uri'])
            path=config['modules'][match[1]];lexical=root/path
            if not re.fullmatch(r'[A-Za-z0-9_./-]+\.rs',path) or Path(path).is_absolute() or any(s in ['','.','..'] for s in path.split('/')) or not lexical.is_relative_to(root/source['ownedDirectory']):raise BuildError('NATIVE_LOCATOR_OUTSIDE_OWNER',path)
            actual=lexical.resolve(strict=True)
            if not actual.is_relative_to(owner):raise BuildError('NATIVE_LOCATOR_OUTSIDE_OWNER',path)
            raw=actual.read_bytes()
            if len(raw)>16777216:raise BuildError('NATIVE_INPUT_LIMIT',path)
            if digest(raw)!=rust[0].get('digest'):raise BuildError('NATIVE_INPUT_DIGEST_MISMATCH',e['id'])
            raw.decode('utf8',errors='strict');inputs[path]=raw;module_files[match[1]]=path
    for source,g in graphs:(stage/(source['id']+'.json')).write_bytes(inputs[source['path']])
    common=['--relation-pack',str(config['routingPack'])]
    graph=json.loads(call([cli,'compose',*[str(stage/(s['id']+'.json')) for s,g in graphs],'--id','urn:bindings:graph','--namespace','bindings',*common],stage,native_env));write(stage/'graph.json',graph)
    policy=json.loads(inputs['policy.json']);policy['graph']={'id':graph['id'],'digest':json.loads(call([cli,'validate','graph.json',*common],stage,native_env))['graph']};write(stage/'policy.json',policy)
    write(stage/'context.json',context);(stage/'spec.json').write_bytes(inputs['projection.json'])
    evaluation=[*common,'--context','context.json','--as-of','2026-10-09T00:00:00.000Z']
    generation=json.loads(call([cli,'compile','graph.json','policy.json',*evaluation],stage,native_env));write(stage/'generation.json',generation_override or generation)
    projection=json.loads(call([cli,'link','graph.json','policy.json','spec.json',*evaluation,'--generation','generation.json'],stage,native_env))
    coverage=[]
    for source,g in graphs:
        used=[]
        for e in g['entities']:
            rule=next((r for r in source.get('coverage',[]) if r['kind']==e['kind']),None)
            if rule is None:continue
            mappings=[m['id'] for m in graph['mappings'] if m['relation']==rule['relation'] and e['id'] in m['targets']]
            exclusions=[x for x in source.get('exclusions',[]) if x['entity']==e['id'] and x['relation']==rule['relation']]
            if len(exclusions)>1:raise BuildError('INVALID_OWNED_EXCLUSION',e['id'])
            if exclusions:
                ex=exclusions[0]
                if mappings or ex['assertedBy']!=source['owner'] or not ex.get('reason','').strip():raise BuildError('INVALID_OWNED_EXCLUSION',e['id'])
                used.append(ex)
            elif not mappings:raise BuildError('UNMAPPED_OWNED_LEAF',e['id'])
            coverage.append({'sourceId':source['id'],'owner':source['owner'],'entityId':e['id'],'relation':rule['relation'],'mappings':mappings,'exclusion':exclusions[0] if exclusions else None})
        if len(used)!=len(source.get('exclusions',[])):raise BuildError('STALE_OWNED_EXCLUSION',source['id'])
    (stage/'Cargo.toml').write_bytes(inputs['Cargo.toml']);(stage/'Cargo.lock').write_bytes(inputs['Cargo.lock']);(stage/'src').mkdir()
    main=inputs['src/main.rs'].decode('utf8')
    # Explicit compiler module declarations follow the same checked module map
    # as locators; changes never require runtime reflective symbol discovery.
    for module,path in module_files.items():
        original=config['originalModules'][module];main=main.replace('../'+original,'../'+path)
    (stage/'src/main.rs').write_text(main)
    for path,raw in inputs.items():
        if path.endswith('.rs') and path!='src/main.rs':(stage/path).parent.mkdir(parents=True,exist_ok=True);(stage/path).write_bytes(raw)
    for slot,name in [('handler','bindings.rs'),('input','schema_bindings.rs')]:
        text=call([cli,'link','graph.json','policy.json','spec.json',*evaluation,'--generation','generation.json','--format','rust','--binding-slot',slot],stage,native_env);(stage/'src'/name).write_text(text)
    cargo=Path.home()/'.cargo/bin/cargo';build_env={**native_env,'CARGO_TARGET_DIR':str(config['targetDirectory'])}
    r=subprocess.run([str(cargo),'build','--locked','--offline','--message-format=json'],cwd=stage,env=build_env,capture_output=True,text=True,timeout=90)
    if r.returncode:
        diagnostics=[json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
        missing=any(d.get('reason')=='compiler-message' and d['message'].get('code',{}).get('code')=='E0425' for d in diagnostics if d.get('message',{}).get('code') is not None)
        raise BuildError('UNRESOLVED_NATIVE_EXPORT' if missing else 'NATIVE_BINDING_COMPILE_FAILED',diagnostics)
    executable=Path(config['targetDirectory'])/'debug/patamaps-native-bindings-example';shutil.copyfile(executable,stage/'consumer');(stage/'consumer').chmod(0o755)
    write(stage/'projection.json',projection)
    records={p:digest(raw) for p,raw in sorted(inputs.items())}
    write(stage/'build.json',{'profile':'consumer-owned-json-string-routing-draft-1','engine':json.loads(call([cli,'engine'],stage,native_env)),'inputBytes':records,'generation':generation,'projection':projection,'coverage':coverage,'moduleMap':config['modules'],'authorization':'not-evaluated','activation':'not-evaluated'})
    return {'graph':graph,'generation':generation,'projection':projection,'coverage':coverage,'stage':stage,'inputs':records}
