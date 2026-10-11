"""Run with the separately installed, version-pinned SSSOM/RDF environment.

No upstream checker patches or disabled validation categories. Network access is
refused during checks; official JSON-LD context bytes are substituted offline.
"""
import argparse, copy, csv, hashlib, io, json, os, socket, sys
from importlib.metadata import version
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('PYSTOW_HOME',str(ROOT/'.tools/scientific-checker-cache'))
def offline(*args,**kwargs):raise AssertionError('Independent checks attempted network access')
socket.socket.connect=offline
socket.create_connection=offline
from sssom.parsers import parse_sssom_table, _check_redefined_builtin_prefixes
from sssom.validators import validate
from sssom.constants import SchemaValidationType
from rdflib import Graph, URIRef, Namespace
import yaml
p=argparse.ArgumentParser();p.add_argument('artifacts',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
pins={'sssom':'0.4.17','sssom-schema':'1.0.0','rdflib':'7.1.4'}
for k,v in pins.items():assert version(k)==v,(k,version(k))
files=['source.tsv','default.sssom.tsv','condensed.sssom.tsv'];results=[]
expected=[SchemaValidationType.JsonSchema,SchemaValidationType.PrefixMapCompleteness,SchemaValidationType.StrictCurieFormat]
for file in files:
    table=parse_sssom_table(str(a.artifacts/file));checks=validate(table,validation_types=expected,fail_on_error=True)
    assert len(table.df)==7 and set(checks)==set(expected)
    assert all(not report.results for report in checks.values())
    results.append({'file':file,'records':len(table.df),'categories':[str(v) for v in checks],'status':'passed'})
def independent_rows(path):
    source=path.read_text();lines=source.splitlines(keepends=True);metadata=[]
    while lines and lines[0].startswith('#'):metadata.append(lines.pop(0)[1:])
    raw=''.join(metadata);indent=len(raw.splitlines()[0])-len(raw.splitlines()[0].lstrip(' '))
    parsed=yaml.safe_load('\n'.join(line[indent:] for line in raw.splitlines()))
    return parsed,list(csv.reader(io.StringIO(''.join(lines)),delimiter='\t'))
raw=independent_rows(a.artifacts/'source.tsv');default=independent_rows(a.artifacts/'default.sssom.tsv')
assert raw==default,'Independent metadata/header/decoded-cell preservation failed'
try:parse_sssom_table(str(a.artifacts/'source.tsv'),strict=True)
except ValueError as e:
    strict={'status':'failed-known-upstream-defect','message':str(e)}
    assert 'non-standard and undefined metadata' in str(e)
else:raise AssertionError('Pinned strict parser defect changed; investigate without weakening expectation')
bad=parse_sssom_table(str(a.artifacts/'source.tsv'));bad.df.loc[0,'subject_id']='UNDECLARED:entity'
try:validate(bad,validation_types=expected,fail_on_error=True)
except Exception as e:unknown={'status':'rejected','exception':type(e).__name__,'message':str(e)}
else:raise AssertionError('Independent checker accepted unknown prefix')
collision=copy.deepcopy(raw[0]);collision['curie_map']['skos']='https://wrong.invalid/'
assert _check_redefined_builtin_prefixes(collision,{},None) is False
package=json.loads((a.artifacts/'crate.json').read_text());metadata=package['metadata'];payloads=package['files']
pin=json.loads((ROOT/'fixtures/scientific/ro-crate-context-pin.json').read_text());context=(ROOT/'fixtures/scientific/ro-crate-1.2-context.jsonld').read_bytes()
assert hashlib.sha256(context).hexdigest()==pin['sha256'] and len(context)==pin['byteLength']
assert metadata['@context']==pin['url'] and payloads['ro-crate-context.jsonld'].encode()==context
nodes={e['@id']:e for e in metadata['@graph']};assert len(nodes)==len(metadata['@graph'])
assert nodes['./']['@type']=='Dataset' and nodes['./']['datePublished']=='2026-10-10'
assert nodes['ro-crate-metadata.json']['conformsTo']['@id']=='https://w3id.org/ro/crate/1.2'
parts={p['@id'] for p in nodes['./']['hasPart']};assert parts==set(payloads)
for path,text in payloads.items():
    node=nodes[path];assert node['@type']=='File' and node['sha256']==hashlib.sha256(text.encode()).hexdigest()
    assert node['contentSize']==str(len(text.encode()))
offline_metadata=copy.deepcopy(metadata);offline_metadata['@context']=json.loads(context)['@context']
base='https://example.invalid/scientific-crate/';rdf=Graph().parse(data=json.dumps(offline_metadata),format='json-ld',publicID=base)
schema=Namespace('http://schema.org/');rdf_type=URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
assert (URIRef(base),rdf_type,schema.Dataset) in rdf
assert (URIRef(base+'ro-crate-metadata.json'),URIRef('http://purl.org/dc/terms/conformsTo'),URIRef('https://w3id.org/ro/crate/1.2')) in rdf
for path in payloads:
    assert (URIRef(base+path),rdf_type,schema.MediaObject) in rdf
    assert str(next(rdf.objects(URIRef(base+path),schema.sha256)))==nodes[path]['sha256']
report={'environment':{'python':sys.version,'pinned':pins},'sssom':results,'defaultExportIndependentCellsAndMetadata':'preserved','unknownPrefix':unknown,'builtInCollisionPredicate':'rejected','strictParser':strict,'rdf':{'status':'passed','triples':len(rdf),'payloads':len(payloads),'contextPin':pin,'inventory':'complete-bytes-and-RDF-correspondence','scope':'closed Patamaps scientific profile; not universal RO-Crate conformance'},'network':'forbidden-during-checks','scientificTruth':'not-established'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: independent pinned SSSOM validation of source and both exports, metadata/cells, prefix controls, offline RDF/RO-Crate inventory. Known strict-parser defect retained.')
