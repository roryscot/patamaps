"""Compare retained, installed workspace runs against pinned original output."""
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from retained_copy import copy_tree, copy_file, install_discovery_tools
from storage_guard import ensure_guarded, node_runtime
from identity import identities

ensure_guarded()
ROOT = Path(__file__).resolve().parents[2]
NODE = node_runtime()
ORACLE = ROOT / json.loads((ROOT / '.tools/parity/oracles/current.json').read_text())['source']
SUPPLEMENT = json.loads((ROOT / 'fixtures/parity/supplement.json').read_text())
sha = lambda raw: 'sha256:' + hashlib.sha256(raw).hexdigest()
def verify_tree():
    for item in SUPPLEMENT['referenceTree']:
        raw = (ORACLE / item['path']).read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == item['gitBlob'], item['path']
verify_tree()
output = ROOT / 'docs/acceptance/parity' / ('workspace-workflow-' + datetime.now(timezone.utc).isoformat().replace(':','-'))
output.mkdir(parents=True)
work = Path(tempfile.mkdtemp(prefix='patamaps-workspace-workflow-'))
copy_tree(ROOT / 'sdk/typescript', work / 'node_modules/patamaps-native-sdk-draft')
copy_tree(ROOT / 'adapters/discovery', work / 'node_modules/patamaps-discovery-draft')
tooling = install_discovery_tools(ORACLE, work / 'node_modules')
native = work / 'patamaps'
copy_file(ROOT / 'target/debug/patamaps', native)
(work / 'package.json').write_text('{"type":"module"}\n')
script = work / 'workflow.mjs'
script.write_text(r'''
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,readdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [mode,oracle,base,exe]=process.argv.slice(2);
await mkdir(base,{recursive:true});
const calls=[];
let api,AdapterRegistry,createDefault;
if(mode==='reference') {
  api=await import(pathToFileURL(join(oracle,'dist/workspace.js')));
  ({AdapterRegistry,createDefaultAdapterRegistry:createDefault}=await import(pathToFileURL(join(oracle,'dist/adapters/registry.js'))));
} else {
  const sdk=await import('patamaps-native-sdk-draft/legacy-validation');
  const providers=await import('patamaps-discovery-draft');
  providers.configureDiscoveryNative(exe,x=>calls.push(x));
  const nativeApi=sdk.createLegacyValidationApi(exe,x=>calls.push(x));
  api={discoverWorkspace:nativeApi.discoverLegacyWorkspace,checkWorkspace:nativeApi.checkLegacyWorkspace,writeWorkspaceOutputs:nativeApi.writeLegacyWorkspaceOutputs,workspaceHasErrors:nativeApi.legacyWorkspaceHasErrors};
  AdapterRegistry=nativeApi.LegacyAdapterRegistry;createDefault=nativeApi.createDefaultLegacyAdapterRegistry;
}
const config={schemaVersion:'1.0.0',id:'urn:test:metamap:workspace',namespace:'test',repository:'fixture',repositoryRoot:'.',sources:[{id:'db',adapter:'prisma',path:'schema.prisma'},{id:'schemas',adapter:'typescript-zod',roots:['schemas']}],correspondences:[{id:'item-domain',source:{sourceId:'schemas',kind:'schema',name:'itemSchema'},target:{sourceId:'db',kind:'model',name:'Item'},fields:{pairs:[{source:'id',target:'id'}],requireSourceCoverage:true,requireTargetCoverage:true},authority:{side:'target',facts:['type']}}],outputs:{graph:'generated/graph.json',snapshot:'generated/snapshot.json',report:'generated/report.md',documentation:'generated/graph.md',cache:'.cache/metamap'},policy:{baselineChanges:'error',unconfiguredStructures:'ignore'}};
const makeLoaded=(root,config)=>({config,configPath:join(root,'meta/config.json'),configDirectory:join(root,'meta'),repositoryRoot:root});
const prisma='model Item {\n id String @id\n}\n';
const zod='import { z } from "zod";\nexport const itemSchema = z.object({ id: z.string() });\n';
async function fixture(name){const root=join(base,name);await mkdir(join(root,'schemas'),{recursive:true});await writeFile(join(root,'schema.prisma'),prisma);await writeFile(join(root,'schemas/item.ts'),zod);return root;}
async function files(root){const result={};async function walk(dir,prefix=''){for(const e of (await readdir(dir,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))){const p=join(dir,e.name),key=prefix+e.name;if(e.isDirectory())await walk(p,key+'/');else result[key]=(await readFile(p)).toString('base64');}}await walk(root);return result;}
const observations=[];
const record=(name,value)=>observations.push({name,value:JSON.parse(JSON.stringify(value))});
async function observe(name,fn){try{const value=await fn();record(name,{status:'observed',...value});}catch(e){record(name,{status:'threw',error:{name:e.name,message:e.message,...(e.code?{code:e.code}:{}),...(e.syscall?{syscall:e.syscall}:{}),...(e.path?{path:e.path}:{}),...(e.errno!==undefined?{errno:e.errno}:{})}});}}
const state=v=>({discovery:v,hasErrors:api.workspaceHasErrors(v),keys:Object.keys(v),baselineOwn:Object.hasOwn(v,'baseline')});
const root=await fixture('pipeline'),loaded=makeLoaded(root,config);
const generated=await api.discoverWorkspace(loaded,{useCache:true});
record('generation',state(generated));await api.writeWorkspaceOutputs(loaded,generated);record('generation-files',await files(root));
const clean=await api.checkWorkspace(loaded,{useCache:true});record('clean-check',state(clean));await api.writeWorkspaceOutputs(loaded,clean);record('clean-files',await files(root));
const baseline=await readFile(join(root,config.outputs.graph));
await writeFile(join(root,'schemas/item.ts'),'import { z } from "zod";\nexport const itemSchema = z.object({ id: z.number().int() });\n');
const drifted=await api.checkWorkspace(loaded,{useCache:true});record('drift-check',state(drifted));record('baseline-preserved',(await readFile(join(root,config.outputs.graph))).equals(baseline));
for(const severity of ['warning','ignore']){const c=structuredClone(config);c.policy.baselineChanges=severity;record('drift-'+severity,state(await api.checkWorkspace(makeLoaded(root,c),{useCache:true})));}
for(const [name,bytes] of [['null-baseline','null'],['invalid-baseline','{}'],['malformed-baseline','{bad']]){await writeFile(join(root,config.outputs.graph),bytes);await observe(name,async()=>state(await api.checkWorkspace(loaded)));}
const missing=await fixture('missing');await observe('missing-baseline',async()=>state(await api.checkWorkspace(makeLoaded(missing,config))));
const readonly=await fixture('readonly');record('readonly',state(await api.discoverWorkspace(makeLoaded(readonly,config),{useCache:false,writeCache:false})));record('readonly-files',await files(readonly));
// Callback identity, receiver binding, stored version and registry ordering.
const customRoot=join(base,'custom');await mkdir(customRoot);const events=[];let cfg,ctx;
const custom={id:'fixture',version:'1.0.0',async fingerprint(c,x){cfg=c;ctx=x;events.push({method:'fingerprint',receiver:this===custom});return [];},async discover(c,x){events.push({method:'discover',receiver:this===custom,configSame:c===cfg,contextSame:x===ctx});return {sourceId:c.id,adapter:'fixture',adapterVersion:'1.0.0',inputs:[],document:{schemaVersion:'2.0.0',id:'urn:test:custom:shard',namespace:x.namespace,entities:[{id:'urn:test:custom:entity',kind:'concept',label:'\ud800\ue000'}],mappings:[],authorities:[]},diagnostics:[]};}};
const registry=new AdapterRegistry().register(custom);custom.version='changed';
const cc={...config,sources:[{id:'a/b😀',adapter:'fixture'}],correspondences:[]};const cl=makeLoaded(customRoot,cc);
record('registry', {ids:registry.ids(),getVersion:registry.get('fixture').version,getMissing:registry.get('missing'),distinctIds:registry.ids()!==registry.ids()});
await observe('registry-duplicate',async()=>({value:registry.register(custom)}));await observe('registry-missing',async()=>({value:registry.require('missing')}));
record('custom-first',state(await api.discoverWorkspace(cl,{adapterRegistry:registry})));record('custom-cached',state(await api.discoverWorkspace(cl,{adapterRegistry:registry})));record('custom-events',events);record('custom-files',await files(customRoot));
const cacheFile=join(customRoot,cc.outputs.cache,(await readdir(join(customRoot,cc.outputs.cache)))[0]);const cache=JSON.parse(await readFile(cacheFile,'utf8'));
for(const [name,entry] of [['wrong-cache-version',{...cache,cacheVersion:'2'}],['wrong-cache-key',{...cache,key:'wrong'}],['missing-cache-result',{cacheVersion:cache.cacheVersion,key:cache.key}],['null-cache-result',{...cache,result:null}],['malformed-cache','{bad']]){await writeFile(cacheFile,typeof entry==='string'?entry:JSON.stringify(entry));await observe(name,async()=>state(await api.discoverWorkspace(cl,{adapterRegistry:registry,writeCache:false})));}
record('builtins',{ids:createDefault().ids(),fresh:createDefault()!==createDefault(),adapterFresh:createDefault().get('prisma')!==createDefault().get('prisma')});
// Node writes lone UTF-16 units as replacement characters in text files.
const unicodeRoot=join(base,'unicode');await mkdir(unicodeRoot);const ul=makeLoaded(unicodeRoot,{...cc,outputs:{...cc.outputs,graph:'nested/\ud800-graph.json'}});const u=await api.discoverWorkspace(ul,{adapterRegistry:registry,useCache:false,writeCache:false});await api.writeWorkspaceOutputs(ul,u);record('unicode-output-files',await files(unicodeRoot));
const normalized=JSON.parse(JSON.stringify(observations).split(base).join('<ROOT>'));
console.log(JSON.stringify({observations:normalized,calls}));
''')
commands=[]
def execute(name,args):
    result=subprocess.run([str(x) for x in args],cwd=work,env={**os.environ,'PATH':''},capture_output=True,timeout=240)
    (output/(name+'.stdout')).write_bytes(result.stdout);(output/(name+'.stderr')).write_bytes(result.stderr)
    commands.append({'name':name,'command':[str(x) for x in args],'exitCode':result.returncode})
    assert result.returncode==0,(name,result.returncode,result.stderr.decode(errors='replace')[-2400:])
    return json.loads(result.stdout)
