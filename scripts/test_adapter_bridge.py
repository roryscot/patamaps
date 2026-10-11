"""Execute every advertised optional bridge through the installed native host.

These are bounded fixture flows, not whole-framework integration or evidence
that providers disclose every runtime dependency. Process caching stays off.
"""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--cli', type=Path, required=True)
p.add_argument('--node', type=Path, required=True)
p.add_argument('--reference', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
cases = [
    ('typescript-zod', {'roots':['schemas']}, {'schemas/domain.ts': 'import {z} from "zod"; export const Item=z.object({id:z.string(),count:z.number().int().nullable()});'}),
    ('prisma', {'path':'schema.prisma'}, {'schema.prisma':'enum State {\n READY\n DONE\n}\nmodel Item {\n id String @id\n state State\n}\n'}),
    ('nextjs-app-router', {'root':'app'}, {'app/layout.tsx':'export default function Layout({children}) {return <main>{children}</main>;}', 'app/page.tsx':'"use client"; export default function Page(){return <main>Home</main>;}','app/api/items/route.ts':'export async function GET(){return new Response("ok");}'}),
    ('json-collections', {'path':'surfaces.json','collections':[{'pointer':'/surfaces','idProperty':'id','labelProperty':'label','entityKind':'media-surface','references':[{'property':'viewIds','targetKind':'flow-view'}]}]}, {'surfaces.json':json.dumps({'surfaces':[{'id':'discover','label':'Discover','viewIds':['feed','search'],'privatePayload':{'ignored':True}}]})}),
    ('legacy-sources', {'path':'sources.json'}, {'sources.json':json.dumps({'sourcesOfTruth':[{'id':'schema','label':'Schema','paths':['schema.prisma'],'outputs':['generated/client.ts']}]})}),
]
reports=[]
def write(path,v):path.write_text(json.dumps(v,indent=2)+'\n')
def run(cli,work,command,expected=0):
    r=subprocess.run([str(cli),*command],cwd=work,capture_output=True,text=True,timeout=30)
    assert r.returncode==expected,(r.returncode,r.stdout,r.stderr)
    return json.loads(r.stdout)
with tempfile.TemporaryDirectory(prefix='patamaps-adapter-bridge-') as temporary:
    for adapter,options,inputs in cases:
        work=Path(temporary)/adapter;work.mkdir()
        for name,content in inputs.items():
            path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        shutil.copyfile(ROOT/'adapters/metamap-process.mjs',work/'bridge.mjs')
        for pack in ['routing','application-topology']:shutil.copyfile(ROOT/'relation-packs'/f'{pack}.json',work/f'{pack}.json')
        identity='urn:bridge:'+adapter
        policy={'schemaVersion':'0.1.0','documentType':'policy','id':'urn:bridge:policy','graph':{'id':identity,'revision':'1'},'mappings':[{'select':{'provenanceStatuses':['observed','declared']},'coverage':'partial','determinism':'deterministic','reversibility':'irreversible'}],'constraints':[],'evidence':[]}
        write(work/'policy.json',policy)
        write(work/'projection.json',{'schemaVersion':'0.1.0','documentType':'projection-spec','id':'urn:bridge:projection','select':{'kinds':['explicitly-unselected:fixture']},'slots':[]})
        config={'schemaVersion':'0.1.0','documentType':'workspace-config','id':identity,'namespace':'bridge','revision':'1','sources':[{'id':'urn:bridge:source:'+adapter,'adapter':'process','invocation':{'executable':str(a.node.resolve()),'arguments':[str(work/'bridge.mjs'),str(a.reference.resolve())],'codeInputs':['bridge.mjs'],'bounds':{'maximumElapsedMs':10000,'maximumStdoutBytes':1048576,'maximumStderrBytes':65536}},'inputs':list(inputs),'config':{'adapter':adapter,**options}}],'packs':['routing.json','application-topology.json'],'policy':'policy.json','projections':[{'path':'projection.json','emissions':[]}],'context':{},'evaluatedAt':'2026-10-10T00:00:00.000Z'}
        write(work/'config.json',config)
        # The original legacy catalog deliberately emits unknown loss. Retain
        # that honest refusal; an adapter cannot invent a reviewed loss policy.
        expected_status='rejected' if adapter=='legacy-sources' else 'viable'
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
            code='import{readFileSync}from"node:fs";import{pathToFileURL}from"node:url";const{compileMetamap}=await import(pathToFileURL(process.argv[1]+"/dist/viability.js"));const v=JSON.parse(readFileSync(0,"utf8"));console.log(JSON.stringify(compileMetamap(v.graph,v.policy,{evaluatedAt:"2026-10-10T00:00:00.000Z"})));'
            r=subprocess.run([str(a.node),'--input-type=module','-e',code,str(a.reference.resolve())],input=json.dumps({'graph':legacy_graph,'policy':legacy_policy}),capture_output=True,text=True,check=True)
            reference_refusal=json.loads(r.stdout)
            origins=lambda v:sorted((i['code'],i.get('subjectId')) for i in v['issues'])
            assert reference_refusal['status']=='rejected' and origins(reference_refusal)==origins(evaluation)
        assert result['cacheHits']==0 and len(graph['entities'])>0
        source_receipts=[i for i in baseline['captures'][0]['sources'] if i['locator'].removeprefix('workspace:') in inputs]
        assert {i['locator'].removeprefix('workspace:') for i in source_receipts}==set(inputs)
        for i in source_receipts:
            raw=inputs[i['locator'].removeprefix('workspace:')].encode();assert i['digest']=='sha256:'+hashlib.sha256(raw).hexdigest() and i['byteLength']==len(raw)
        if adapter=='json-collections':assert all('privatePayload' not in e.get('attributes',{}) for e in graph['entities'])
        write(work/'baseline.json',baseline);saved=(work/'baseline.json').read_bytes()
        checked=run(a.cli.resolve(),work,['check','config.json','baseline.json','--root',str(work)],expected_exit)
        assert checked['status']==('unchanged' if expected_status=='viable' else 'rejected') and checked['changes']==[] and (work/'baseline.json').read_bytes()==saved
        reports.append({'adapter':adapter,'pass':True,'expected':expected_status,'status':expected_status,'adapterVersion':receipt['adapterVersion'],'inputs':source_receipts,'entities':len(graph['entities']),'mappings':len(graph['mappings']),'generatedDigest':baseline['digest'],'repeatedCheck':checked,'referenceRefusal':reference_refusal,'evaluation':evaluation,'cacheHits':0})
report={'engines':run(a.cli.resolve(),ROOT,['engine']),'cases':reports,'scope':'Captured bounded fixtures for all five advertised reused adapters; no provider dependency-closure, whole-framework, authentication or activation claim'}
a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,report)
print('PASS: all five adapters consumed exact captured fixtures; four viable controls and the original legacy unknown-loss refusal repeat without baseline writes or process caching.')
