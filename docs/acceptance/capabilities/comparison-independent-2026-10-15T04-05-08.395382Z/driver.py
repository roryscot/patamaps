from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
require='--require-complete' in sys.argv
cli=ROOT/'target/debug/patamaps'
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('comparison-independent-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
work=Path(tempfile.mkdtemp(prefix='comparison-independent-',dir=ROOT/'.tools/capabilities'))
def digest(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
commands=[]
report={'status':'running','requireComplete':require,'scope':'Independent native CLI diagnostic controls; no activation or unique causal attribution.','retainedWork':work.relative_to(ROOT).as_posix(),'binaryDigest':digest(cli),'commands':commands,'deleted':[]}
def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(label,args):
 p=subprocess.run([str(cli),*map(str,args)],capture_output=True,cwd=ROOT,env={**os.environ,'PATH':'/usr/bin:/bin'})
 for stream in ['stdout','stderr']:(out/(label+'.'+stream+'.log')).write_bytes(getattr(p,stream))
 commands.append({'label':label,'argv':[str(cli),*map(str,args)],'exitCode':p.returncode,'stdoutDigest':digest(out/(label+'.stdout.log')),'stderrDigest':digest(out/(label+'.stderr.log'))});save()
 try:value=json.loads(p.stdout)
 except ValueError:value=None
 return p.returncode,value
try:
 graph=json.loads((ROOT/'fixtures/routing/graph.json').read_bytes());policy=json.loads((ROOT/'fixtures/routing/policy.json').read_bytes());spec=json.loads((ROOT/'fixtures/routing/projection-spec.json').read_bytes())
 subject=next(e['id'] for e in graph['entities'] if e['kind']=='routing:command')
 def cap(label,g=graph,p=policy,s=spec):
  directory=work/label;directory.mkdir()
  second=json.loads(json.dumps(s));second['id']='urn:comparison:second'
  for name,value in [('graph',g),('policy',p),('spec',s),('second-spec',second)]: (directory/(name+'.json')).write_text(json.dumps(value)+'\n')
  path=directory/'capture.json'
  code,_=run(label+'-capture',['capture',directory/'graph.json',directory/'policy.json','--spec',directory/'spec.json','--spec',directory/'second-spec.json','--relation-pack',ROOT/'relation-packs/core.json','--relation-pack',ROOT/'relation-packs/routing.json','--as-of','2026-10-10T12:00:00Z','--output',path]);assert code==0
  code,v=run(label+'-replay',['replay',path]);assert code==0 and v['status']=='verified'
  return path
 base=cap('base');assert json.loads(base.read_bytes())['result']['status']=='viable'
 duplicate=json.loads(json.dumps(graph));duplicate['entities'].append(duplicate['entities'][0]);bad=cap('duplicate',g=duplicate);assert json.loads(bad.read_bytes())['result']['status']=='rejected'
 code,dup=run('duplicate-compare',['compare',base,bad]);report['duplicateComparisonAvailable']=code==0
 if code==0:assert dup['graphIdentityMode']=='occurrence-aware' and dup['admittedPathsAfter']['status']=='unavailable'
 else:assert code==1 and any(i['code']=='DUPLICATE_DIFF_ID' for i in dup['issues'])
 changed=json.loads(json.dumps(spec));changed['slots'][0]['targetKinds']=['unavailable-kind'];candidate=cap('consumer',s=changed)
 code,consumer=run('consumer-compare',['compare',base,candidate]);assert code==0
 report['consumerOriginsAvailable']=subject in consumer.get('diagnosticOrigins',{}).get('subjects',[])
 changed_policy=json.loads(json.dumps(policy));changed_policy['evidence'].append({'id':'urn:comparison:evidence','subjects':[subject],'kind':'test-observation','result':'supports','producer':'urn:comparison:producer'})
 p=cap('policy',p=changed_policy);code,pol=run('policy-compare',['compare',base,p]);assert code==0
 report['policyOriginsAvailable']=subject in pol.get('diagnosticOrigins',{}).get('subjects',[])
 code,explicit=run('explicit-compare',['compare',base,base,'--origin',subject]);report['explicitDiagnosticAvailable']=code==0
 if code==0:assert not explicit['changes'] and subject in explicit['diagnosticOrigins']['subjects'] and explicit['admittedPathsAfter']['status']=='available'
 if require:assert all(report[k] for k in ['duplicateComparisonAvailable','consumerOriginsAvailable','policyOriginsAvailable','explicitDiagnosticAvailable'])
 assert digest(cli)==report['binaryDigest']
 report.update(status='passed',engines=json.loads(subprocess.check_output([cli,'engine'])),allControlsRequireComplete=require)
except BaseException as e:report.update(status='failed',error=type(e).__name__+': '+str(e));raise
finally:save();print(json.dumps({'receipt':str(out/'receipt.json'),**{k:v for k,v in report.items() if isinstance(v,(bool,str))}}),flush=True)
