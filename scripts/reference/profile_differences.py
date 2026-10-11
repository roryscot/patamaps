"""Predeclared stricter source/capture bounds, never normalized into parity."""
import argparse,copy,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('--node',type=Path,required=True);p.add_argument('--cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.cli=a.cli.resolve()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def run(argv,cwd,expected=0):
    r=subprocess.run([str(x)for x in argv],cwd=cwd,capture_output=True,text=True,timeout=90);assert r.returncode==expected,(r.returncode,r.stdout,r.stderr);return r.stdout
with tempfile.TemporaryDirectory(prefix='patamaps-profile-differences-')as temporary:
    work=Path(temporary);prefix='#mapping_set_id: urn:sssom:large\n#license: https://creativecommons.org/publicdomain/zero/1.0/\n#curie_map:\n# EX: https://example.org/\nsubject_id\tpredicate_id\tobject_id\tmapping_justification\tcomment\nEX:A\tskos:exactMatch\tEX:B\tsemapv:ManualMappingCuration\t';raw=(prefix+'x'*(16777217-len(prefix)-1)+'\n').encode();assert len(raw)==16777217;(work/'large.tsv').write_bytes(raw)
    code='import{readFileSync}from"node:fs";import{pathToFileURL}from"node:url";const{parseSssomTsv,interpretSssomDocument}=await import(pathToFileURL(process.argv[1]+"/dist/sssom.js"));const d=parseSssomTsv(readFileSync(process.argv[2]));const i=interpretSssomDocument(d);console.log(JSON.stringify({status:"source-parsed",rows:d.rows.length,records:i.records.length,commentLength:d.rows[0][4].length}));'
    original=json.loads(run([a.node,'--input-type=module','-e',code,a.reference.resolve(),work/'large.tsv'],work));assert original['records']==1
    write(work/'source.json',{'id':'large','namespace':'difference','sourceRevision':'1'})
    native=json.loads(run([a.cli,'sssom','import','large.tsv','--source-config','source.json'],work,1));assert any(i['code']=='INVALID_CANONICAL_VALUE' and i['message']=='INPUT_BYTE_LIMIT: input exceeds 16777216 bytes' for i in native['issues']),native
    original_capture=json.loads((ROOT/'docs/acceptance/scientific-native/capture.json').read_text());sources=copy.deepcopy(original_capture['sources']);sources[0].pop('content');inputs=original_capture['inputs']
    for name,v in [('graph',inputs['graph']),('policy',inputs['policy']),('spec',inputs['projectionSpec']),('context',inputs['context']),('receipts',sources),('pack',inputs['packs'][0])]:write(work/(name+'.json'),v)
    missing=json.loads(run([a.cli,'capture','graph.json','policy.json','--spec','spec.json','--context','context.json','--relation-pack','pack.json','--source-receipts','receipts.json','--as-of',inputs['evaluatedAt']],work));assert missing['result']['status']=='viable';write(work/'missing.json',missing)
    replay=json.loads(run([a.cli,'replay','missing.json'],work));assert replay['status']=='verified'
    crate_result=subprocess.run([str(x) for x in [a.cli,'sssom','crate','missing.json',ROOT/'docs/acceptance/scientific-native/crate-options.json']],cwd=work,capture_output=True,text=True,timeout=90)
    assert crate_result.returncode==2 and 'SCIENTIFIC_CRATE_REPLAY' in crate_result.stderr,(crate_result.returncode,crate_result.stdout,crate_result.stderr)
    refusal={'exitCode':crate_result.returncode,'stdout':crate_result.stdout,'stderr':crate_result.stderr}
    report={'engines':json.loads(run([a.cli,'engine'],work)),'controls':[{'id':'D007','expectedReference':'source-parsed','expectedSuccessor':'16 MiB input refusal','inputBytes':len(raw),'inputDigest':'sha256:'+hashlib.sha256(raw).hexdigest(),'generator':'One well-formed SSSOM record with an ASCII comment padded to 16 MiB + 1; template retained in profile_differences.py','reference':original,'successor':native,'pass':True},{'id':'D009','expectedSuccessor':'SCIENTIFIC_CRATE_REPLAY','capture':missing,'replay':replay,'crateRefusal':refusal,'pass':True,'scope':'Native complete-capture requirement; old partial-crate mode is intentionally not implemented'}],'claim':'Intentional stricter limits and complete-source profile; no shared-profile equivalence claim'}
a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,report)
print('PASS: D007 explicit 16 MiB source refusal against original valid control, and D009 missing-source crate refusal despite a valid replay.')
