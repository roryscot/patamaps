"""Retain declared disagreements as controls, never normalize them into parity."""
import argparse,json,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ENGINE='399747a4ad05a37cd8db1cedd53048fad2175be4'
p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('--node',type=Path,required=True);p.add_argument('--cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
def run(argv,cwd,expected=0):
 result=subprocess.run([str(a)for a in argv],cwd=cwd,capture_output=True,text=True);assert result.returncode==expected,result.stdout+result.stderr;return result.stdout
with tempfile.TemporaryDirectory(prefix='patamaps-differences-') as directory:
 work=Path(directory);checkout=work/'reference';checkout.mkdir();archive=work/'reference.tar'
 run(['git','-C',args.reference,'archive',ENGINE,'--output',archive],ROOT)
 with tarfile.open(archive)as tar:tar.extractall(checkout,filter='data')
 (checkout/'node_modules').symlink_to(args.reference.resolve()/'node_modules',target_is_directory=True)
 run([args.node,checkout/'node_modules/typescript/lib/tsc.js','-p','tsconfig.build.json'],checkout)
 legacy=json.loads(run([args.node,'--input-type=module','-e',"import{pathToFileURL}from'node:url';const root=process.argv[1];const{hydratePathTree}=await import(pathToFileURL(root+'/dist/path-tree.js'));const{verifyEd25519Signature}=await import(pathToFileURL(root+'/dist/governance.js'));const signature=Buffer.alloc(64);signature[0]=1;console.log(JSON.stringify({D005:hydratePathTree({_: '/users/:longname/:id'}, {longname:':id',id:'literal'})._,firstProbe:hydratePathTree({_: '/users/:id/:next'}, {id:':next',next:'literal'})._,D006:verifyEd25519Signature(Buffer.from('negative control'),Buffer.from('302a300506032b65700321000100000000000000000000000000000000000000000000000000000000000000','hex').toString('base64'),signature.toString('base64'))}));",checkout],ROOT))
 graph={'schemaVersion':'0.1.0','documentType':'graph','id':'urn:difference:graph','namespace':'difference','revision':'1','entities':[{'id':'urn:difference:route','kind':'route','attributes':{'path':'/users/:longname/:id'}}],'mappings':[],'authorities':[]}
 policy={'schemaVersion':'0.1.0','documentType':'policy','id':'urn:difference:policy','graph':{'id':graph['id'],'revision':'1'},'mappings':[],'constraints':[],'evidence':[]}
 spec={'schemaVersion':'0.1.0','documentType':'projection-spec','id':'urn:difference:spec','consumer':'urn:difference:consumer','select':{'ids':['urn:difference:route']},'slots':[],'pathTree':{}}
 import base64
 weak_key=base64.b64encode(bytes.fromhex('302a300506032b65700321000100000000000000000000000000000000000000000000000000000000000000')).decode()
 trust={'schemaVersion':'0.1.0','documentType':'trusted-consumer','mode':'governed','id':'urn:difference:trust','revision':'1','consumer':'urn:difference:consumer','environment':'test','principals':[{'id':'owner','role':'owner','revoked':False}],'keys':[{'id':'owner-key','principal':'owner','algorithm':'Ed25519','publicKey':weak_key,'validFrom':'2026-10-10T00:00:00.000Z','validUntil':'2026-10-10T08:00:00.000Z','revoked':False}],'grants':[]}
 for name,value in [('graph',graph),('policy',policy),('spec',spec),('parameters',{'longname':':id','id':'literal'}),('trust',trust)]:
  (work/(name+'.json')).write_text(json.dumps(value))
 actual_tree=json.loads(run([args.cli.resolve(),'path-tree','graph.json','policy.json','spec.json','--as-of','2026-10-10T01:00:00Z','--parameters','parameters.json'],work))
 actual_path=actual_tree['tree']['users'][':longname'][':id']['_']
 run([args.cli.resolve(),'capture','graph.json','policy.json','--spec','spec.json','--as-of','2026-10-10T01:00:00Z','-o','capture.json'],work)
 weak_refusal=json.loads(run([args.cli.resolve(),'propose','capture.json','--trust','trust.json','--consumer','urn:difference:consumer','--environment','test','--proposer','agent'],work,1))
 assert legacy['D005']=='/users/literal/literal'and actual_path=='/users/:id/literal'
 assert legacy['D006']is True and any(i['code']=='GOVERNANCE_INVALID_CRYPTO'for i in weak_refusal['issues'])
 report={'engineRevision':ENGINE,'referenceNode':run([args.node,'--version'],ROOT).strip(),'initialProbe':{'path':'/users/:id/:next','parameters':{'id':':next','next':'literal'},'referenceActual':legacy['firstProbe'],'successorActual':'/users/:next/literal','disposition':'This probe did not distinguish the implementations. The reference replaces longer tokens first; the final D005 control inserts a shorter token from a longer token value.'},'controls':[{'id':'D005','referenceExpected':'/users/literal/literal','successorExpected':'/users/:id/literal','referenceActual':legacy['D005'],'successorActual':actual_path,'pass':True},{'id':'D006','referenceLibrarySignatureExpected':True,'successorTrustKeyExpected':'GOVERNANCE_INVALID_CRYPTO','referenceLibrarySignatureActual':legacy['D006'],'successorRefusal':weak_refusal,'pass':True}],'inputs':{'graph':graph,'policy':policy,'spec':spec,'trust':trust},'successorHydration':actual_tree,'claim':'Intentional successor changes; these disagreements are retained, not counted as shared-profile equivalence.'}
 args.output.write_text(json.dumps(report,indent=2)+'\n')
 print('PASS: D005 literal hydration and D006 weak-key refusal against isolated pinned reference; complete controls retained in '+str(args.output))
