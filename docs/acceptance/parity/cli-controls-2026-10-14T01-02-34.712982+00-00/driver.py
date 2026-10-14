"""Freeze real original CLI streams/file effects before installed comparison."""
import base64,hashlib,json,os,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
from storage_guard import ensure_guarded, node_runtime
from retained_copy import copy_tree,copy_file,install_discovery_tools
from identity import identities
ensure_guarded()
ROOT=Path(__file__).resolve().parents[2];NODE=node_runtime()
ORACLE=ROOT/json.loads((ROOT/'.tools/parity/oracles/current.json').read_text())['source']
SPEC=json.loads((ROOT/'fixtures/parity/supplement.json').read_text())
sha=lambda b:'sha256:'+hashlib.sha256(b).hexdigest()
def verify():
 for f in SPEC['referenceTree']:
  b=(ORACLE/f['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==f['gitBlob'],f['path']
verify()
freeze='--freeze' in os.sys.argv
out=ROOT/'docs/acceptance/parity'/('cli-controls-'+datetime.now(timezone.utc).isoformat().replace(':','-'));out.mkdir(parents=True)
work=Path(tempfile.mkdtemp(prefix='patamaps-cli-controls-'))
expanded='--expanded' in os.sys.argv
corpus_path=ROOT/'fixtures/parity'/('cli-expanded-controls.json' if expanded else 'cli-controls.json')
core=json.loads((ORACLE/'dist/relation-packs/core.json').read_text()) if (ORACLE/'dist/relation-packs/core.json').exists() else json.loads((ROOT/'crates/patamaps-core/src/legacy_core.json').read_text())
graph={'schemaVersion':'2.0.0','id':'urn:test:cli','namespace':'test','relationPacks':[{'id':core['id'],'version':core['version']}],'entities':[{'id':'urn:test:c','kind':'concept','label':'C'},{'id':'urn:test:a','kind':'artifact','label':'A'},{'id':'urn:test:b','kind':'artifact','label':'B'}],'mappings':[{'id':'urn:test:m','relation':'core:references','sources':['urn:test:c'],'targets':['urn:test:a'],'cardinality':'one-to-one','lossiness':'unknown'}],'authorities':[{'id':'urn:test:authority','concept':'urn:test:c','source':'urn:test:a','facts':['*'],'mode':'canonical'}]}
after=json.loads(json.dumps(graph));after['entities'][1]['label']='changed'
config={'schemaVersion':'1.0.0','id':'urn:test:cli:workspace','namespace':'test','repository':'fixture','repositoryRoot':'.','sources':[{'id':'db','adapter':'prisma','path':'schema.prisma'},{'id':'schemas','adapter':'typescript-zod','roots':['schemas']}],'correspondences':[{'id':'item','source':{'sourceId':'schemas','kind':'schema','name':'itemSchema'},'target':{'sourceId':'db','kind':'model','name':'Item'},'fields':{'pairs':[{'source':'id','target':'id'}]},'authority':{'side':'target','facts':['type']}}],'outputs':{'graph':'generated/graph.json','snapshot':'generated/snapshot.json','report':'generated/report.md','documentation':'generated/graph.md','cache':'.cache/metamap'},'policy':{'baselineChanges':'error','unconfiguredStructures':'ignore'}}
legacy={'description':'old catalog','sourcesOfTruth':[{'id':'source','label':'Source','paths':['src/main.rs'],'outputs':['generated/api.ts'],'updateSteps':'build'},{'id':'ambiguous','label':'Ambiguous','paths':['a OR b','src/*.rs'],'outputs':['description'],'specDoc':'docs/spec.md','note':'check'}]}
base_files={'graph.json':json.dumps(graph),'after.json':json.dumps(after),'invalid.json':'{}','malformed.json':'{bad','pack.json':json.dumps(core),'invalid-pack.json':'{}','legacy.json':json.dumps(legacy),'config.json':json.dumps(config),'schema.prisma':'model Item {\n id String @id\n}\n','schemas/item.ts':'import { z } from "zod";\nexport const itemSchema = z.object({ id: z.string() });\n','occupied.json':'previous output'}
# Independent fixtures for errors/query/serialization; one retained sequence for cache/baseline behavior.
cases=[]
def add(name,args,files=None,group=None):cases.append({'name':name,'args':args,'files':base_files if files is None else files,'group':group or name})
add('empty',[]);add('unknown',['not-a-command'])
for command in ['validate','diff','trace','authority','generate','check','migrate-sources']:add(command+'-missing',[command])
for command in ['validate','diff','trace','authority']:
 add(command+'-unknown-option',[command,'--other'])
 add(command+'-pack-missing-value',[command,'--relation-pack'])
 add(command+'-pack-value-is-option',[command,'--relation-pack','--other'])
add('validate-valid',['validate','graph.json']);add('validate-invalid',['validate','invalid.json']);add('validate-extra',['validate','graph.json','after.json']);add('validate-missing-file',['validate','absent.json']);add('validate-malformed',['validate','malformed.json']);add('validate-pack',['validate','graph.json','--relation-pack','pack.json']);add('validate-repeated-pack',['validate','--relation-pack','pack.json','graph.json','--relation-pack','pack.json']);add('validate-invalid-pack',['validate','graph.json','--relation-pack','invalid-pack.json'])
for name,args in [('same',['graph.json','graph.json']),('changed',['graph.json','after.json']),('invalid-before',['invalid.json','graph.json']),('invalid-after',['graph.json','invalid.json']),('extra',['graph.json','after.json','invalid.json'])]:add('diff-'+name,['diff',*args])
for direction in ['incoming','outgoing','both','bad']:add('trace-'+direction,['trace','graph.json','urn:test:a',direction,'3'])
for depth in ['0','-1','x','1.5','+2','1e2','0x10','2tail','9999999999999999999999999999']:add('trace-depth-'+depth,['trace','graph.json','urn:test:c','both',depth])
add('trace-relation',['trace','graph.json','urn:test:c','both','3','core:references']);add('trace-no-relation',['trace','graph.json','urn:test:c','both','3','core:contains']);add('trace-extra',['trace','graph.json','urn:test:c','both','3','core:references','ignored']);add('trace-unknown-entity',['trace','graph.json','urn:test:missing']);add('trace-invalid-graph',['trace','invalid.json','urn:test:c'])
for name,args in [('resolved',['graph.json','urn:test:c','*']),('missing',['graph.json','urn:test:missing','type']),('extra',['graph.json','urn:test:c','*','other']),('invalid-graph',['invalid.json','urn:test:c','*'])]:add('authority-'+name,['authority',*args])
add('migrate-stdout',['migrate-sources','legacy.json']);add('migrate-file',['migrate-sources','legacy.json','out.json']);add('migrate-overwrite',['migrate-sources','legacy.json','occupied.json']);add('migrate-no-parent',['migrate-sources','legacy.json','absent/out.json']);add('migrate-invalid',['migrate-sources','invalid.json']);add('migrate-extra',['migrate-sources','legacy.json','out.json','ignored']);add('migrate-malformed',['migrate-sources','malformed.json'])
add('generate-first',['generate','config.json'],group='pipeline');add('generate-cache',['generate','config.json'],group='pipeline');add('check-clean',['check','config.json'],group='pipeline');add('generate-no-cache',['generate','config.json','--no-cache'],group='pipeline');add('generate-unknown-second',['generate','config.json','--other','ignored'],group='pipeline')
add('check-no-baseline',['check','config.json']);add('check-no-cache',['check','config.json','--no-cache']);add('generate-missing-file',['generate','absent.json']);add('generate-invalid-config',['generate','invalid.json'])
error_config=json.loads(json.dumps(config));error_config['sources']=[{'id':'not-installed','adapter':'unregistered'}];error_files={**base_files,'config.json':json.dumps(error_config)};add('generate-unregistered',['generate','config.json'],error_files);add('check-unregistered',['check','config.json'],error_files)
warning_graph=json.loads(json.dumps(graph));warning_graph['authorities'].append({'id':'urn:test:authority:b','concept':'urn:test:c','source':'urn:test:b','facts':['*'],'mode':'canonical'});add('authority-ambiguous',['authority','graph.json','urn:test:c','*'],{**base_files,'graph.json':json.dumps(warning_graph)})
unicode_graph=json.loads(json.dumps(graph));unicode_graph['entities'][0]['label']='\ud800\ue000';add('unicode-graph',['validate','graph.json'],{**base_files,'graph.json':json.dumps(unicode_graph)})
if expanded:
 cases=[]
 provenance={'status':'declared','assertedBy':'fixture'}
 for field in ['mappings','authorities']:
  for row in graph[field]:row['provenance']=provenance
 after=json.loads(json.dumps(graph));after['entities'][1]['label']='changed'
 base_files={**base_files,'graph.json':json.dumps(graph),'after.json':json.dumps(after)}
 add('valid-graph',['validate','graph.json']);add('valid-pack',['validate','graph.json','--relation-pack','pack.json']);add('diff-identical-valid',['diff','graph.json','graph.json']);add('diff-changed-valid',['diff','graph.json','after.json'])
 for direction in ['incoming','outgoing','both']:add('valid-trace-'+direction,['trace','graph.json','urn:test:a',direction,'3'])
 for depth in ['0','-1','x','1.5','+2','1e2','0x10','2tail','9999999999999999999999999999']:add('valid-trace-depth-'+depth,['trace','graph.json','urn:test:c','both',depth])
 add('valid-trace-relation',['trace','graph.json','urn:test:c','both','3','core:references']);add('valid-trace-no-relation',['trace','graph.json','urn:test:c','both','3','core:contains']);add('valid-trace-extra',['trace','graph.json','urn:test:c','both','3','core:references','ignored']);add('valid-trace-unknown',['trace','graph.json','urn:test:missing'])
 add('resolved-authority',['authority','graph.json','urn:test:c','*']);add('absent-authority',['authority','graph.json','urn:test:missing','type'])
 ambiguous=json.loads(json.dumps(graph));ambiguous['authorities'].append({'id':'urn:test:authority:b','concept':'urn:test:c','source':'urn:test:b','facts':['*'],'mode':'canonical','provenance':provenance});add('ambiguous-authority',['authority','graph.json','urn:test:c','*'],{**base_files,'graph.json':json.dumps(ambiguous)})
 unicode=json.loads(json.dumps(graph));unicode['entities'][0]['label']='\ud800\ue000';unicode_after=json.loads(json.dumps(unicode));unicode_after['entities'][0]['label']='replacement';add('unicode-diff-valid',['diff','graph.json','after.json'],{**base_files,'graph.json':json.dumps(unicode),'after.json':json.dumps(unicode_after)})
 drift_config=json.loads(json.dumps(config));drift_config['correspondences'][0]['fields']['pairs']=[{'source':'missing','target':'id'}];add('generate-refusal-report',['generate','config.json'],{**base_files,'config.json':json.dumps(drift_config)})
 add('generate-baseline',['generate','config.json'],group='baseline-drift');add('check-baseline-clean',['check','config.json'],group='baseline-drift')
 # Subsequent source edits remain explicit inputs in the frozen record.
 add('check-baseline-drift',['check','config.json'],group='baseline-drift');cases[-1]['updates']={'schemas/item.ts':'import { z } from "zod";\nexport const itemSchema = z.object({ id: z.number() });\n'}
trace=work/'native.ndjson';bootstrap=work/'trace.mjs';bootstrap.write_text(r'''
import cp from 'node:child_process';import {appendFileSync} from 'node:fs';import {syncBuiltinESMExports} from 'node:module';
const exe=process.env.PATAMAPS_TEST_NATIVE,trace=process.env.PATAMAPS_TEST_TRACE;
const log=(command,input,result)=>appendFileSync(trace,JSON.stringify({command,input,exitCode:result.status,signal:result.signal,stdout:result.stdout??'',stderr:result.stderr??'',processError:result.error?.message??null})+'\n');
const sync=cp.spawnSync;cp.spawnSync=function(file,args,options){const r=sync.call(this,file,args,options);if(file===exe)log([file,...args],options?.input??null,r);return r;};
const spawn=cp.spawn;cp.spawn=function(file,args,options){const p=spawn.call(this,file,args,options);if(file===exe){let input='',stdout='',stderr='';const end=p.stdin.end.bind(p.stdin);p.stdin.end=function(chunk,...rest){if(chunk)input+=chunk.toString();return end(chunk,...rest)};p.stdout.on('data',x=>stdout+=x.toString());p.stderr.on('data',x=>stderr+=x.toString());p.on('close',(status,signal)=>log([file,...args],input,{status,signal,stdout,stderr}));}return p;};
const exec=cp.execFile;cp.execFile=function(file,args,options,callback){return exec.call(this,file,args,options,(error,stdout,stderr)=>{if(file===exe)log([file,...args],null,{status:error?.code??0,signal:error?.signal??null,stdout,stderr,error:typeof error?.code==='string'?error:null});callback(error,stdout,stderr)});};
syncBuiltinESMExports();
''')
candidate_entry=work/'traced-entry.mjs'
candidate_entry.write_text("process.env.PATAMAPS_TEST_NATIVE="+json.dumps(str(work/'patamaps'))+";process.env.PATAMAPS_TEST_TRACE="+json.dumps(str(trace))+";await import("+json.dumps(bootstrap.as_uri())+");await import("+json.dumps((work/'node_modules/patamaps-native-sdk-draft/cli.mjs').as_uri())+");\n")
commands=[]
def run_cases(mode,rows):
 results=[];created=set()
 for case in rows:
  root=work/mode/case['group']
  if case['group'] not in created:
   root.mkdir(parents=True)
   for name,text in case['files'].items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode())
   created.add(case['group'])
  for name,text in case.get('updates',{}).items():(root/name).write_bytes(text.encode())
  cmd=[NODE,ORACLE/'dist/cli.js',*case['args']] if mode=='reference' else [work/'patamaps','legacy','run','--node',NODE,'--entry',candidate_entry,'--',*case['args']]
  env={**os.environ,'PATH':'','PATAMAPS_TEST_NATIVE':str(work/'patamaps'),'PATAMAPS_TEST_TRACE':str(trace)}
  r=subprocess.run(list(map(str,cmd)),cwd=root,env=env,capture_output=True,timeout=90)
  normal=lambda s:s.replace(str(root),'<ROOT>')
  files={p.relative_to(root).as_posix():base64.b64encode(p.read_bytes()).decode() for p in sorted(root.rglob('*')) if p.is_file()}
  observed={'exitCode':r.returncode,'stdout':normal(r.stdout.decode(errors='replace')),'stderr':normal(r.stderr.decode(errors='replace')),'files':files}
  (out/(mode+'-'+case['name']+'.json')).write_text(json.dumps(observed,indent=2)+'\n');results.append({'name':case['name'],'expected' if mode=='reference' else 'observed':observed});commands.append({'mode':mode,'case':case['name'],'command':list(map(str,cmd)),'exitCode':r.returncode})
 return results
if freeze:
 assert not corpus_path.exists(),'Frozen expectations must not be overwritten'
 reference=run_cases('reference',cases);verify()
 corpus={'schemaVersion':'1.0.0','referenceEngine':SPEC['referenceEngine'],'scope':'Exact original process statuses/streams and every retained file byte for seven CLI workflows. JSON files/array order and cache/output side effects are not normalized. Absolute owned fixture roots alone are normalized in diagnostic streams. Finite fixtures do not prove complete commands or platforms.','referenceDriverDigest':sha(Path(__file__).read_bytes()),'cases':[{**c,'expected':e['expected']} for c,e in zip(cases,reference)]}
 corpus_path.write_text(json.dumps(corpus,indent=2,ensure_ascii=True)+'\n');receipt={'status':'frozen-original','cases':len(cases),'corpusDigest':sha(corpus_path.read_bytes()),'commands':commands,'retainedWork':str(work)}
else:
 corpus=json.loads(corpus_path.read_bytes());assert corpus['referenceEngine']==SPEC['referenceEngine'];cases=corpus['cases']
 copy_tree(ROOT/'sdk/typescript',work/'node_modules/patamaps-native-sdk-draft');copy_tree(ROOT/'adapters/discovery',work/'node_modules/patamaps-discovery-draft');tooling=install_discovery_tools(ORACLE,work/'node_modules');copy_file(ROOT/'target/debug/patamaps',work/'patamaps')
 candidate=run_cases('candidate',cases);verify();diffs=[{'name':c['name'],'expected':c['expected'],'observed':o['observed']} for c,o in zip(cases,candidate) if c['expected']!=o['observed']]
 calls=[json.loads(line) for line in trace.read_text().splitlines()];assert calls and all(c['command'][0]==str(work/'patamaps') for c in calls)
 engine=json.loads(subprocess.check_output([work/'patamaps','engine']));assert all(engine[k]==v for k,v in identities(ROOT).items())
 receipt={'schemaVersion':'1.0.0','status':'matched' if not diffs else 'different','referenceEngine':SPEC['referenceEngine'],'driverDigest':sha(Path(__file__).read_bytes()),'corpus':{'path':corpus_path.relative_to(ROOT).as_posix(),'digest':sha(corpus_path.read_bytes())},'candidate':{'binaryDigest':sha((work/'patamaps').read_bytes()),'engine':engine,'sourceInventory':[{'path':p.relative_to(ROOT).as_posix(),'digest':sha(p.read_bytes())} for folder in ['sdk/typescript','adapters/discovery'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file()]},'counts':{'cases':len(cases),'matched':len(cases)-len(diffs),'differences':len(diffs),'nativeExecutions':len(calls)},'differences':diffs,'installedPackages':sorted(p.name for p in (work/'node_modules').iterdir()),'tooling':tooling,'commands':commands,'retainedWork':str(work),'scope':corpus['scope']}
 (out/'native-executions.ndjson').write_bytes(trace.read_bytes());(out/'driver.py').write_bytes(Path(__file__).read_bytes());(out/'bootstrap.mjs').write_bytes(bootstrap.read_bytes())
(out/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+'\n');(ROOT/('.tools/parity/current-cli-expanded-controls.json' if expanded else '.tools/parity/current-cli-controls.json')).write_text(json.dumps({'receipt':(out/'receipt.json').relative_to(ROOT).as_posix()})+'\n')
print(json.dumps({'status':receipt['status'],'receipt':str(out/'receipt.json'),'counts':receipt.get('counts',{'cases':receipt.get('cases')}),'differences':[r['name'] for r in receipt.get('differences',[])]}),flush=True)
if not freeze:assert not diffs,'CLI differs from frozen original'
