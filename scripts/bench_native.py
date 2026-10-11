"""Fixed-seed native routing workload/refusal measurements, without speed claims."""
import argparse, copy, hashlib, json, os, platform, random, subprocess, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--build-profile',choices=['release','development','unspecified'],default='unspecified');a=p.parse_args();a.cli=a.cli.resolve()
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def encoded(v):return (json.dumps(v,separators=(',',':'),ensure_ascii=False)+'\n').encode()
seed=20261010;records=[];env={**os.environ,'PATH':'/usr/bin:/bin'}
with tempfile.TemporaryDirectory(prefix='patamaps-benchmark-') as directory:
    work=Path(directory)
    for n in [1000,10000,100000]:
        rng=random.Random(seed);entities=[];mappings=[]
        for i in range(n):
            s=f'urn:bench:command:{i}';t=f'urn:bench:handler:{i}'
            entities.extend([{'id':s,'kind':'routing:command','label':f'fixed-{rng.getrandbits(32)}'},{'id':t,'kind':'routing:handler'}])
            mappings.append({'id':f'urn:bench:mapping:{i}','relation':'routing:handled_by','sources':[s],'targets':[t],'cardinality':'one-to-one','lossiness':'lossless','provenance':{'status':'declared','assertedBy':'benchmark-fixture'}})
        graph={'schemaVersion':'0.1.0','documentType':'graph','id':'urn:bench:graph','namespace':'benchmark','revision':'1','entities':entities,'mappings':mappings,'authorities':[]}
        policy={'schemaVersion':'0.1.0','documentType':'policy','id':'urn:bench:policy','graph':{'id':graph['id'],'revision':'1'},'mappings':[{'select':{'relations':['routing:handled_by']},'coverage':'total','determinism':'deterministic','reversibility':'irreversible'}],'constraints':[],'evidence':[]}
        graph_bytes=encoded(graph);policy_bytes=encoded(policy);(work/'graph.json').write_bytes(graph_bytes);(work/'policy.json').write_bytes(policy_bytes)
        # Expected behavior follows the published byte bound, before measuring.
        expected='controlled-refusal-input-limit' if len(graph_bytes)>16777216 else 'viable'
        trials=[]
        for trial in range(3):
            argv=[str(a.cli),'compile','graph.json','policy.json','--relation-pack',str(ROOT/'relation-packs/routing.json'),'--as-of','2026-10-10T00:00:00Z']
            start=time.perf_counter();r=subprocess.run(argv,cwd=work,env=env,capture_output=True,timeout=120);elapsed=time.perf_counter()-start
            result=json.loads(r.stdout);actual='viable' if r.returncode==0 else 'controlled-refusal-input-limit' if any(i['code']=='INVALID_JSON' and 'input exceeds' in i['message'].lower() for i in result.get('issues',[])) else 'other-rejection'
            if expected!='viable':
                assert r.returncode==1 and any('limit' in i['message'].lower() for i in result['issues']),result
                actual='controlled-refusal-input-limit'
            assert actual==expected,(n,actual,result)
            trials.append({'trial':trial,'wallSeconds':elapsed,'exitCode':r.returncode,'stdoutBytes':len(r.stdout),'stdoutDigest':digest(r.stdout),'stderr':r.stderr.decode(),'status':actual})
        records.append({'mappings':n,'entities':2*n,'graphBytes':len(graph_bytes),'graphDigest':digest(graph_bytes),'policyDigest':digest(policy_bytes),'expected':expected,'trials':trials})
report={'profile':'native simple routing, complete admission; not proof/repair/lifecycle throughput','seed':seed,'host':platform.platform(),'architecture':platform.machine(),'binary':{'path':str(a.cli),'bytes':a.cli.stat().st_size,'digest':digest(a.cli.read_bytes())},'engine':json.loads(subprocess.check_output([str(a.cli),'engine'])),'buildProfile':a.build_profile,'buildProvenance':'Caller-declared profile; binary hash and source identity are not build attestation','measurement':'wall time for fresh CLI process, strict parsing, graph checks, admission and JSON output; cold/warm filesystem cache not separated','workloads':records,'comparison':'No TypeScript timing baseline; no speed or memory advantage established','nativeRuntime':'Node absent from PATH'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: fixed-seed 1k/10k native routing workloads and predeclared 100k byte-limit refusal, three trials each; timings bound to binary and inputs.')
