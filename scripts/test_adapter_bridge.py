"""Execute every advertised optional bridge through the installed native host.

These are bounded fixture flows, not whole-framework integration or evidence
that providers disclose every runtime dependency. Process caching stays off.
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, tempfile
from contextlib import contextmanager
from pathlib import Path
from parity.retained_copy import copy_tree, install_discovery_tools
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--cli', type=Path, required=True)
p.add_argument('--node', type=Path, required=True)
p.add_argument('--reference', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
typescript = a.reference.resolve() / 'node_modules/typescript'
assert json.loads((typescript/'package.json').read_text())['version']=='5.9.3'
assert json.loads((ROOT/'adapters/discovery/package.json').read_text())['dependencies']=={'typescript':'5.9.3','patamaps-native-sdk-draft':'0.1.0','ajv':'8.20.0','ajv-formats':'3.0.1'}
cases = [
    ('typescript-zod', {'roots':['schemas']}, {'schemas/domain.ts': 'import {z} from "zod"; export const Item=z.object({id:z.string(),count:z.number().int().nullable()});'}),
    ('prisma', {'path':'schema.prisma'}, {'schema.prisma':'enum State {\n READY\n DONE\n}\nmodel Item {\n id String @id\n state State\n}\n'}),
    ('nextjs-app-router', {'root':'app'}, {'app/layout.tsx':'export default function Layout({children}) {return <main>{children}</main>;}', 'app/page.tsx':'"use client"; export default function Page(){return <main>Home</main>;}','app/api/items/route.ts':'export async function GET(){return new Response("ok");}'}),
    ('json-collections', {'path':'surfaces.json','collections':[{'pointer':'/surfaces','idProperty':'id','labelProperty':'label','entityKind':'media-surface','references':[{'property':'viewIds','targetKind':'flow-view'}]}]}, {'surfaces.json':json.dumps({'surfaces':[{'id':'discover','label':'Discover','viewIds':['feed','search'],'privatePayload':{'ignored':True}}]})}),
    ('legacy-sources', {'path':'sources.json'}, {'sources.json':json.dumps({'sourcesOfTruth':[{'id':'schema','label':'Schema','paths':['schema.prisma'],'outputs':['generated/client.ts']}]})}),
    ('sssom-tsv', {'path':'mapping.data','formatVersion':'1.0.0','sourceRevision':'fixture-r1'}, {'mapping.data':(ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv').read_text()}),
    ('metamap-shard', {'path':'shard.json'}, {'shard.json':json.dumps({'schemaVersion':'2.0.0','id':'urn:bridge:portable-source','namespace':'bridge','entities':[{'id':'urn:bridge:portable-item','kind':'item','label':'Portable item','attributes':{'sourceExtension':{'preserved':True}}},{'id':'urn:bridge:portable-target','kind':'item','label':'Portable target'}],'mappings':[{'id':'urn:bridge:portable-reference','relation':'core:references','sources':['urn:bridge:portable-item'],'targets':['urn:bridge:portable-target'],'cardinality':'one-to-one','lossiness':'lossless','provenance':{'status':'declared','assertedBy':'fixture-owner'}}],'authorities':[],'metadata':{'declaredOnly':True}})}),
]
reports=[]
commands=[]
@contextmanager
def retained_directory():
    # A test result must not remove its consumer installation or source data.
    yield tempfile.mkdtemp(prefix='patamaps-independent-discovery-')
def write(path,v):path.write_text(json.dumps(v,indent=2)+'\n')
def run(cli,work,command,expected=0):
    r=subprocess.run([str(cli),*command],cwd=work,capture_output=True,text=True,timeout=30)
    number=len(commands)
    stdout=work/f'native-{number}.stdout';stderr=work/f'native-{number}.stderr'
    stdout.write_text(r.stdout);stderr.write_text(r.stderr)
    commands.append({'argv':[str(cli),*command],'cwd':str(work),'exitCode':r.returncode,
                     'stdout':str(stdout),'stdoutDigest':'sha256:'+hashlib.sha256(stdout.read_bytes()).hexdigest(),
                     'stderr':str(stderr),'stderrDigest':'sha256:'+hashlib.sha256(stderr.read_bytes()).hexdigest()})
    assert r.returncode==expected,(r.returncode,r.stdout,r.stderr)
    return json.loads(r.stdout)
with retained_directory() as temporary:
    print('Retained independent discovery fixture root: '+temporary,flush=True)
    for adapter,options,inputs in cases:
        work=Path(temporary)/adapter;work.mkdir()
        for name,content in inputs.items():
            path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        copy_tree(ROOT/'adapters',work/'adapters')
        tooling_record=install_discovery_tools(a.reference.resolve(),work/'node_modules')
        copy_tree(ROOT/'sdk/typescript',work/'node_modules/patamaps-native-sdk-draft')
        bridge=work/'adapters/metamap-process.mjs'
        absent=work/'no-metamap-package-installed'
        assert not absent.exists()
        code_inputs=sorted(str(path.relative_to(work)) for path in (work/'adapters').rglob('*') if path.is_file() and path.suffix in {'.mjs','.js','.json'})
        code_inputs+=sorted(str(path.relative_to(work)) for path in (work/'node_modules/patamaps-native-sdk-draft').rglob('*') if path.is_file() and (path.suffix in {'.mjs','.js','.json'}))
        if adapter in {'typescript-zod','nextjs-app-router'}:
            code_inputs+=['node_modules/typescript/lib/typescript.js','node_modules/typescript/package.json']
        if adapter=='metamap-shard':
            for item in tooling_record['packages']:
                if item['name']=='typescript':continue
                code_inputs+=sorted(str(path.relative_to(work)) for path in (work/'node_modules'/item['name']).rglob('*') if path.is_file() and path.suffix in {'.js','.json'})
        packs=['routing','application-topology']+(['scientific-skos'] if adapter=='sssom-tsv' else [])
        for pack in packs:shutil.copyfile(ROOT/'relation-packs'/f'{pack}.json',work/f'{pack}.json')
        identity='urn:bridge:'+adapter
        policy={'schemaVersion':'0.1.0','documentType':'policy','id':'urn:bridge:policy','graph':{'id':identity,'revision':'1'},'mappings':[{'select':{'provenanceStatuses':['observed','declared']},'coverage':'partial','determinism':'deterministic','reversibility':'irreversible'}],'constraints':[],'evidence':[]}
        if adapter=='sssom-tsv':
            # Unknown loss is checked before applicability in both engines.
            # Preserve the source and test that selecting nothing cannot bypass it.
            policy['mappings'][0]['applicability']={'when':{'key':'useScientificAssertions','operator':'equals','value':True}}
            policy['semantics']=json.loads((ROOT/'fixtures/laws/policy.json').read_text())['semantics']
            policy['semantics']['riskBudgets']=[{'id':'urn:bridge:scientific-budget','consumer':'urn:bridge:scientific-consumer','classifications':[],
                'maximumTotalCost':0,'maximumInferredMappings':0,'maximumLossyMappings':0,'requireCompleteClassification':True,'requireCompleteDependencies':True}]
        write(work/'policy.json',policy)
        write(work/'projection.json',{'schemaVersion':'0.1.0','documentType':'projection-spec','id':'urn:bridge:projection','select':{'kinds':['explicitly-unselected:fixture']},'slots':[]})
        arguments=[str(bridge),'--native',str(a.cli.resolve())] if adapter=='sssom-tsv' else [str(bridge),str(absent)]
        config={'schemaVersion':'0.1.0','documentType':'workspace-config','id':identity,'namespace':'bridge','revision':'1','sources':[{'id':'urn:bridge:source:'+adapter,'adapter':'process','invocation':{'executable':str(a.node.resolve()),'arguments':arguments,'codeInputs':code_inputs,'bounds':{'maximumElapsedMs':10000,'maximumStdoutBytes':1048576,'maximumStderrBytes':65536}},'inputs':list(inputs),'config':{'adapter':adapter,**options}}],'packs':[pack+'.json' for pack in packs],'policy':'policy.json','projections':[{'path':'projection.json','emissions':[]}],'context':{},'evaluatedAt':'2026-10-10T00:00:00.000Z'}
        if adapter=='sssom-tsv':
            config['context']={'useScientificAssertions':False}
            projection=json.loads((work/'projection.json').read_text())
            projection['semantics']={'consumer':'urn:bridge:scientific-consumer','budget':'urn:bridge:scientific-budget'}
            write(work/'projection.json',projection)
        write(work/'config.json',config)
        # The original legacy catalog deliberately emits unknown loss. Retain
        # that honest refusal; an adapter cannot invent a reviewed loss policy.
        expected_status='rejected' if adapter in {'legacy-sources','sssom-tsv'} else 'viable'
        expected_exit=2 if expected_status=='rejected' else 0
        result=run(a.cli.resolve(),work,['generate','config.json','--root',str(work)],expected_exit)
        baseline=result['baseline'];receipt=baseline['discovery'][0];graph=baseline['captures'][0]['inputs']['graph']
        evaluation=baseline['captures'][0]['result'];assert evaluation['status']==expected_status,(adapter,evaluation)
        reference_refusal=None
        if expected_status=='rejected':
            assert evaluation['issues'] and all(i['code']=='UNDECLARED_LOSSINESS' for i in evaluation['issues'])
            assert baseline['outputs']=={}
            legacy_graph={k:v for k,v in graph.items() if k!='documentType'};legacy_graph['schemaVersion']='2.0.0'
            legacy_policy={k:v for k,v in policy.items() if k!='documentType'};legacy_policy['schemaVersion']='1.0.0'
            code='import{readFileSync}from"node:fs";import{pathToFileURL}from"node:url";const{compileMetamap}=await import(pathToFileURL(process.argv[1]+"/dist/viability.js"));const v=JSON.parse(readFileSync(0,"utf8"));console.log(JSON.stringify({result:compileMetamap(v.graph,v.policy,{evaluatedAt:"2026-10-10T00:00:00.000Z"}),envelopeChanges:[]}));'
            if adapter=='sssom-tsv':
                # Convert only the declared wire envelope and exact bundled pack
                # reference. Retain every scientific fact and unknown-loss value.
                semantics=legacy_policy.pop('semantics');semantics.pop('interpretation')
                legacy_policy.update(semantics);legacy_policy['schemaVersion']='2.0.0'
                code='''import{readFileSync}from"node:fs";import{pathToFileURL}from"node:url";
const dir=process.argv[1],v=JSON.parse(readFileSync(0,"utf8"));
const{compileMetamap}=await import(pathToFileURL(dir+"/dist/viability.js"));
const{RelationRegistry,coreRelationPack}=await import(pathToFileURL(dir+"/dist/relations.js"));
const{scientificSkosRelationPack}=await import(pathToFileURL(dir+"/dist/scientific-relations.js"));
const{relationPackDigest}=await import(pathToFileURL(dir+"/dist/relation-pack.js"));
const pack=scientificSkosRelationPack(),envelopeChanges=[];
for(const reference of v.graph.relationPacks){
  if(reference.id!==pack.id||reference.version!==pack.version)throw new Error("Unexpected scientific pack reference");
  envelopeChanges.push({field:"relationPacks[].digest",before:reference.digest,after:relationPackDigest(pack),reason:"Restore the exact pinned MetaMap 2.0 pack envelope for the reference-only call"});
  reference.digest=relationPackDigest(pack);
}
console.log(JSON.stringify({result:compileMetamap(v.graph,v.policy,{evaluatedAt:"2026-10-10T00:00:00.000Z",context:v.context,relationRegistry:new RelationRegistry([coreRelationPack,pack])}),envelopeChanges}));'''
            payload=json.dumps({'graph':legacy_graph,'policy':legacy_policy,'context':config['context']})
            (work/'reference-refusal.input.json').write_text(payload+'\n')
            argv=[str(a.node),'--input-type=module','-e',code,str(a.reference.resolve())]
            r=subprocess.run(argv,input=payload,capture_output=True,text=True)
            (work/'reference-refusal.stdout').write_text(r.stdout);(work/'reference-refusal.stderr').write_text(r.stderr)
            commands.append({'argv':argv,'cwd':str(ROOT),'exitCode':r.returncode,'input':str(work/'reference-refusal.input.json'),
                'inputDigest':'sha256:'+hashlib.sha256((work/'reference-refusal.input.json').read_bytes()).hexdigest(),
                'stdout':str(work/'reference-refusal.stdout'),'stdoutDigest':'sha256:'+hashlib.sha256(r.stdout.encode()).hexdigest(),
                'stderr':str(work/'reference-refusal.stderr'),'stderrDigest':'sha256:'+hashlib.sha256(r.stderr.encode()).hexdigest()})
            assert r.returncode==0,r.stderr
            observed=json.loads(r.stdout);reference_refusal=observed['result']
            write(work/'reference-envelope-changes.json',observed['envelopeChanges'])
            origins=lambda v:sorted((i['code'],i.get('subjectId')) for i in v['issues'])
            assert reference_refusal['status']=='rejected' and origins(reference_refusal)==origins(evaluation)
        assert result['cacheHits']==0 and len(graph['entities'])>0
        source_receipts=[i for i in baseline['captures'][0]['sources'] if i['locator'].removeprefix('workspace:') in inputs]
        assert {i['locator'].removeprefix('workspace:') for i in source_receipts}==set(inputs)
        for i in source_receipts:
            raw=inputs[i['locator'].removeprefix('workspace:')].encode();assert i['digest']=='sha256:'+hashlib.sha256(raw).hexdigest() and i['byteLength']==len(raw)
        if adapter=='json-collections':assert all('privatePayload' not in e.get('attributes',{}) for e in graph['entities'])
        if adapter=='metamap-shard':
            original=json.loads(inputs['shard.json'])
            for key in ['entities','mappings','authorities','metadata']:
                assert receipt['shard'][key]==original[key]
        if adapter=='sssom-tsv':
            assert len(graph['mappings'])==7 and all(mapping['lossiness']=='unknown' for mapping in graph['mappings'])
            assert graph['authorities']==[] and all(entity['kind']=='scientific:entity' for entity in graph['entities'])
            # Composition names its sources; the baseline also retains the
            # complete discovery shard, where per-source metadata belongs.
            changes=receipt['shard']['metadata']['patamapsDiscovery']['compatibilityChanges']
            reference_changes=json.loads((work/'reference-envelope-changes.json').read_text())
            assert len(changes)==len(reference_changes)==1
            assert changes[0]['original']==reference_changes[0]['after']
            assert changes[0]['converted']==reference_changes[0]['before']
            assert receipt['shard']['metadata']['sssom']['effectiveMetadata']['license']
            assert evaluation['status']=='rejected' and 'generation' not in evaluation
            assert len(evaluation['issues'])==7 and all(issue['code']=='UNDECLARED_LOSSINESS' for issue in evaluation['issues'])
        write(work/'baseline.json',baseline);saved=(work/'baseline.json').read_bytes()
        checked=run(a.cli.resolve(),work,['check','config.json','baseline.json','--root',str(work)],expected_exit)
        assert checked['status']==('unchanged' if expected_status=='viable' else 'rejected') and checked['changes']==[] and (work/'baseline.json').read_bytes()==saved
        code_inventory=[{'path':path,'digest':'sha256:'+hashlib.sha256((work/path).read_bytes()).hexdigest(),'bytes':(work/path).stat().st_size} for path in code_inputs]
        reports.append({'adapter':adapter,'pass':True,'expected':expected_status,'status':expected_status,'adapterVersion':receipt['adapterVersion'],'inputs':source_receipts,'entities':len(graph['entities']),'mappings':len(graph['mappings']),'generatedDigest':baseline['digest'],'repeatedCheck':checked,'referenceRefusal':reference_refusal,'evaluation':evaluation,'cacheHits':0,'codeInventory':code_inventory,'tooling':tooling_record,'retainedStaging':[str(path) for path in work.glob('.patamaps-discovery-*')]})
engine=json.loads(subprocess.check_output([str(a.cli.resolve()),'engine']))
report={'status':'passed','engines':engine,'candidateBinaryDigest':'sha256:'+hashlib.sha256(a.cli.resolve().read_bytes()).hexdigest(),
        'host':{'platform':platform.platform(),'architecture':platform.machine()},'retainedRun':temporary,'commands':commands,'cases':reports,
        'providerProvenance':json.loads((ROOT/'adapters/discovery/provenance.json').read_text()),'typescriptVersion':'5.9.3',
        'runtimeMetaMapPackage':'absent; the historical absolute argument points to a nonexistent directory',
        'scope':'Installed captured fixtures for seven extracted providers through the native host; five viable framework/shard controls and independently matched legacy/scientific unknown-loss refusals. Scientific assertions remain unadmitted. Exact optional tooling bytes are verified against the frozen tooling closure. The reference is used only as an independent expected-refusal oracle. No provider dependency-closure, whole-framework, authentication, activation, full 64 MiB workflow or full-parity claim.',
        'fixtureDriverDigest':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scientificExpectationCorrection':{'previous':'viable with an empty consumer and inactive declarations','current':'rejected for seven source assertions with unknown loss','reason':'Both native admission and pinned MetaMap validate declared loss before contextual applicability. Preserve facts, assert exact refusal codes/subjects against the reference, and retain all failed attempts.','referenceSource':'src/viability.ts:validateDeclaredSemantics; src/__tests__/scientific-source.test.ts'},
        'shardFixtureCorrection':{'previous':'An empty mapping set was incorrectly expected to be viable under a policy selector for declared/observed mappings.','current':'The positive fixture explicitly declares one lossless core:references mapping between two entities; its complete entities, mapping, authority and metadata fields must survive discovery.','reason':'Native and pinned reference both refuse the previous empty fixture with EMPTY_MAPPING_SELECTOR. Its bytes, logs and independent reference result remain in docs/acceptance/parity/component-refresh-2026-10-11T23-28-04.834843Z/seven-provider-workspace.failure.json. No original expectations or native refusals are changed.'},
        'originalCasesClosed':0}
a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,report)
print('PASS: seven installed providers consumed exact captured fixtures without a MetaMap runtime package; five viable flows and independently matched legacy/scientific refusals repeat without baseline writes or process caching. Retained run: '+temporary)
