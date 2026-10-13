"""Retain actual boundary inputs, native/oracle executions and exact comparisons."""
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from identity import identities
from storage_guard import ensure_guarded

ensure_guarded()

ROOT = Path(__file__).resolve().parents[2]
NODE = Path('/Users/admin/.nvm/versions/node/v22.16.0/bin/node')
binary = ROOT / 'target/debug/patamaps'
oracle = ROOT / json.loads((ROOT/'.tools/parity/oracles/current.json').read_text())['source']
rules_path = ROOT/'fixtures/parity/scientific-bound-rules.json'
rules = json.loads(rules_path.read_text())
maximum = rules['bounds']['inputBytes']
# Retained Base64 requests and native outputs need more than the input limit.
# This reserve only governs the runner; it does not reduce accepted inputs.
minimum_free_bytes = 768 * 1024 * 1024
free_bytes = shutil.disk_usage(ROOT).free
if free_bytes < minimum_free_bytes:
    print(json.dumps({'status':'environment-blocked','reason':'insufficient-storage',
                      'availableBytes':free_bytes,'minimumFreeBytes':minimum_free_bytes,
                      'originalCasesClosed':0,'executedCases':0}),flush=True)
    raise SystemExit(75)
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
output = ROOT/'docs/acceptance/parity'/f'scientific-bounds-{stamp}'
output.mkdir(parents=True)
run = Path(tempfile.mkdtemp(prefix='scientific-bounds-',dir=ROOT/'.tools/parity/runs'))
sha = lambda raw: 'sha256:' + hashlib.sha256(raw).hexdigest()
request_store = ROOT/'.tools/parity/requests'
request_store.mkdir(parents=True, exist_ok=True)

def retain_request(name, request):
    """Keep complete bytes at each run path without multiplying identical data."""
    raw = json.dumps(request,separators=(',',':')).encode('utf-8')
    digest = sha(raw)
    shared = request_store/(digest.removeprefix('sha256:')+'.json')
    path = run/f'{name}.request.json'
    if not shared.exists():
        retained = ROOT/'.tools/parity/runs/scientific-bounds-9u1t97oo'/path.name
        if (retained.is_file() and not retained.is_symlink()
                and retained.stat().st_size == len(raw)
                and sha(retained.read_bytes()) == digest):
            os.link(retained,shared)
        else:
            with path.open('xb') as file:
                file.write(raw)
            os.link(path,shared)
    if (shared.is_symlink() or not shared.is_file()
            or shared.stat().st_size != len(raw)
            or sha(shared.read_bytes()) != digest):
        raise ValueError('Retained boundary request does not match generated input bytes')
    if not path.exists():
        os.link(shared,path)
    if not os.path.samefile(shared,path):
        raise ValueError('Boundary request paths do not share the verified input')
    return path,digest,shared