reference=execute('reference',[NODE,script,'reference',ORACLE,work/'reference',native])
verify_tree()
# Save the complete original observations before the candidate can execute.
(output/'frozen-original.json').write_text(json.dumps(reference['observations'],indent=2,ensure_ascii=True)+'\n')
candidate=execute('candidate',[NODE,script,'candidate',ORACLE,work/'candidate',native])
assert len(reference['observations'])==len(candidate['observations'])
differences=[{'name':e['name'],'expected':e,'observed':a} for e,a in zip(reference['observations'],candidate['observations']) if e!=a]
assert all(c['command'][0]==str(native) and not c['processError'] and not c['signal'] for c in candidate['calls'])
required=['assemble','cache-key','cache-check','cache-entry','resolve','read-json','write-file','check','outputs','has-errors','adapter-registry']
for op in required:
    assert any(c['command'][1:4]==['legacy','workspace','json'] and json.loads(c['input'])['operation']==op for c in candidate['calls']),op
engine=json.loads(subprocess.check_output([native,'engine']))
assert engine=={'documentType':'executor-description','schemaVersion':'0.1.0',**identities(ROOT)}
receipt={'schemaVersion':'1.0.0','status':'matched' if not differences else 'different','referenceEngine':SUPPLEMENT['referenceEngine'],'originalTreeFilesVerified':len(SUPPLEMENT['referenceTree']),'driverDigest':sha(Path(__file__).read_bytes()),'scriptDigest':sha(script.read_bytes()),'frozenOriginalDigest':sha((output/'frozen-original.json').read_bytes()),'candidate':{'binaryDigest':sha(native.read_bytes()),'engine':engine,'sourceInventory':[{'path':p.relative_to(ROOT).as_posix(),'digest':sha(p.read_bytes())} for folder in ['sdk/typescript','adapters/discovery'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file()]},'installedPackages':sorted(p.name for p in (work/'node_modules').iterdir()),'tooling':tooling,'counts':{'observations':len(reference['observations']),'matched':len(reference['observations'])-len(differences),'differences':len(differences),'nativeCalls':len(candidate['calls'])},'commands':commands,'retainedWork':str(work),'differences':differences,'scope':'Complete JSON-visible results, caller hooks, cache behavior and every output byte for retained pipeline/custom/Unicode fixtures. Finite controls; not full filesystem/platform or workspace acceptance.'}
(output/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+'\n')
(ROOT/'.tools/parity/current-workspace-workflow.json').write_text(json.dumps({'receipt':(output/'receipt.json').relative_to(ROOT).as_posix()})+'\n')
print(json.dumps({'receipt':str(output/'receipt.json'),'counts':receipt['counts'],'differences':[d['name'] for d in differences]}))
assert not differences,'Workspace differs from frozen original'
