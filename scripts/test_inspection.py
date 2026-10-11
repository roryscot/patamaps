"""Exercise native inspection/repair commands in an isolated writable workspace."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CLI=Path(sys.argv[1]).resolve()
destination=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
def invoke(args):
 p=subprocess.run([str(CLI),*args],cwd=work,capture_output=True,check=True)
 return p.stdout
def write(name,value):
 path=work/name;path.write_text(json.dumps(value));return str(path)
with tempfile.TemporaryDirectory(prefix='patamaps-inspection-') as directory:
 work=Path(directory)
 graph=json.loads((ROOT/'fixtures/routing/graph.json').read_text());policy=json.loads((ROOT/'fixtures/routing/policy.json').read_text());spec=json.loads((ROOT/'fixtures/routing/projection-spec.json').read_text())
 graph['entities'][0]['label']='<img src=x onerror=alert(1)>'
 target=graph['mappings'][0]['targets'][0];graph['mappings'][0]['targets']=['urn:handler:missing']
 spec['consumer']='urn:consumer:inspection'
 for name,value in [('graph.json',graph),('policy.json',policy),('spec.json',spec)]:write(name,value)
 invoke(['capture','graph.json','policy.json','--spec','spec.json','--relation-pack',str(ROOT/'relation-packs/routing.json'),'--as-of','2026-10-10T00:00:00Z','-o','capture.json'])
 baseline=json.loads((work/'capture.json').read_text());assert baseline['result']['status']=='rejected'
 write('mapping.json',graph['mappings'][0]);mapping_bytes=invoke(['canonical','mapping.json']).removesuffix(b'\n');digest='sha256:'+hashlib.sha256(mapping_bytes).hexdigest()
 request={'schemaVersion':'0.1.0','documentType':'repair-request','baseline':baseline,'consumer':spec['consumer'],'allowedFacts':[{'subject':'*','fact':'*'}],'protectedFacts':[],
  'edits':[{'id':'select-handler','semanticCost':1,'operation':{'kind':'select-target','mappingIndex':0,'expectedDigest':digest,'target':target}}],
  'bounds':{'maximumCandidates':100,'maximumEdits':2,'maximumDerivationDepth':128,'maximumElapsedMilliseconds':60000,'maximumWorkUnits':2000000}}
 write('request.json',request)
 report=json.loads(invoke(['repair','request.json']));assert report['status']=='complete';assert report['coverage']['examined']==1;assert len(report['proposals'])==1;assert report['applied'] is False;assert report['attempts'][0]['authorization']=='approval-required'
 assert report['attempts'][0]['candidate']['result']['status']=='viable'
 cancelled=json.loads(invoke(['repair','request.json','--cancel-after-ms','0']));assert cancelled['status']=='incomplete';assert cancelled['coverage']['examined']==0;assert 'WORK_CANCELLED' in cancelled['coverage']['stopReasons']
 write('candidate.json',report['attempts'][0]['candidate'])
 selection=graph['entities'][0]['id']
 explanation=json.loads(invoke(['inspect','capture.json','--subject',selection]));assert explanation['record']['admission']=='rejected';assert explanation['record']['approval']['status']=='not-evaluated'
 html=invoke(['inspect','capture.json','--subject',selection,'--html']).decode();assert '<img' not in html and '&lt;img' in html and '<script' not in html
 before=(work/'graph.json').read_bytes();assert json.loads(before)==graph
 if destination:
  destination.mkdir(parents=True,exist_ok=True)
  (destination/'inspection-rejected.html').write_text(html)
  (destination/'inspection-viable.html').write_bytes(invoke(['inspect','candidate.json','--before','capture.json','--subject',selection,'--html']))
  (destination/'inspection-native.json').write_text(json.dumps({'scope':'native read-only CLI; Linux activation not attempted','checks':['useful finite repair','explicit approval required','cooperative CLI cancellation','source input unchanged','rejected/viable shared report','escaped script-free HTML'],'repair':report,'explanation':explanation},indent=2)+'\n')
 print('PASS: native finite repair, approval requirement, cancellation, unchanged sources, and escaped rejected/viable debugger artifacts.')