fixture = (ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv').read_bytes()
metadata = {'mapping_set_id':'https://example.test/set','license':'https://creativecommons.org/licenses/by/4.0/','curie_map':{'A':'https://example.test/A/','B':'https://example.test/B/'}}
columns = ['subject_id','predicate_id','object_id','mapping_justification']
row = ['A:1','skos:exactMatch','B:1','semapv:ManualMappingCuration']

def encoded(meta,cols,rows):
    return ('#'+json.dumps(meta,separators=(',',':'))+'\n'+'\t'.join(cols)+'\n'+''.join('\t'.join(v)+'\n' for v in rows)).encode()

def cases():
    yield 'licensed-source', fixture, None
    yield 'model-over-16-mib', encoded({**metadata,'mapping_set_description':'x'*(17*1024*1024)},columns,[row]), None
    line = b'#license: https://creativecommons.org/licenses/by/4.0/'
    assert line in fixture
    at = fixture.replace(line,line+b' #'+b'x'*(maximum-len(fixture)-2),1)
    assert len(at) == maximum
    yield 'input-at-64-mib',at,None
    yield 'input-over-64-mib',at+b' ',None
    body = ('\t'.join(columns)+'\n'+'\t'.join(row)+'\n').encode()
    small = ('mapping_set_id: https://example.test/set\nlicense: https://creativecommons.org/licenses/by/4.0/\ncurie_map: {A: https://example.test/A/, B: https://example.test/B/}\n#').encode()
    external = small+b'x'*(maximum-len(small))
    assert len(external) == maximum
    yield 'external-metadata-at-64-mib',body,external
    yield 'rows-at-limit',encoded(metadata,columns,[row]*50000),None
    yield 'rows-over-limit',encoded(metadata,columns,[row]*50001),None
    for count,name in [(256,'columns-at-limit'),(257,'columns-over-limit')]:
        extra=[f'ext_{i}' for i in range(count-len(columns))]
        meta={**metadata,'extension_definitions':[{'slot_name':v} for v in extra]}
        yield name,encoded(meta,columns+extra,[row+['']*len(extra)]),None

def observe(side,raw,exit_code):
    """Unstructured output and failed transports are not parser refusals."""
    try:
        value=json.loads(raw)
        if side=='reference':
            assert exit_code==0
            assert value['status'] in ['accepted','refused']
            if value['status']=='accepted':
                assert isinstance(value['canonicalDigest'],str)
                assert isinstance(value['rows'],int) and isinstance(value['columns'],int)
            else:
                assert isinstance(value['error']['code'],str)
                assert isinstance(value['error']['message'],str)
            return value
        if exit_code==0:
            assert raw.endswith(b'\n')
            return {'status':'accepted','canonicalDigest':sha(raw[:-1]),
                    'rows':len(value['rows']),'columns':len(value['columns'])}
        assert exit_code==1
        error=value['error']
        assert isinstance(error['code'],str) and isinstance(error['message'],str)
        return {'status':'refused','error':{'name':'SssomError','code':error['code'],'message':error['message']}}
    except (AssertionError,KeyError,TypeError,ValueError) as error:
        return {'status':'process-failed','reason':type(error).__name__,'detail':str(error),
                'stdoutBytes':len(raw),'exitCode':exit_code}

records=[]
completed=[]
failure=None
engine=None
environment={**os.environ,'PATH':''}
try:
    engine=json.loads(subprocess.check_output([binary,'engine']))
    assert all(engine[key]==value for key,value in identities(ROOT).items())
    for name,input_,metadata_ in cases():
        request={'input':base64.b64encode(input_).decode()}
        if metadata_ is not None: request['metadata']=base64.b64encode(metadata_).decode()
        path,request_digest,shared_path=retain_request(name,request)
        commands=[('reference',[str(NODE),str(ROOT/'scripts/parity/reference_sssom.mjs'),str(oracle),str(path)]),('candidate',[str(binary),'sssom','json','parse'])]
        outcomes={}
        for side,command in commands:
            stdout_path=run/f'{name}.{side}.stdout'
            stderr_path=run/f'{name}.{side}.stderr'
            with path.open('rb') as stdin,stdout_path.open('wb') as stdout,stderr_path.open('wb') as stderr:
                result=subprocess.run(command,stdin=stdin,stdout=stdout,stderr=stderr,env=environment,cwd=ROOT)
            raw=stdout_path.read_bytes()
            outcome=observe(side,raw,result.returncode)
            outcomes[side]=outcome
            records.append({'name':name,'side':side,'command':command,'exitCode':result.returncode,'outcome':outcome,
                            'requestDigest':request_digest,'requestPath':str(path.relative_to(ROOT)),
                            'sharedRequestPath':str(shared_path.relative_to(ROOT)),'requestStorage':'verified-hard-link',
                            'stdoutDigest':sha(raw),'stderrDigest':sha(stderr_path.read_bytes())})
            if outcome['status']=='process-failed':
                failure={'case':name,'side':side,'outcome':outcome,'stderrPath':str(stderr_path.relative_to(ROOT))}
                break
        if failure:
            break
        reference,candidate=outcomes['reference'],outcomes['candidate']
        equal=reference['status']==candidate['status'] and (reference==candidate if reference['status']=='accepted' else reference['error']['code']==candidate['error']['code'])
        records[-1]['capabilityEqual']=equal
        records[-1]['diagnosticEqual']=reference.get('error')==candidate.get('error')
        completed.append(name)
        print(json.dumps({'case':name,'equal':equal,'reference':reference['status'],'candidate':candidate['status']}),flush=True)
    if not failure:
        assert completed==rules['expectedInputs']
        assert all(engine[key]==value for key,value in identities(ROOT).items())
except (OSError,subprocess.SubprocessError,AssertionError,ValueError) as error:
    failure={'reason':type(error).__name__,'detail':str(error),'errno':getattr(error,'errno',None)}

comparisons=[record for record in records if record['side']=='candidate' and 'capabilityEqual' in record]
differences=[record['name'] for record in comparisons if not record['capabilityEqual']]
diagnostics=[record['name'] for record in comparisons if not record['diagnosticEqual']]
status='environment-failed' if failure else ('differences-observed' if differences else 'capabilities-matched')
receipt={'schemaVersion':'1.0.0','status':status,'rulesDigest':sha(rules_path.read_bytes()),
         'driverDigest':sha(Path(__file__).read_bytes()),'referenceEngine':'399747a4ad05a37cd8db1cedd53048fad2175be4',
         'candidate':{'binaryDigest':sha(binary.read_bytes()),'engine':engine},'host':{'platform':platform.platform(),'architecture':platform.machine()},
         'records':records,'completedInputs':completed,'expectedInputs':rules['expectedInputs'],'failure':failure,
         'capabilityDifferences':differences,'unresolvedDiagnostics':diagnostics,'originalCasesClosed':0,'retainedRun':str(run.relative_to(ROOT)),'scope':rules['scope']}
try:
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
except OSError as error:
    print(json.dumps({'status':'environment-failed','receiptWriteError':str(error),'partialReceipt':receipt}),flush=True)
    raise SystemExit(75)
print(json.dumps({'status':status,'receipt':str((output/'receipt.json').relative_to(ROOT)),
                  'completedInputs':completed,'capabilityDifferences':differences,'unresolvedDiagnostics':diagnostics,'failure':failure},indent=2),flush=True)
raise SystemExit(75 if failure else (1 if differences else 0))
