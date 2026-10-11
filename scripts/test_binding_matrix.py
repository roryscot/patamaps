"""Transpose the 22 preserved native binding scenarios into a native Rust build.

Preserve original authored graphs/policy/fact scopes and declared expectations.
D001 changes draft envelopes and stale-generation report formatting. D002 uses
JSON strings at generated function boundaries. No privileged activation occurs.
"""
import argparse,copy,hashlib,importlib.util,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
module=importlib.util.spec_from_file_location('consumer_builder',ROOT/'examples/native-bindings/build.py');builder=importlib.util.module_from_spec(module);module.loader.exec_module(builder)
p=argparse.ArgumentParser();p.add_argument('--cli',type=Path,required=True);p.add_argument('--node',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.cli=a.cli.resolve();a.output=a.output.resolve()
reference=ROOT/'fixtures/reference/examples/routing/bindings';expectations=json.loads((ROOT/'fixtures/conformance.json').read_text())['nativeBindingCases']
env={**os.environ,'PATH':'/usr/bin:/bin'}
def write(path,v):path.write_text(json.dumps(v,indent=2)+'\n')
def convert(v,kind):
    v=copy.deepcopy(v);v.pop('$schema',None);v.update(schemaVersion='0.1.0',documentType=kind);return v
def call(exe,identity,input,expected=0):
    r=subprocess.run([str(exe),identity,json.dumps(input,ensure_ascii=False)],env=env,capture_output=True,text=True,timeout=10)
    assert r.returncode==expected,(identity,input,r.returncode,r.stdout,r.stderr)
    return json.loads(r.stdout) if expected==0 else r.stderr.strip()
results=[];commands=[]
with tempfile.TemporaryDirectory(prefix='patamaps-binding-matrix-') as temp:
    work=Path(temp);base=work/'base';shutil.copytree(ROOT/'examples/native-bindings',base)
    config=json.loads((reference/'metamap.config.json').read_text());config={'sources':config['sources'],'modules':{'contract':'contract/input_schema.rs','service':'service/handlers/create_user.rs'},'originalModules':{'contract':'contract/input_schema.rs','service':'service/handlers/create_user.rs'},'routingPack':str(ROOT/'relation-packs/routing.json'),'targetDirectory':str(ROOT/'target/binding-consumer')}
    for s in config['sources']:
        g=convert(json.loads((reference/s['path']).read_text()),'graph')
        for e in g['entities']:
            if e['kind'] in ['routing:schema','routing:handler']:
                slot='contract' if e['kind']=='routing:schema' else 'service';symbol='validate_create_user' if slot=='contract' else 'create_user';file=config['modules'][slot]
                e['locators']=[{'uri':f'rust:crate::{slot}::{symbol}','digest':builder.digest((base/file).read_bytes())}]
        (base/s['path']).parent.mkdir(parents=True,exist_ok=True);write(base/s['path'],g)
    policy=convert(json.loads((reference/'consumer/viability-template.json').read_text())['policy'],'policy');write(base/'policy.json',policy)
    spec=convert(json.loads((reference/'consumer/projection.json').read_text()),'projection-spec');write(base/'projection.json',spec);write(base/'sources.json',config)
    accepted=builder.build(base,a.cli,work/'accepted',{'environment':'production'})
    saved={str(f.relative_to(accepted['stage'])):builder.digest(f.read_bytes()) for f in accepted['stage'].rglob('*') if f.is_file()}
    identity='urn:bindings:command:create-user'
    native_input_cases=[{'name':' Ada '},{'name':'\ufeffAda\ufeff'},{'name':'\u0085'},None,[],{}, {'name':''},{'name':'   '},{'name':1}]
    # Reuse the original validator/service unchanged as an independent runtime
    # shadow, rather than deriving expected outputs from the Rust implementation.
    shadow=work/'shadow.mjs';shadow.write_text('import {validateCreateUser} from '+json.dumps((reference/'contract/input-schema.mjs').as_uri())+'; import {createUser} from '+json.dumps((reference/'service/handlers/create-user.mjs').as_uri())+'; const inputs=JSON.parse(process.argv[2]); console.log(JSON.stringify(inputs.map(i=>{try{return {status:"executed",result:createUser(validateCreateUser(i))};}catch(e){return {status:"runtime-rejected",code:e.message};}})));')
    r=subprocess.run([str(a.node),str(shadow),json.dumps(native_input_cases)],capture_output=True,text=True,check=True);old_inputs=json.loads(r.stdout);input_results=[]
    for input,old in zip(native_input_cases,old_inputs,strict=True):
        if old['status']=='executed':new={'status':'executed','result':call(accepted['stage']/'consumer',identity,input)}
        else:new={'status':'runtime-rejected','code':call(accepted['stage']/'consumer',identity,input,2)}
        assert new==old,(input,new,old);input_results.append({'input':input,'reference':old,'native':new,'pass':True})
    for entry in expectations:
        case=entry['referenceCase'];expected=entry['originalExpectation'];root=work/case;shutil.copytree(base,root)
        graphs={s['id']:json.loads((root/s['path']).read_text()) for s in config['sources']};pol=copy.deepcopy(policy);cfg=copy.deepcopy(config);context={'environment':'development' if case=='development-context' else 'production'};override=None
        if case in ['missing-handler','missing-endpoint']:
            relation='routing:handled_by' if case=='missing-handler' else 'routing:exposed_as';removed={m['id'] for m in graphs['consumer']['mappings'] if m['relation']==relation};graphs['consumer']['mappings']=[m for m in graphs['consumer']['mappings'] if m['id'] not in removed];pol['mappings']=[m for m in pol['mappings'] if m['mapping'] not in removed]
        elif case in ['ambiguous-handler','ambiguous-endpoint']:
            kind='handler' if case=='ambiguous-handler' else 'endpoint';original=next(e for e in graphs['service']['entities'] if e['kind']==f'routing:{kind}');alternative=copy.deepcopy(original);alternative['id']=f'urn:bindings:{kind}:alternative';graphs['service']['entities'].append(alternative)
            original=next(m for m in graphs['consumer']['mappings'] if m['relation']==('routing:handled_by' if kind=='handler' else 'routing:exposed_as'));m=copy.deepcopy(original);m.update(id=f'urn:bindings:mapping:alternative-{kind}',targets=[alternative['id']]);graphs['consumer']['mappings'].append(m);d=copy.deepcopy(next(d for d in pol['mappings'] if d['mapping']==original['id']));d['mapping']=m['id'];pol['mappings'].append(d)
        elif case=='missing-context':context={}
        elif case=='conflicting-owners':graphs['consumer']['authorities'].append({'id':'urn:bindings:authority:conflicting-owner','concept':identity,'source':'urn:bindings:consumer:api','facts':['implementation'],'mode':'canonical','provenance':{'status':'declared','assertedBy':'team:consumer'}})
        elif case in ['narrow-delegation','widened-delegation']:graphs['consumer']['authorities'].append({'id':'urn:bindings:authority:delegated','concept':identity,'source':'urn:bindings:consumer:api','facts':['implementation'] if case=='narrow-delegation' else ['implementation','security'],'mode':'delegated','delegatedFrom':'urn:bindings:authority:implementation','provenance':{'status':'declared','assertedBy':'team:service'}})
        elif case=='conflicting-shards':graphs['consumer']['entities'].append({'id':identity,'kind':'routing:command','label':'A contradictory declaration'})
        elif case in ['unmapped-leaf','owned-exclusion']:
            e=copy.deepcopy(graphs['service']['entities'][0]);e['id']='urn:bindings:handler:unbound';graphs['service']['entities'].append(e)
            if case=='owned-exclusion':next(s for s in cfg['sources'] if s['id']=='service')['exclusions']=[{'entity':e['id'],'relation':'routing:handled_by','reason':'Internal helper is outside the API consumer','assertedBy':'team:service'}]
        elif case=='invalid-native-export':graphs['service']['entities'][0]['locators'][0]['uri']='rust:crate::service::not_exported'
        elif case=='locator-escape':cfg['modules']['service']='../outside.rs'
        elif case=='symlink-escape':
            path=root/'service/handlers/create_user.rs';outside=root/'outside-owner.rs';path.rename(outside);path.symlink_to(outside)
        elif case=='native-byte-drift':(root/'service/handlers/create_user.rs').write_text('pub fn create_user(_: &str)->String{"drifted".into()}')
        elif case=='moved-implementation':
            original=root/'service/handlers/create_user.rs';moved=root/'service/relocated/create_user.rs';moved.parent.mkdir();original.rename(moved);cfg['modules']['service']='service/relocated/create_user.rs'
        elif case=='new-implementation-identity':
            old=graphs['service']['entities'][0]['id'];new='urn:bindings:handler:new-implementation';graphs['service']['entities'][0]['id']=new
            for authority in graphs['service']['authorities']:
                if authority['source']==old:authority['source']=new
            for m in graphs['consumer']['mappings']:m['targets']=[new if t==old else t for t in m['targets']]
        elif case=='stale-generation':override=copy.deepcopy(accepted['generation']);override['activeMappings']=[]
        elif case not in ['normal-binding','development-context','invalid-runtime-input','runtime-structure-change']:raise AssertionError(case)
        for s in cfg['sources']:write(root/s['path'],graphs[s['id']])
        write(root/'sources.json',cfg);write(root/'policy.json',pol)
        try:
            actual=builder.build(root,a.cli,work/(case+'-candidate'),context,override)
            if expected['expected']=='rejected':raise AssertionError(f'{case}: candidate was accepted')
            if case=='invalid-runtime-input':outcome={'status':'runtime-rejected','code':call(actual['stage']/'consumer',identity,{'name':''},2)}
            elif case=='runtime-structure-change':outcome={'status':'runtime-rejected','code':call(actual['stage']/'consumer','urn:bindings:unknown',{'name':'Ada'},2)}
            else:
                response=call(actual['stage']/'consumer',identity,{'name':' Ada '});assert response=={'operation':'create-user','displayName':'Ada'}
                endpoint=next(s for s in actual['projection']['entries'][0]['slots'] if s['name']=='endpoint')['targets'][0]['attributes']['path']
                if 'endpoint' in expected:assert endpoint==expected['endpoint']
                if case=='moved-implementation':
                    assert actual['projection']['entries'][0]['subject']['id']==identity;assert actual['inputs']['service/relocated/create_user.rs']==accepted['inputs']['service/handlers/create_user.rs'];assert (actual['stage']/'src/main.rs').read_text().find('service/relocated/create_user.rs')>=0
                if case=='new-implementation-identity':assert next(s for s in actual['projection']['entries'][0]['slots'] if s['name']=='handler')['targets'][0]['id']=='urn:bindings:handler:new-implementation'
                if case=='narrow-delegation':assert next(d for d in actual['graph']['authorities'] if d['id']=='urn:bindings:authority:delegated')['facts']==['implementation']
                if case=='owned-exclusion':assert any(r['exclusion'] is not None for r in actual['coverage'])
                outcome={'status':'executed','response':response,'endpoint':endpoint,'build':json.loads((actual['stage']/'build.json').read_text())}
        except builder.BuildError as e:
            assert expected['expected']=='rejected',(case,e.code,e.details)
            required={'stale-generation':'PROJECTION_GENERATION_RECHECK_FAILED','conflicting-shards':'CONFLICTING_SHARD_DEFINITION'}.get(case,expected['code']);codes=[i['code'] for i in e.details] if isinstance(e.details,list) and e.details and 'code' in e.details[0] else [e.code]
            assert required in codes,(case,required,e.code,e.details)
            outcome={'status':'rejected','code':required,'details':e.details}
        assert outcome['status']==expected['expected'],(case,outcome,expected)
        if expected['expected']=='runtime-rejected':assert outcome['code']==expected['code']
        now={str(f.relative_to(accepted['stage'])):builder.digest(f.read_bytes()) for f in accepted['stage'].rglob('*') if f.is_file()};assert now==saved,'Candidate changed saved accepted build'
        results.append({'id':case,'originalExpectation':expected,'successor':outcome,'pass':True,'savedAcceptedBuildUnchanged':True})
    a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,{'profile':'consumer-owned-json-string-routing-draft-1','referencePin':json.loads((ROOT/'fixtures/conformance.json').read_text())['engineRevision'],'compiler':json.loads(builder.call([a.cli,'engine'],work,env)),'cases':results,'runtimeInputShadow':input_results,'scope':'All 22 declared scenario meanings transposed into native builds; no claim of old JS API drop-in compatibility. D008 maps only stale-generation and conflicting-shards diagnostic names, retaining original expectations and full findings. D002 serializes consumer input/output at generated string-function boundaries.','authorization':'not-evaluated','activation':'not-evaluated'})
print('PASS: all 22 preserved binding scenarios transposed into real Rust builds/runtime, saved artifact preservation, plus nine unchanged-JavaScript validator/service shadow inputs.')
