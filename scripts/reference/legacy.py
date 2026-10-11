"""Re-evaluate five preserved legacy examples; never migrate their approvals.

Original inputs/generations remain byte evidence. New envelope/pack/graph
addresses are explicit migration steps and both full evaluations are retained.
"""
import argparse,copy,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REV='399747a4ad05a37cd8db1cedd53048fad2175be4'
p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('--node',type=Path,required=True);p.add_argument('--cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.cli=a.cli.resolve();a.output.mkdir(parents=True,exist_ok=True)
manifest=json.loads((ROOT/'fixtures/reference/evaluation/legacy-compatibility.json').read_text());reports=[]
def run(argv,cwd,input=None):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,input=input,capture_output=True,text=True,timeout=30);assert r.returncode==0,(r.returncode,r.stdout,r.stderr);return r.stdout
def original(path):return subprocess.check_output(['git','-C',str(a.reference),'show',REV+':'+path])
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
code='import{readFileSync}from"node:fs";import{pathToFileURL}from"node:url";const root=process.argv[1],{compileMetamap}=await import(pathToFileURL(root+"/dist/viability.js")),{RelationRegistry,coreRelationPack}=await import(pathToFileURL(root+"/dist/relations.js"));const v=JSON.parse(readFileSync(0,"utf8"));console.log(JSON.stringify(compileMetamap(v.graph,v.policy,{context:v.context,evaluatedAt:v.evaluatedAt,relationRegistry:new RelationRegistry([coreRelationPack,...v.packs])})));'
for entry in manifest['cases']:
    output=a.output/entry['id'];output.mkdir(exist_ok=True);g=json.loads(original(entry['graph']));pol=json.loads(original(entry['policy']));packs=[json.loads(original(path)) for path in entry['packs']]
    for name,path in [('original-graph.json',entry['graph']),('original-policy.json',entry['policy']),('original-generation.json',entry['generation'])]:(output/name).write_bytes(original(path))
    before=json.loads(run([a.node,'--input-type=module','-e',code,a.reference.resolve()],ROOT,input=json.dumps({'graph':g,'policy':pol,'packs':packs,'context':entry['context'],'evaluatedAt':entry['evaluatedAt']})))
    with tempfile.TemporaryDirectory(prefix='patamaps-legacy-') as temporary:
        work=Path(temporary);changed=copy.deepcopy(g);changed.pop('$schema',None);changed.update(schemaVersion='0.1.0',documentType='graph');policy=copy.deepcopy(pol);policy.pop('$schema',None);policy.update(schemaVersion='0.1.0',documentType='policy');paths=[]
        binding_changes=[]
        for i,pack in enumerate(packs):
            migrated=copy.deepcopy(pack);migrated.pop('$schema',None);migrated.update(schemaVersion='0.1.0',documentType='relation-pack');path=work/f'pack-{i}.json';write(path,migrated);paths.extend(['--relation-pack',str(path)])
            for binding in changed.get('relationPacks',[]):
                if binding['id']!=pack['id']:continue
                original_binding=copy.deepcopy(binding)
                if 'uri' in binding and ':' not in binding['uri']:binding['uri']='workspace:'+binding['uri']
                if binding!=original_binding:binding_changes.append({'original':original_binding,'migrated':copy.deepcopy(binding)})
        # Obtain the checked typed pack addresses in an explicit probe without
        # old digest assertions. The final migrated graph restores every exact
        # binding under the new domain and must pass full validation again.
        probe=copy.deepcopy(changed)
        for binding in probe.get('relationPacks',[]):binding.pop('digest',None)
        write(work/'pack-address-probe.json',probe)
        probe_digest=json.loads(run([a.cli,'validate','pack-address-probe.json',*paths],work))['graph']
        write(work/'probe-policy.json',{'schemaVersion':'0.1.0','documentType':'policy','id':'urn:legacy:address-probe','graph':{'id':probe['id'],'digest':probe_digest},'mappings':[],'constraints':[],'evidence':[]})
        typed=json.loads(run([a.cli,'capture','pack-address-probe.json','probe-policy.json','--as-of',entry['evaluatedAt'],*paths],work))['inputs']['packs']
        addresses={}
        for i,pack in enumerate(typed):
            path=work/f'typed-pack-{i}.json';write(path,pack);addresses[pack['id']]='sha256:'+hashlib.sha256(run([a.cli,'canonical',path],work).removesuffix('\n').encode()).hexdigest()
        for binding in changed.get('relationPacks',[]):
            if 'digest' in binding:binding['digest']=addresses[binding['id']]
        for record in binding_changes:record['migrated']=copy.deepcopy(next(b for b in changed['relationPacks'] if b['id']==record['original']['id']))
        binding_changes=[{'original':before,'migrated':after} for before,after in zip(g.get('relationPacks',[]),changed.get('relationPacks',[]),strict=True) if before!=after]
        write(work/'graph.json',changed)
        checked=json.loads(run([a.cli,'validate','graph.json',*paths],work))
        old_binding=copy.deepcopy(policy['graph']);policy['graph']={'id':changed['id'],'digest':checked['graph']}
        write(work/'policy.json',policy);write(work/'context.json',entry['context'])
        captured=json.loads(run([a.cli,'capture','graph.json','policy.json','--context','context.json','--as-of',entry['evaluatedAt'],*paths],work));after=captured['result']
        def normalize(v):return {'status':v['status'],'activeMappings':sorted(v.get('generation',{}).get('activeMappings',[])),'findings':sorted({(i['code'],i.get('subjectId')) for i in v.get('issues',[])},key=str)}
        l,r=normalize(before),normalize(after);assert l==r,(entry['id'],l,r)
        write(output/'migration.json',{'difference':'D001','originalGraphBinding':old_binding,'newGraphBinding':policy['graph'],'packBindingChanges':binding_changes,'compiler':json.loads(run([a.cli,'engine'],ROOT)),'originalInputPaths':entry['inputs'],'historicalGeneration':'preserved-not-executed-or-authorizing','approval':'not-migrated'})
        write(output/'reference-evaluation.json',before);write(output/'native-capture.json',captured);write(output/'native-policy.json',policy)
        reports.append({'id':entry['id'],'pass':True,'reference':l,'successor':r,'files':{p.name:'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}})
write(a.output/'acceptance.json',{'referenceEngine':REV,'successorEngine':json.loads(run([a.cli,'engine'],ROOT)),'cases':reports,'scope':'Fresh evaluations of five legacy example inputs; retained historical generations are not replayed by Rust or treated as approvals','normalization':'D001 declared envelope/address migration; exact finding codes/subjects and active mappings'})
print('PASS: five legacy examples retain raw historical evidence and agree on fresh evaluation decisions and finding subjects.')
