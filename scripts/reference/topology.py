"""Exact decisions and finding subjects for the shared topology profile."""
import argparse,copy,json,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REV='399747a4ad05a37cd8db1cedd53048fad2175be4'
p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('--node',type=Path,required=True);p.add_argument('--cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.cli=a.cli.resolve()
original=json.loads((ROOT/'fixtures/topology/original.json').read_text());cases=[]
def case(id,expected,edit=lambda g,p:None,code=None):
    g,p=copy.deepcopy(original['graph']),copy.deepcopy(original['policy']);edit(g,p);cases.append({'id':id,'expected':expected,'code':code,'graph':g,'policy':p,'context':{}})
def remove(g,name):g['mappings']=[m for m in g['mappings'] if m['id']!='urn:test:mapping:'+name]
def add(g,name,relation,source,target):
    m=copy.deepcopy(g['mappings'][0]);m.update(id='urn:test:mapping:'+name,relation=relation,sources=[source],targets=[target]);g['mappings'].append(m)
def excluded(g,p,scoped=True,remove_binding=True):
    e=g['entities'][3];e['attributes'].update(topologyDisposition='excluded',exclusionReason='Reviewed semantic exception',exclusionOwner='team:test')
    if scoped:e['attributes']['exclusionRelations']=['topology:implemented_by']
    if remove_binding:remove(g,'route-page')
def parent(g,p):
    e=copy.deepcopy(g['entities'][2]);e['id']='urn:test:container:parent';g['entities'].append(e)
    add(g,'parent-contained','topology:contains','urn:test:segment:root',e['id']);add(g,'parent-wrap','topology:wraps',e['id'],'urn:test:container:root');add(g,'parent-provides','topology:provides_context',e['id'],'urn:test:context:web')
def second_provider(g,p):
    e=copy.deepcopy(g['entities'][2]);e.update(id='urn:test:provider:second',kind='topology:context-provider');g['entities'].append(e)
    add(g,'host-second','topology:hosts_provider','urn:test:container:root',e['id']);add(g,'second-provides','topology:provides_context',e['id'],'urn:test:context:web')
case('original-controls','viable')
for name,code in [('route-page','TOPOLOGY_REQUIRED_RELATION_MISSING'),('container-context','TOPOLOGY_CONTEXT_PROVIDER_MISSING'),('hydration-page','TOPOLOGY_REQUIRED_RELATION_MISSING'),('segment-page','TOPOLOGY_ENTITY_UNREACHABLE')]:case('removed-'+name,'rejected',lambda g,p,n=name:remove(g,n),code)
case('unscoped-exclusion','rejected',lambda g,p:excluded(g,p,False),'TOPOLOGY_EXCLUSION_NOT_ALLOWED')
case('relation-scoped-exclusion','viable',excluded)
def missing_owner(g,p):excluded(g,p);del g['entities'][3]['attributes']['exclusionOwner']
case('excluded-without-owner','rejected',missing_owner,'INVALID_TOPOLOGY_EXCLUSION')
case('excluded-and-mapped','rejected',lambda g,p:excluded(g,p,True,False),'EXCLUDED_TOPOLOGY_SUBJECT_MAPPED')
case('closest-provider-shadows-ancestor','viable',parent)
def fallback(g,p):parent(g,p);remove(g,'container-context')
case('ancestor-provider-fallback','viable',fallback)
case('same-depth-provider-ambiguity','rejected',second_provider,'TOPOLOGY_CONTEXT_PROVIDER_AMBIGUOUS')
case('wrong-counterpart-kind','rejected',lambda g,p:p['constraints'][0]['parameters'].update(counterpartKinds=['routing:schema']),'TOPOLOGY_COUNTERPART_KIND_MISMATCH')
case('empty-selection','rejected',lambda g,p:p['constraints'][0]['parameters'].update(subjectKinds=['unknown:kind']),'EMPTY_TOPOLOGY_SELECTION')
case('typed-parameter-refusal','rejected',lambda g,p:p['constraints'][0]['parameters'].update(allowExcluded='yes'),'INVALID_CONSTRAINT_PARAMETERS')
case('unique-counterpart-costs-no-extra-cardinality','viable',lambda g,p:add(g,'same-page-again','topology:implemented_by','urn:test:route:home','urn:test:page:home'))
def inactive(g,p):
    target='urn:test:mapping:route-page';p['mappings']=[{'select':{'ids':[m['id'] for m in g['mappings'] if m['id']!=target]},'coverage':'total','determinism':'deterministic','reversibility':'irreversible'},{'mapping':target,'coverage':'total','determinism':'deterministic','reversibility':'irreversible','applicability':{'when':{'key':'environment','operator':'equals','value':'production'}}}]
case('inactive-binding-refuses','rejected',inactive,'TOPOLOGY_REQUIRED_RELATION_MISSING');cases[-1]['context']={'environment':'development'}
def run(argv,cwd):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,timeout=90);assert r.returncode==0,(argv,r.stdout,r.stderr);return r.stdout
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
with tempfile.TemporaryDirectory(prefix='patamaps-topology-reference-') as directory:
    work=Path(directory);reference=work/'reference';reference.mkdir();archive=work/'source.tar'
    run(['git','-C',a.reference,'archive',REV,'--output',archive],ROOT)
    with tarfile.open(archive) as tar:tar.extractall(reference,filter='data')
    (reference/'node_modules').symlink_to(a.reference.resolve()/'node_modules',target_is_directory=True)
    run([a.node,reference/'node_modules/typescript/lib/tsc.js','-p','tsconfig.build.json'],reference)
    write(work/'cases.json',cases);old=json.loads(run([a.node,ROOT/'scripts/reference/evaluate_topology.mjs',reference,work/'cases.json'],work));new=[];comparisons=[]
    for c,o in zip(cases,old,strict=True):
        for name,kind in [('graph','graph'),('policy','policy')]:
            v=copy.deepcopy(c[name]);v.pop('$schema',None);v.update(schemaVersion='0.1.0',documentType=kind);write(work/(name+'.json'),v)
        write(work/'context.json',c['context'])
        captured=json.loads(run([a.cli,'capture','graph.json','policy.json','--context','context.json','--as-of','2026-09-08T00:00:00.000Z','--relation-pack',ROOT/'relation-packs/routing.json','--relation-pack',ROOT/'relation-packs/application-topology.json'],work));result=captured['result'];new.append({'id':c['id'],'capture':captured})
        def normalize(v):return {'status':v['status'],'activeMappings':sorted(v.get('generation',{}).get('activeMappings',[])),'findings':sorted({(i['code'],i.get('subjectId')) for i in v.get('issues',[])},key=str)}
        l,r=normalize(o['result']),normalize(result);assert l==r,(c['id'],l,r);assert result['status']==c['expected'],(c['id'],result)
        if c['code']:assert any(i['code']==c['code'] for i in result['issues'])
        comparisons.append({'id':c['id'],'pass':True,'expected':c['expected'],'reference':l,'successor':r})
report={'referenceEngine':REV,'successorEngine':json.loads(run([a.cli,'engine'],ROOT)),'cases':cases,'reference':old,'successor':new,'comparisons':comparisons,'normalization':'D001 draft envelopes/generation addresses only; finding codes and subjects exact','scope':'17 explicit shared topology controls plus separate native aggregate-work refusal; not old API drop-in parity'}
a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,report)
print('PASS: 17 pinned topology controls agree on decisions, active mappings and exact finding subjects.')
