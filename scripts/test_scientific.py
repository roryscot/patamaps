"""Actual native scientific lookup and complete package controls; no activation.

The existing TypeScript lookup is reused unchanged as a behavioral shadow. An
explicit adapter presents the new generated target table in its old API shape.
"""
import argparse, copy, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--cli',type=Path,required=True);p.add_argument('--node',type=Path,required=True);p.add_argument('--tsc',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.cli=a.cli.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_TARGET_DIR':str(ROOT/'target/scientific-consumer')}
def run(argv,cwd,expected=0):
    r=subprocess.run([str(v) for v in argv],cwd=cwd,env=env,capture_output=True,text=True,timeout=120)
    assert r.returncode==expected,f'{argv}\nexit={r.returncode}\n{r.stdout}\n{r.stderr}'
    return r.stdout
def write(path,v):path.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def cli(work,*args,expected=0):return json.loads(run([a.cli,*args],work,expected))
manifest=json.loads((ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset-manifest.json').read_text())
options={'id':'mgi-subset','namespace':'scientific-source','sourceRevision':manifest['sourceCommit'],'provenance':manifest}
report={'engines':json.loads(run([a.cli,'engine'],ROOT)),'sourcePin':manifest,'authorization':'not-evaluated','activation':'not-evaluated','scientificTruth':'not-established'}
with tempfile.TemporaryDirectory(prefix='patamaps-scientific-') as directory:
    work=Path(directory);shutil.copyfile(ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv',work/'source.tsv');write(work/'source-options.json',options)
    imported=cli(work,'sssom','import','source.tsv','--source-config','source-options.json');write(work/'imported.json',imported)
    raw=imported['graph'];graph=copy.deepcopy(raw);pack=imported['pack'];write(work/'pack.json',pack)
    for m in graph['mappings']:m['lossiness']='lossy'
    broad=next(m for m in graph['mappings'] if m['relation']=='scientific:broad-match')
    context={'executeScientificReversal':False};write(work/'context.json',context);write(work/'graph.json',graph)
    request={'schemaVersion':'0.1.0','documentType':'composition-request','law':'urn:metamap:scientific:law:reverse-broad','premises':[broad['id']],'context':context,'bounds':{'maxDepth':8,'maxDerivations':32},'derivations':[],'assessments':[],'evidence':[]};write(work/'request.json',request)
    proof=cli(work,'derive','graph.json','request.json','--relation-pack','pack.json');assert proof['status']=='proposed'
    graph['mappings'].append(proof['mapping']);write(work/'graph.json',graph)
    consumer='urn:metamap:example:exploratory-scientific-consumer';budget='urn:metamap:example:scientific-ordinal-budget'
    costs={'scientific:exact-match':1,'scientific:close-match':4,'scientific:broad-match':2,'scientific:narrow-match':2,'scientific:related-match':5}
    policy={'schemaVersion':'0.1.0','documentType':'policy','id':'urn:metamap:example:scientific-exploratory-policy','graph':{'id':graph['id'],'revision':graph['revision']},'mappings':[{'select':{'ids':[m['id'] for m in raw['mappings']]},'coverage':'partial','determinism':'deterministic','reversibility':'irreversible'},{'mapping':proof['mapping']['id'],'coverage':'partial','determinism':'deterministic','reversibility':'irreversible','applicability':{'when':{'key':'executeScientificReversal','operator':'equals','value':True}}}],'constraints':[],'evidence':[],'semantics':{'interpretation':'declared-law-application','derivations':[proof['derivation']],'derivationLimits':{'maxDepth':8,'maxDerivations':32},'assessments':[],'uncertaintyRequirements':[],'riskBudgets':[{'id':budget,'consumer':consumer,'classifications':[{'id':'urn:metamap:example:classification:'+m['id'].split(':')[-1],'select':{'ids':[m['id']]},'classification':'normative-derived-inverse' if m['id']==proof['mapping']['id'] else 'source-declared-approximation','cost':0 if m['id']==proof['mapping']['id'] else costs[m['relation']]} for m in graph['mappings']],'maximumTotalCost':18,'maximumInferredMappings':0,'maximumLossyMappings':7,'requireCompleteClassification':True,'requireCompleteDependencies':True}]}}
    spec={'schemaVersion':'0.1.0','documentType':'projection-spec','id':'urn:metamap:example:scientific-lookup','select':{'ids':[e['id'] for e in graph['entities']]},'slots':[{'name':n,'relation':f'scientific:{n}-match','direction':'outgoing','cardinality':'many','allowLossy':True} for n in ['exact','close','broad','narrow','related']],'semantics':{'consumer':consumer,'budget':budget}}
    write(work/'policy.json',policy);write(work/'projection-spec.json',spec);write(work/'receipts.json',imported['sources'])
    def capture_case(g,pol):
        write(work/'candidate.json',g);write(work/'candidate-policy.json',pol)
        return cli(work,'capture','candidate.json','candidate-policy.json','--relation-pack','pack.json','--spec','projection-spec.json','--source-receipts','receipts.json','--context','context.json','--as-of','2026-10-10T00:00:00.000Z',expected=0)
    captured=capture_case(graph,policy);assert captured['result']['status']=='viable',captured['result'];write(work/'capture.json',captured)
    assert captured['result']['projection']['semantics']['risk']['totalCost']==18
    cases=[]
    def rejected(name,g,pol,code):
        c=capture_case(g,pol);assert c['result']['status']=='rejected',(name,c)
        assert any(i['code']==code for i in c['result']['issues']),(name,code,c['result']['issues'])
        write(work/'negative.json',c);assert cli(work,'replay','negative.json')['status']=='verified'
        cases.append({'id':name,'expected':code,'capture':c,'replay':'verified'})
    unknown=copy.deepcopy(policy);unknown['mappings']=unknown['mappings'][:1];unknown['semantics']['derivations']=[];unknown['semantics']['riskBudgets'][0]['classifications']=unknown['semantics']['riskBudgets'][0]['classifications'][:-1];rejected('raw-unknown-loss',raw,unknown,'UNDECLARED_LOSSINESS')
    strict=copy.deepcopy(policy);strict['semantics']['uncertaintyRequirements']=[{'id':'urn:metamap:example:identity-required','select':{'ids':[m['id'] for m in graph['mappings']]},'dimension':'identity','allowedStates':['supported'],'requireEvidence':True}];rejected('supported-identity-required',graph,strict,'UNCERTAINTY_STATE_NOT_ALLOWED')
    limited=copy.deepcopy(policy);limited['semantics']['riskBudgets'][0]['maximumTotalCost']=17;rejected('budget17',graph,limited,'CONSUMER_RISK_BUDGET_EXCEEDED')
    reverse=copy.deepcopy(policy);del reverse['mappings'][1]['applicability'];rejected('irreversible-reversal',graph,reverse,'IRREVERSIBLE_DERIVATION_PREMISE')
    stale=copy.deepcopy(graph);next(m for m in stale['mappings'] if m['id']==broad['id'])['provenance']['sourceRevision']='changed-r2';rejected('changed-premise',stale,policy,'DERIVATION_PREMISE_OR_RULE_MISMATCH')
    settings={'name':'Seven MGI assertions with a checked exploratory lookup','description':'Licensed seven-of-1564 subset; producer species limitation retained','datePublished':'2026-10-10','consumer':consumer,'environment':'offline-exploration','source':options,'tsvReceipt':'mgi-subset:tsv','externalSources':[{'id':f"https://github.com/mapping-commons/mh_mapping_initiative/blob/{manifest['sourceCommit']}/{manifest['sourcePath']}",'name':'Full producer source','description':'1564-record original source remains external'}]};write(work/'crate-options.json',settings)
    package=cli(work,'sssom','crate','capture.json','crate-options.json');write(work/'crate.json',package);verified=cli(work,'sssom','verify-crate','crate.json');assert verified['status']=='verified'
    tamper=[]
    for name in ['bindings-1.rs','export.sssom.tsv','source/source-0.txt','policy.json','artifact-manifest.json']:
        bad=copy.deepcopy(package);bad['files'][name]+=' ';write(work/'bad-crate.json',bad)
        text=run([a.cli,'sssom','verify-crate','bad-crate.json'],work,2);tamper.append({'file':name,'result':'rejected','response':text})
    native=work/'installed-consumer';shutil.copytree(ROOT/'examples/scientific-lookup',native)
    for name,target in [('bindings-1.rs','bindings.rs'),('graph.json','graph.json'),('projection-0.json','projection.json')]:
        (native/'src'/target).write_text(package['files'][name])
    cargo=Path.home()/'.cargo/bin/cargo'
    tests=run([cargo,'test','--locked','--offline'],native);run([cargo,'build','--locked','--offline'],native)
    executable=ROOT/'target/scientific-consumer/debug/patamaps-scientific-lookup-example'
    rust=json.loads(run([executable],native));assert len(rust)==len(graph['entities'])
    run([executable,'urn:metamap:unknown'],native,2)
    shadow=work/'shadow';shadow.mkdir();(shadow/'package.json').write_text('{"type":"module"}');(shadow/'bindings.ts').write_text(package['files']['bindings-0.ts'])
    shutil.copyfile(ROOT/'fixtures/reference/examples/scientific-mapping/lookup.mjs',shadow/'lookup.mjs')
    for name in ['graph.json','projection-0.json']:(shadow/name).write_text(package['files'][name])
    (shadow/'main.mjs').write_text('import {readFileSync} from "node:fs"; import {bindings} from "./bindings.js"; import {createScientificLookup} from "./lookup.mjs"; const g=JSON.parse(readFileSync("graph.json","utf8")); const p=JSON.parse(readFileSync("projection-0.json","utf8")); const lookup=createScientificLookup(id=>({subject:p.entries.find(e=>e.subject.id===id).subject,slots:bindings[id]}),p,g); console.log(JSON.stringify(p.entries.map(e=>lookup(e.subject.id)).sort((a,b)=>a.subject.id<b.subject.id?-1:a.subject.id>b.subject.id?1:0)));')
    run([a.node,a.tsc,'--strict','--target','ES2022','--module','NodeNext','--moduleResolution','NodeNext','bindings.ts'],shadow)
    ts=json.loads(run([a.node,'main.mjs'],shadow));write(a.output/'native-lookup.json',rust);write(a.output/'shadow-lookup.json',ts)
    def first_difference(x,y,path='$'):
        if isinstance(x,dict) and isinstance(y,dict):
            if set(x)!=set(y):return (path,'keys',list(x),list(y))
            for k in x:
                d=first_difference(x[k],y[k],path+'.'+k)
                if d:return d
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):return (path,'length',len(x),len(y))
            for i,(u,v) in enumerate(zip(x,y,strict=True)):
                d=first_difference(u,v,f'{path}[{i}]')
                if d:return d
        elif x!=y:return (path,x,y)
        return None
    assert rust==ts,('Native lookup drift from unchanged existing consumer',first_difference(rust,ts))
    assertions=[m for e in rust for slot in e['slots'].values() for m in slot['assertions']];assert len(assertions)==7;assert {m['id'] for m in assertions}=={m['id'] for m in raw['mappings']}
    write(work/'document.json',imported['document']);default=cli(work,'sssom','export','document.json');condensed=cli(work,'sssom','export','document.json','--condense')
    (work/'default.sssom.tsv').write_text(default['text']);(work/'condensed.sssom.tsv').write_text(condensed['text'])
    for name in ['source.tsv','default.sssom.tsv','condensed.sssom.tsv','crate.json','imported.json','capture.json','graph.json','policy.json','projection-spec.json','crate-options.json']:
        shutil.copyfile(work/name,a.output/name)
    report.update(consumerLookup='executed-and-tested',existingTypeScriptShadow='exactly-equal',sourceAssertions=7,relations=5,ordinalCost=18,negativeCases=cases,crateVerification=verified,crateTamperCases=tamper,nativeLookup=rust,sourceBytesPreserved=(work/'source.tsv').read_bytes()==(ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv').read_bytes(),exports={'default':default['loss'],'condensed':condensed['loss']},nativeTestStdout=tests)
write(a.output/'acceptance.json',report)
print('PASS: installed static Rust lookup equals unchanged TypeScript consumer; seven assertion identities, five relations, budget18, strict/budget/reversal/stale controls, complete crate and tamper controls.')
