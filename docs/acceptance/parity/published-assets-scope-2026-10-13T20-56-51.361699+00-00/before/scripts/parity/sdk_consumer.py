"""Compile and execute a copied SDK/native subset outside the checkout."""
import re
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from identity import identities
from retained_copy import copy_file
from storage_guard import ensure_guarded

ensure_guarded()

ROOT = Path(__file__).resolve().parents[2]
NODE = Path('/Users/admin/.nvm/versions/node/v22.16.0/bin/node')
TSC = Path('/Users/admin/dev/SEEDZ/metamap/node_modules/typescript/lib/tsc.js')
binary = ROOT / 'target/debug/patamaps'
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
output = ROOT / 'docs/acceptance/parity' / f'sdk-consumer-{stamp}'
output.mkdir(parents=True)
stage = Path(tempfile.mkdtemp(prefix='patamaps-installed-sdk-', dir='/private/tmp'))
package = stage / 'node_modules/patamaps-native-sdk-draft'
package.mkdir(parents=True)
files = sorted((ROOT / 'sdk/typescript').glob('*.mjs')) + sorted((ROOT / 'sdk/typescript').glob('*.d.ts')) + [ROOT / 'sdk/typescript/package.json']
sha = lambda path: 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
inventory = [{'path': path.relative_to(ROOT).as_posix(), 'digest': sha(path)} for path in files]
reference_pointer = json.loads((ROOT / '.tools/parity/oracles/current.json').read_bytes())
reference = ROOT / reference_pointer['source']
supplement = json.loads((ROOT / 'fixtures/parity/supplement.json').read_bytes())
mapping_path = ROOT / 'fixtures/parity/legacy-pack-type-mapping.json'
type_mapping = json.loads(mapping_path.read_bytes())
graph_mapping_path = ROOT / 'fixtures/parity/legacy-graph-type-mapping.json'
graph_type_mapping = json.loads(graph_mapping_path.read_bytes())
reporting_mapping_path = ROOT / 'fixtures/parity/legacy-reporting-type-mapping.json'
reporting_type_mapping = json.loads(reporting_mapping_path.read_bytes())
correspondence_mapping_path = ROOT / 'fixtures/parity/legacy-correspondence-type-mapping.json'
correspondence_type_mapping = json.loads(correspondence_mapping_path.read_bytes())
config_mapping_path = ROOT / 'fixtures/parity/legacy-config-type-mapping.json'
config_type_mapping = json.loads(config_mapping_path.read_bytes())
workspace_mapping_path = ROOT / 'fixtures/parity/legacy-workspace-type-mapping.json'
workspace_type_mapping = json.loads(workspace_mapping_path.read_bytes())
migration_mapping_path = ROOT / 'fixtures/parity/legacy-migration-type-mapping.json'
migration_type_mapping = json.loads(migration_mapping_path.read_bytes())
evaluation_mapping_path = ROOT / 'fixtures/parity/legacy-evaluation-type-mapping.json'
evaluation_type_mapping = json.loads(evaluation_mapping_path.read_bytes())
viability_mapping_path = ROOT / 'fixtures/parity/legacy-viability-type-mapping.json'
viability_type_mapping = json.loads(viability_mapping_path.read_bytes())
type_rows = viability_type_mapping['rows'] + evaluation_type_mapping['rows'] + migration_type_mapping['rows'] + workspace_type_mapping['rows'] + config_type_mapping['rows'] + type_mapping['rows'] + graph_type_mapping['rows'] + reporting_type_mapping['rows'] + correspondence_type_mapping['rows']
assert type_mapping['referenceEngine'] == supplement['referenceEngine']

def verify_reference():
    for item in supplement['referenceTree']:
        raw = (reference / item['path']).read_bytes()
        assert hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() == item['gitBlob'], item['path']

verify_reference()
for item in type_rows:
    assert sha(reference / item['referenceModule']) == item['referenceSourceDigest']
for path in files:
    copy_file(path, package / path.name)
copy_file(ROOT / 'LICENSE', package / 'LICENSE')
copy_file(ROOT / 'NOTICE', package / 'NOTICE')
installed = stage / 'patamaps'
copy_file(binary, installed)
raw = (ROOT / 'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv').read_text()
legacy_file = stage / 'legacy-utf16-pack.json'
legacy_file.write_bytes(br'{"schemaVersion":"2.0.0","schemaVersion":"1.0.0","id":"urn:installed:file","version":"1","description":"\ud800","relations":[]}')
executable_duplicate_file = stage / 'executable-duplicate-pack.json'
executable_duplicate_file.write_bytes(br'{"schemaVersion":"1.0.0","description":"\ud800","\u0073chemaVersion":"2.0.0"}')
replacement_file = stage / 'legacy-utf8-replacement-pack.json'
replacement_file.write_bytes(b'{"schemaVersion":"1.0.0","id":"urn:installed:utf8","version":"1","relations":[],"description":"\xff"}')
legacy_expected_bytes = br'{"description":"\ud800","id":"urn:installed:file","relations":[],"schemaVersion":"1.0.0","version":"1"}' + b'\n'
digest_fixture = ROOT / 'fixtures/parity/digest-controls.json'
assert sha(digest_fixture) == 'sha256:b3738bc0f7c9816d6a4276e3eea40bb16d691889e9384facef62b55519a54b34'
digest_cases = {row['name']: row for row in json.loads(digest_fixture.read_bytes())['cases']}
digest_controls = ''
for name in ['case-order','numeric-keys','unpaired-forward','invalid-executable-shape']:
    case = digest_cases[name]
    digest_controls += f"if(legacy.digestLegacyRelationPack(JSON.parse({json.dumps(case['text'])})) !== {json.dumps(case['expected']['digest'])}) throw new Error('Installed unchecked digest mismatch: {name}');\n"
digest_controls += """let nullDigestRefused=false;
try { legacy.digestLegacyRelationPack(JSON.parse('null')); } catch(error) { nullDigestRefused=error instanceof TypeError && error.message === "Cannot read properties of null (reading 'schemaVersion')" && !('code' in error); }
if(!nullDigestRefused) throw new Error('Installed unchecked null digest dispatch mismatch');
"""
program = '''import {createCanonicalApi,createSssomApi,createLegacyValidationApi,SssomError,SSSOM_BUILTIN_PREFIXES,SSSOM_PROPAGATABLE_SLOTS,type SssomDocument,type SssomSourceConfig,type LegacyValidationResult} from "patamaps-native-sdk-draft";
const canonical = createCanonicalApi(__PATAMAPS_EXECUTABLE__);
if(canonical.canonicalJson({z:1,a:2}) !== '{"a":2,"z":1}') throw new Error('Canonical mismatch');
if(canonical.canonicalDigest({a:2,z:1}) !== 'sha256:PLACEHOLDER') throw new Error('Digest mismatch');
const science = createSssomApi(__PATAMAPS_EXECUTABLE__);
const config:SssomSourceConfig = science.parseSssomSourceConfig({id:'source',adapter:'sssom-tsv',path:'mapping.data',formatVersion:'1.0.0',sourceRevision:'r1',provenance:{nested:[1,true]}});
if(config.path !== 'mapping.data' || !Object.isFrozen(config.provenance?.nested)) throw new Error('Source config/immutability mismatch');
if(SSSOM_BUILTIN_PREFIXES.skos !== 'http://www.w3.org/2004/02/skos/core#' || !SSSOM_PROPAGATABLE_SLOTS.includes('subject_source') || !Object.isFrozen(SSSOM_PROPAGATABLE_SLOTS)) throw new Error('Scientific profile mismatch');
const source: SssomDocument = science.parseSssomTsv(__PATAMAPS_SSSOM_TEXT__);
if(source.rows.length !== 7 || !Object.isFrozen(source.rows[0])) throw new Error('Source/immutability mismatch');
if(science.interpretSssomDocument(source).records.length !== 7) throw new Error('Interpretation mismatch');
const exported = science.exportSssomTsv(source,{condense:true});
if(!exported.loss.semanticFieldsPreserved || exported.loss.byteIdentityPreserved || exported.loss.droppedFields.length) throw new Error('Export contract mismatch');
if(science.parseSssomTsv(exported.text).rows.length !== 7) throw new Error('Round trip mismatch');
if(science.expandSssomCurie('A:term',{A:'https://example.test/A/'}) !== 'https://example.test/A/term') throw new Error('CURIE mismatch');
let refused = false;
try { science.parseSssomTsv(new Uint8Array([0xff])); } catch(error) { refused = error instanceof SssomError && error.code === 'SSSOM_UTF8'; }
if(!refused) throw new Error('Wrong malformed-source refusal');
refused = false;
try { science.parseSssomSourceConfig({...config,formatVersion:'9'}); } catch(error) { refused = error instanceof SssomError && error.code === 'SSSOM_SOURCE_CONFIG'; }
if(!refused) throw new Error('Wrong invalid-config refusal');
const legacy = createLegacyValidationApi(__PATAMAPS_EXECUTABLE__);
const contextArray=[NaN,-0,Infinity];
const parsedContext=legacy.parseLegacyEvaluationContext({x:contextArray});
if(parsedContext.x!==contextArray || Object.isFrozen(parsedContext) || !legacy.evaluateLegacyContextExpression({key:'x',operator:'equals',value:NaN},parsedContext)) throw new Error('Installed context identity/numeric fact mismatch');
if(legacy.evaluateLegacyContextExpression({key:'x',operator:'equals',value:0},{x:-0}) || !legacy.evaluateLegacyContextExpression({key:'x',operator:'equals',value:-0},{x:-0})) throw new Error('Installed negative-zero context equality mismatch');
if([...legacy.requiredLegacyContextKeys({all:[{key:'b',operator:'equals',value:1},{key:'a',operator:'in',values:[]},{key:'b',operator:'equals',value:2},{key:'optional',operator:'exists'}]})].join(',')!=='b,a') throw new Error('Installed ordered context key mismatch');
if(legacy.legacyInactiveReason({when:{any:[]},unless:{all:[]}},{})!=='when-not-satisfied' || legacy.legacyInactiveReason(undefined,{})!==undefined) throw new Error('Installed context inactivity mismatch');
const prototypeInput=Object.fromEntries([['__proto__',[1]],['x',0]]);
if(Object.getPrototypeOf(legacy.parseLegacyEvaluationContext(prototypeInput))!==prototypeInput.__proto__) throw new Error('Installed parsed context prototype binding mismatch');
const graph = {schemaVersion:'2.0.0',id:'urn:installed:graph',namespace:'installed',relationPacks:[{id:'urn:metamap:relation-pack:core',version:'1.0.0'}],entities:[{id:'urn:installed:a',kind:'field'},{id:'urn:installed:b',kind:'field'}],mappings:[{id:'urn:installed:m',relation:'core:references',sources:['urn:installed:a'],targets:['urn:installed:b'],cardinality:'one-to-one',lossiness:'lossless',provenance:{status:'declared',assertedBy:'installed-consumer'}}],authorities:[]};
if(!legacy.legacySelectorMatches(graph.mappings[0] as import('patamaps-native-sdk-draft').LegacyStructuralMapping,{sourceKinds:['field'],targetKinds:['field']},new Map(graph.entities.map(e=>[e.id,e.kind])))) throw new Error('Installed selector mismatch');
const impact=legacy.analyzeLegacyImpact(graph as import('patamaps-native-sdk-draft').LegacyGraphDocument,{changedSubjects:['urn:installed:b']});
if(impact.paths.length!==3 || impact.paths.find(p=>p.subjectId==='urn:installed:a')?.path.join(',')!=='urn:installed:b,urn:installed:m,urn:installed:a') throw new Error('Installed original impact path mismatch');
const validated:LegacyValidationResult = legacy.validateLegacyDocument(graph);
if(!validated.valid || validated.issues.length || legacy.validateLegacyDocumentShape(graph).length) throw new Error('Legacy validation mismatch');
graph.mappings[0].targets = ['urn:installed:missing'];
const invalid = legacy.validateLegacyDocument(graph);
if(invalid.valid || invalid.issues.length !== 1 || invalid.issues[0].code !== 'UNRESOLVED_ENDPOINT' || invalid.issues[0].path !== '$.mappings[0].targets[0]' || invalid.issues[0].subjectId !== 'urn:installed:m') throw new Error('Legacy semantic diagnostic mismatch');
if(legacy.validateLegacyDocument(null).issues[0].code !== 'INVALID_DOCUMENT') throw new Error('Legacy shape diagnostic mismatch');
const portableInput = {schemaVersion:'1.0.0',id:'urn:installed:pack',version:'1',relations:[{id:'test:edge',cyclePolicy:'allow'}]};
const portable = legacy.parseLegacyRelationPack(portableInput);
if(portable !== portableInput) throw new Error('Pack parser changed caller identity');
__PATAMAPS_UNCHECKED_DIGEST_CONTROLS__
const migration = legacy.importLegacyRelationPack(portable);
if(migration.admitted || migration.registryValidated || migration.discardedPaths.length || migration.changes.length !== 2 || migration.originalDocumentDigest !== legacy.digestLegacyRelationPack(portable) || migration.nativeViewDigest === migration.originalDocumentDigest) throw new Error('Pack migration/address mismatch');
if(portable.schemaVersion !== '1.0.0' || migration.nativeView.schemaVersion !== '0.1.0') throw new Error('Pack envelope changed its original');
const customGraph = {...graph,relationPacks:[{id:portable.id,version:portable.version}],mappings:[{...graph.mappings[0],relation:'test:edge',targets:['urn:installed:b']}]};
if(!legacy.validateLegacyDocument(customGraph,{legacyPacks:[portable]}).valid) throw new Error('Portable pack registry mismatch');
if(legacy.validateLegacyDocument(customGraph,{legacyPacks:[]}).valid) throw new Error('Explicit empty portable registry was ignored');
refused = false;
try { legacy.parseLegacyRelationPack({...portable,newMandatoryFeature:true}); } catch(error) { refused = error instanceof Error && 'code' in error && error.code === 'LEGACY_PACK_SCHEMA'; }
if(!refused) throw new Error('Unsupported pack field was discarded');
const loading = legacy.loadLegacyRelationPack(__PATAMAPS_LEGACY_FILE__);
if(!(loading instanceof Promise)) throw new Error('File loading must remain asynchronous');
const loaded = await loading;
if(loaded.schemaVersion !== '1.0.0' || loaded.description !== String.fromCharCode(0xd800) || legacy.parseLegacyRelationPack(loaded) !== loaded) throw new Error('Legacy file data/identity mismatch');
if(legacy.digestLegacyRelationPack(loaded) !== __PATAMAPS_LEGACY_DIGEST__) throw new Error('UTF-16 original address mismatch');
refused = false;
try { legacy.importLegacyRelationPack(loaded); } catch(error) {
  refused = error instanceof Error && 'code' in error && error.code === 'LEGACY_NATIVE_UTF16' && 'report' in error && (error.report as {error:{issues:{path:string}[];originalDocumentDigest:string}}).error.issues[0].path === '/description' && (error.report as {error:{originalDocumentDigest:string}}).error.originalDocumentDigest === __PATAMAPS_LEGACY_DIGEST__;
}
if(!refused) throw new Error('Unpaired UTF-16 was silently altered for native import');
refused = false;
try { await legacy.loadLegacyRelationPack(__PATAMAPS_DUPLICATE_FILE__); } catch(error) { refused = error instanceof Error && 'code' in error && error.code === 'DUPLICATE_JSON_KEY'; }
if(!refused) throw new Error('Executable source duplicate was ignored');
const replacement = await legacy.loadLegacyRelationPack(__PATAMAPS_REPLACEMENT_FILE__);
if(replacement.description !== String.fromCharCode(0xfffd)) throw new Error('Legacy UTF-8 file replacement mismatch');
refused = false;
try { await legacy.loadLegacyRelationPack(__PATAMAPS_MISSING_FILE__); } catch(error) { refused = error instanceof Error && 'code' in error && error.code === 'ENOENT' && 'path' in error && error.path === __PATAMAPS_MISSING_FILE__; }
if(!refused) throw new Error('Missing file refusal mismatch');
'''.replace('__PATAMAPS_UNCHECKED_DIGEST_CONTROLS__', digest_controls).replace('__PATAMAPS_EXECUTABLE__', json.dumps(str(installed))).replace('__PATAMAPS_SSSOM_TEXT__', json.dumps(raw)).replace('PLACEHOLDER', hashlib.sha256(b'{"a":2,"z":1}').hexdigest()).replace('__PATAMAPS_LEGACY_FILE__', json.dumps(str(legacy_file))).replace('__PATAMAPS_LEGACY_DIGEST__', json.dumps('sha256:' + hashlib.sha256(legacy_expected_bytes).hexdigest())).replace('__PATAMAPS_DUPLICATE_FILE__', json.dumps(str(executable_duplicate_file))).replace('__PATAMAPS_REPLACEMENT_FILE__', json.dumps(str(replacement_file))).replace('__PATAMAPS_MISSING_FILE__', json.dumps(str(stage / 'missing-pack.json')))
program += '''
import type {LegacyPortableRelationPack,LegacyRelationLaw} from "patamaps-native-sdk-draft";
const readonlyPortable:LegacyPortableRelationPack = {schemaVersion:'1.0.0',id:'urn:installed:readonly-pack',version:'1',relations:[{id:'test:readonly-edge',cyclePolicy:'allow',sourceKinds:['field'] as const,cardinalities:['one-to-one'] as const}] as const};
if(legacy.parseLegacyRelationPack(readonlyPortable) !== readonlyPortable) throw new Error('Readonly pack parser identity mismatch');
const originalReverseDeclaration:LegacyRelationLaw = {id:'urn:law:readonly',operation:'reverse',operands:['test:readonly-edge'] as const,resultRelation:'test:readonly-edge',conditions:{middleKinds:['field'] as const},handling:{lossiness:'conservative',uncertainty:'conservative',authority:'none'}};
// This declaration matches the original type. Shape validation still refuses
// reverse middleKinds; type construction alone establishes no checked state.
if(originalReverseDeclaration.operands.length !== 1) throw new Error('Readonly law tuple mismatch');
'''
(stage / 'consumer.mts').write_text(program)
program += '''
import type {LegacyExecutableRelationPack} from "patamaps-native-sdk-draft";
const core=legacy.legacyCoreRelationPack;
const registry=new legacy.LegacyRelationRegistry();
if(registry.getPack(core.id)!==core || registry.get(core.relations[0].id)!==core.relations[0]) throw new Error('Default registry identity mismatch');
const executorPack:LegacyExecutableRelationPack={schemaVersion:'2.0.0',id:'urn:installed:executor',version:'1',imports:[{id:core.id,version:core.version,digest:legacy.digestLegacyRelationPack(core)}],relations:[],laws:[{id:'urn:installed:law',operation:'chain',operands:['core:contains','core:contains'],resultRelation:'core:contains',handling:{authority:'none',lossiness:'conservative',uncertainty:'conservative'}}]};
registry.registerPack(executorPack);
const registered=registry.getLaw('urn:installed:law');
if(!registered || registered.pack===executorPack || !Object.isFrozen(registered.law.operands) || registry.executablePacks()[0]!==registered.pack) throw new Error('Executable registry identity/freeze mismatch');
executorPack.description='caller changed';
if(registered.pack.description!==undefined || registry.allPacks().length!==2) throw new Error('Executable snapshot/order mismatch');
const live:LegacyPortableRelationPack=JSON.parse(JSON.stringify(core));
const driftRegistry=new legacy.LegacyRelationRegistry([live,executorPack]);
live.description='dependency drift';
let driftRefused=false;
try {driftRegistry.getLaw('urn:installed:law');} catch(error) {driftRefused=error instanceof Error && error.message.includes('Missing exact imported pack');}
if(!driftRefused) throw new Error('Dependency drift was not refused');
const lookupArray=registry.allPacks();lookupArray.length=0;
if(registry.allPacks().length!==2) throw new Error('Registry query array mutation changed registry');
'''
program += '''
import {LegacyGraphValidationError,type LegacyGraphDocument} from "patamaps-native-sdk-draft";
const queryDocument:LegacyGraphDocument={schemaVersion:'2.0.0',id:'urn:installed:query',namespace:'installed',entities:[{id:'urn:installed:a',kind:'field'},{id:'urn:installed:b',kind:'field'}],mappings:[{id:'urn:installed:q',relation:'core:references',sources:['urn:installed:a'],targets:['urn:installed:b'],cardinality:'one-to-one',lossiness:'lossless',provenance:{status:'declared',assertedBy:'installed-consumer'}}],authorities:[]};
const queries=new legacy.LegacyGraph(queryDocument,{registry});
if(queries.document!==queryDocument || queries.registry!==registry || queries.getEntity('urn:installed:a')!==queryDocument.entities[0] || queries.getMapping('urn:installed:q')!==queryDocument.mappings[0]) throw new Error('Graph lookup identity mismatch');
const trace=queries.trace('urn:installed:a',{direction:'outgoing',maxDepth:70});
for(const depth of [NaN,Infinity,-Infinity]) {
 const options=Object.freeze({maxDepth:depth});
 if(queries.trace('urn:installed:missing',options).length!==0)throw new Error('Missing start must precede depth validation');
 let depthRefused=false;
 try {queries.trace('urn:installed:a',options);}catch(error){depthRefused=error instanceof Error&&error.message==='maxDepth must be a non-negative integer';}
 if(!depthRefused)throw new Error('Non-finite trace depth did not reach native validation');
}
if(trace.length!==2 || trace[1].entity!==queryDocument.entities[1] || trace[1].viaMapping!==queryDocument.mappings[0] || queries.neighbors('urn:installed:a',{relations:[]}).length!==0) throw new Error('Graph traversal mismatch');
if(legacy.LegacyGraph.from(queryDocument,{registry}).document!==queryDocument || queries.resolveAuthority('urn:installed:a','type').status!=='unresolved') throw new Error('Graph factory or authority mismatch');
queryDocument.entities[0].id='urn:installed:renamed';
if(queries.getEntity('urn:installed:a')!==queryDocument.entities[0] || queries.getEntity('urn:installed:renamed')!==undefined) throw new Error('Graph retained key mismatch');
let validationRefused=false;
try {legacy.LegacyGraph.from(queryDocument,{registry,validate:false});} catch(error) {validationRefused=error instanceof LegacyGraphValidationError && error.issues.some(issue=>issue.code==='UNRESOLVED_ENDPOINT');}
if(!validationRefused) throw new Error('Graph from invalid refusal mismatch');
'''
program += '''
import {LegacyCompositionError,type LegacyCompositionOptions} from "patamaps-native-sdk-draft";
const left:LegacyGraphDocument={schemaVersion:'2.0.0',id:'urn:installed:left',namespace:'installed',entities:[{id:'urn:installed:a',kind:'field'}],mappings:[{id:'urn:installed:merged-edge',relation:'core:references',sources:['urn:installed:a'],targets:['urn:installed:b'],cardinality:'one-to-one',lossiness:'lossless',provenance:{status:'declared',assertedBy:'installed'}}],authorities:[]};
const right:LegacyGraphDocument={...left,id:'urn:installed:right',entities:[{id:'urn:installed:b',kind:'field'}],mappings:[]};
const compositionOptions:LegacyCompositionOptions={id:'urn:installed:merged',namespace:'installed'};
const merged=legacy.composeLegacyDocuments([left,right] as const,compositionOptions);
if(merged.entities[0]!==left.entities[0] || merged.entities[1]!==right.entities[0] || merged.mappings[0]!==left.mappings[0] || merged.entities===left.entities || !Object.hasOwn(merged,'label')) throw new Error('Composition retained identity/order/own properties mismatch');
if(new legacy.LegacyGraph(merged).validationIssues.length) throw new Error('Cross-shard validation mismatch');
const recomposed=legacy.composeLegacyDocuments([merged],{id:'urn:installed:recomposed',namespace:'installed'});
if(recomposed.entities[0]!==merged.entities[0] || recomposed.label!==undefined || !Object.hasOwn(recomposed,'label')) throw new Error('Recomposition optional-field/identity mismatch');
let compositionRefused=false;
try {legacy.composeLegacyDocuments([left,{...right,entities:[{id:left.entities[0].id,kind:'other'}]}],compositionOptions);} catch(error) {compositionRefused=error instanceof LegacyCompositionError && error.identifier===left.entities[0].id;}
if(!compositionRefused) throw new Error('Composition conflict error mismatch');
'''
reporting_fixture = ROOT / 'fixtures/parity/reporting-controls.json'
reporting_corpus = json.loads(reporting_fixture.read_bytes())
assert sha(reporting_fixture) == 'sha256:6374b76bcd45d9e47dee7d4ae59547d4aaccb18a10a20736946c9b3578d97d0e'
reporting_samples = [item for item in reporting_corpus['cases'] if item['name'] in ['changed-properties-ordinal','documentation-locale-ties-utf16-true','drift-grouping-adapter-31']]
assert len(reporting_samples) == 3
program += "\nimport {type LegacyGraphDiff,type LegacyReportInput} from \"patamaps-native-sdk-draft\";\n"
program += "const reportingSamples:Array<{name:string;action:{operation:string;before?:string;after?:string;graph?:string;correspondences?:string;input?:string};expected:unknown}>=" + json.dumps(reporting_samples,ensure_ascii=True) + ";\n"
program += '''
for(const test of reportingSamples) {
 const action=test.action; let observed:unknown;
 if(action.operation==='diff') {const result:LegacyGraphDiff=legacy.diffLegacyDocuments(JSON.parse(action.before!),JSON.parse(action.after!));observed=result;}
 else if(action.operation==='graph-documentation') observed=legacy.renderLegacyGraphDocumentation(JSON.parse(action.graph!),JSON.parse(action.correspondences!));
 else {const input:LegacyReportInput=JSON.parse(action.input!);observed=legacy.renderLegacyDriftReport(input);}
 if(JSON.stringify(observed)!==JSON.stringify(test.expected)) throw new Error('Installed reporting mismatch: '+test.name);
}
const emptyDiff:LegacyGraphDiff=legacy.emptyLegacyGraphDiff();emptyDiff.changes.push({change:'added',kind:'entity',id:'mutation'});
if(legacy.emptyLegacyGraphDiff().changes.length) throw new Error('Empty diff retained mutable state');
'''
correspondence_fixture = ROOT / 'fixtures/parity/correspondence-controls.json'
correspondence_corpus = json.loads(correspondence_fixture.read_bytes())
assert sha(correspondence_fixture) == 'sha256:3061410d68ab3fb14a4de5aaaa13088cf187302c5e1876c09c709303fe8df860'
correspondence_samples = [item for item in correspondence_corpus['cases'] if item['name'] in ['matching-fields-authority','explicit-arrays-and-transform','coverage-order-duplicates-and-stale-ignores']]
assert len(correspondence_samples) == 3
program += "\nimport {type LegacyCorrespondenceResult,type LegacyCorrespondenceConfig} from \"patamaps-native-sdk-draft\";\n"
program += "const correspondenceSamples=" + json.dumps(correspondence_samples,ensure_ascii=True) + ";\n"
program += '''
for(const test of correspondenceSamples){
 const input=JSON.parse(test.action.input);const configurations:LegacyCorrespondenceConfig[]=input.configurations;
 const result:LegacyCorrespondenceResult=legacy.materializeLegacyCorrespondences(input.namespace,input.documentId,input.discovered,configurations,input.configRevision);
 const value={document:result.document,issues:result.issues,configuredStructureIds:[...result.configuredStructureIds]};
 if(JSON.stringify(value)!==JSON.stringify(test.expected.value)) throw new Error('Installed correspondence mismatch: '+test.name);
 const records=[...result.document.entities,...result.document.mappings,...result.document.authorities];
 if(!records.every(record=>record.provenance===records[0].provenance)) throw new Error('Installed shared provenance mismatch');
 if(result.document.authorities[0].facts!==configurations[0].authority?.facts) throw new Error('Installed authority-facts identity mismatch');
 const pair=configurations[0].fields!.pairs[0];const fieldMapping=result.document.mappings.find(m=>m.attributes && Object.hasOwn(m.attributes,'comparedFacts'))!;
 if(pair.compare && fieldMapping.attributes!.comparedFacts!==pair.compare) throw new Error('Installed comparison-array identity mismatch');
 if(pair.allowDifferences && fieldMapping.attributes!.allowedDifferences!==pair.allowDifferences) throw new Error('Installed waiver-array identity mismatch');
 if(!(result.configuredStructureIds instanceof Set) || Object.keys(result.document.mappings[1]).join('|')!==test.expected.host.mappingKeys[1].join('|')) throw new Error('Installed Set/own-property order mismatch');
}
const identifier:unknown='urn:installed:identifier';if(!legacy.isLegacyReferenceIdentifier(identifier)) throw new Error('Identifier guard mismatch');const narrowedIdentifier:string=identifier;
if(!legacy.isLegacyRelationIdentifier('core:derives_from') || legacy.isLegacyRelationIdentifier('Core:maps')) throw new Error('Relation guard mismatch');
if(legacy.makeLegacyUrn('n','mapping','a /é')!=='urn:n:mapping:a%20%2F%C3%A9' || legacy.makeLegacyRepositoryUri('./a'+String.fromCharCode(92)+'b c','my/repo')!=='repo://my%2Frepo/a/b%20c') throw new Error('Installed URI mismatch');
if(!legacy.hasLegacyAmbiguousPathLanguage('a OR b') || !legacy.isLegacyPathPattern('a[0]')) throw new Error('Installed path predicate mismatch');
let uriRefused=false;try{legacy.makeLegacyUrn('n','mapping',String.fromCharCode(0xd800));}catch(error){uriRefused=error instanceof URIError && error.message==='URI malformed';}if(!uriRefused) throw new Error('Installed URIError mismatch');
'''
config_fixture = ROOT / 'fixtures/parity/config-controls.json'
config_corpus = json.loads(config_fixture.read_bytes())
assert sha(config_fixture) == 'sha256:8e8679fa88f457687ab06614a2e6b98d778cbd17af6257474a7682bafde30aed'
config_samples = [case for case in config_corpus['cases'] if case['name'] in ['minimal','all-adapters','complete-correspondence']]
assert len(config_samples) == 3
config_file = stage / 'workspace-config.json'
config_file.write_text(config_samples[0]['action']['input'])
program += '\nimport {type LegacyMetamapConfig,type LegacyLoadedMetamapConfig,type LegacyBuiltInSourceConfig} from "patamaps-native-sdk-draft";\n'
program += "const configSamples=" + json.dumps(config_samples,ensure_ascii=True) + ";\n"
program += '''
if(legacy.LEGACY_METAMAP_CONFIG_VERSION !== '1.0.0') throw new Error('Config version mismatch');
for(const test of configSamples){const value=JSON.parse(test.action.input);const result:LegacyMetamapConfig=legacy.parseLegacyMetamapConfig(value);if(result!==value || JSON.stringify(result)!==JSON.stringify(test.expected.value)) throw new Error('Installed config identity/value mismatch: '+test.name);}
const configLoading=legacy.loadLegacyMetamapConfig(__CONFIG_FILE__);if(!(configLoading instanceof Promise)) throw new Error('Config load must be asynchronous');
const loadedConfig:LegacyLoadedMetamapConfig=await configLoading;if(loadedConfig.configPath!==__CONFIG_FILE__ || loadedConfig.repositoryRoot!==__CONFIG_DIRECTORY__ || loadedConfig.configDirectory!==__CONFIG_DIRECTORY__) throw new Error('Installed resolved config paths mismatch');
let duplicateConfigRefused=false;try{const duplicate=JSON.parse(configSamples[0].action.input);duplicate.sources.push({...duplicate.sources[0]});legacy.parseLegacyMetamapConfig(duplicate);}catch(error){duplicateConfigRefused=error instanceof Error&&error.message==='Duplicate source id db'&&!('code' in error);}if(!duplicateConfigRefused) throw new Error('Installed config semantic refusal mismatch');
'''.replace('__CONFIG_FILE__',json.dumps(str(config_file))).replace('__CONFIG_DIRECTORY__',json.dumps(str(stage)))
program += """
import type {LegacyWorkspaceDiscovery,LegacyWorkspaceOptions,LegacyAdapterResult,LegacyMetamapAdapter} from "patamaps-native-sdk-draft";
const workspaceAdapter:LegacyMetamapAdapter={id:'custom',version:'1',async fingerprint(){return []},async discover(c,context){return {sourceId:c.id,adapter:'custom',adapterVersion:'1',inputs:[],document:{schemaVersion:'2.0.0',id:'urn:installed:workspace:shard',namespace:context.namespace,entities:[{id:'urn:installed:workspace:entity',kind:'concept'}],mappings:[],authorities:[]},diagnostics:[]}}};
const workspaceRegistry=new legacy.LegacyAdapterRegistry().register(workspaceAdapter);
const workspaceOptions:LegacyWorkspaceOptions={adapterRegistry:workspaceRegistry,useCache:false,writeCache:false};
const workspaceInput:LegacyAdapterResult=await workspaceAdapter.discover({id:'custom',adapter:'custom'},{namespace:'installed',repository:'fixture',repositoryRoot:'.'});
const workspaceConfig:LegacyMetamapConfig={schemaVersion:'1.0.0',id:'urn:installed:workspace',namespace:'installed',repository:'fixture',repositoryRoot:'.',sources:[{id:'custom',adapter:'custom'}],correspondences:[],outputs:{graph:'g',snapshot:'s',report:'r',documentation:'d'}};
const workspaceResult:LegacyWorkspaceDiscovery=legacy.assembleLegacyWorkspace(workspaceConfig,[workspaceInput],[],new legacy.LegacyRelationRegistry());
if(legacy.legacyWorkspaceHasErrors(workspaceResult)||workspaceResult.adapters[0]!==workspaceInput||workspaceResult.graph.entities[0]!==workspaceInput.document.entities[0]||workspaceResult.snapshot.sources[0].inputs!==workspaceInput.inputs)throw new Error('Installed workspace value or identity mismatch');
if(workspaceRegistry.require('custom').id!=='custom'||workspaceOptions.writeCache!==false)throw new Error('Installed custom adapter registry mismatch');
"""
program += """
import type {LegacySourceOfTruthDocument,LegacySourcesOfTruthResult,LegacyCliResult} from "patamaps-native-sdk-draft";
const legacyCatalog:LegacySourceOfTruthDocument={sourcesOfTruth:[{id:'catalog',label:'Catalog',paths:['src/a.rs'],outputs:['description']}]};
const legacyMigrated:LegacySourcesOfTruthResult=legacy.adaptLegacySourcesOfTruth(legacyCatalog);
if(!legacy.isLegacySourceOfTruthDocument(legacyCatalog)||legacyMigrated.document.authorities[0].mode!=='canonical'||!Object.hasOwn(legacyMigrated.document.entities[2],'locators')||legacyMigrated.document.entities[2].locators!==undefined||legacyMigrated.document.entities[0].provenance!==legacyMigrated.document.mappings[0].provenance)throw new Error('Installed migration value/identity/undefined mismatch');
if(!legacy.validateLegacyDocument(legacyMigrated.document).valid||legacy.validateLegacyDocumentShape(legacyMigrated.document).length!==0||!Object.hasOwn(legacyMigrated.document.entities[2],'locators'))throw new Error('Optional undefined graph fields changed or failed native validation');
const usageResult:LegacyCliResult=await legacy.runLegacyCli([]);
if(usageResult.exitCode!==2||usageResult.stdout!==''||!usageResult.stderr.startsWith('Usage:'))throw new Error('Installed native CLI planning mismatch');
"""
viability_fixture = ROOT / 'fixtures/parity/viability-controls.json'
assert sha(viability_fixture) == 'sha256:df246fe562839235f187e2f61e21a329d01c3e4f2c20d90c03d37c8191a464fc'
viability_baseline = next(row for row in json.loads(viability_fixture.read_bytes())['cases'] if row['name']=='baseline')
program += '''
import {configureLegacyValidation,compileLegacyMetamap,validateLegacyViabilityPolicy,validateLegacyViableGeneration,parseLegacyViabilityPolicy,parseLegacyViableGeneration,LEGACY_METAMAP_VIABILITY_POLICY_VERSION,LEGACY_METAMAP_GENERATION_VERSION} from "patamaps-native-sdk-draft";
import type {LegacyMetamapViabilityPolicy,LegacyCompileOptions,LegacyCompilationResult} from "patamaps-native-sdk-draft";
configureLegacyValidation(__PATAMAPS_EXECUTABLE__);
const v1Input=JSON.parse(__VIABILITY_INPUT__) as {document:LegacyGraphDocument;policy:LegacyMetamapViabilityPolicy;options:LegacyCompileOptions};
const v1Result:LegacyCompilationResult=compileLegacyMetamap(v1Input.document,v1Input.policy,v1Input.options);
if(JSON.stringify(v1Result)!==JSON.stringify(JSON.parse(__VIABILITY_EXPECTED__)))throw new Error('Installed direct v1 compiler full original output mismatch');
if(v1Result.status!=='viable')throw new Error('Installed v1 baseline did not compile');
if(!validateLegacyViabilityPolicy(v1Input.policy).valid||!validateLegacyViableGeneration(v1Result.generation).valid)throw new Error('Installed direct v1 validation mismatch');
if(parseLegacyViabilityPolicy(v1Input.policy)!==v1Input.policy||parseLegacyViableGeneration(v1Result.generation)!==v1Result.generation)throw new Error('Installed direct v1 parser identity mismatch');
if(v1Result.generation.context!==v1Input.options.context||!Object.isFrozen(v1Result.generation.context)||!Object.isFrozen(v1Result.generation.activeMappings))throw new Error('Installed v1 caller context identity/freeze mismatch');
if(LEGACY_METAMAP_VIABILITY_POLICY_VERSION!=='1.0.0'||LEGACY_METAMAP_GENERATION_VERSION!=='1.0.0')throw new Error('Installed original v1 version constant mismatch');
'''.replace('__PATAMAPS_EXECUTABLE__',json.dumps(str(installed))).replace('__VIABILITY_INPUT__',json.dumps(viability_baseline['action']['input'])).replace('__VIABILITY_EXPECTED__',json.dumps(json.dumps(viability_baseline['expected']['value'],separators=(',',':'))))
(stage / 'consumer.mts').write_text(program)
(stage / 'negative.mts').write_text('''import {createSssomApi,createCanonicalApi,createLegacyValidationApi} from "patamaps-native-sdk-draft";
createSssomApi('/absolute/path').parseSssomTsv({});
createSssomApi('/absolute/path').exportSssomTsv({}, {condense:'yes'});
createSssomApi('/absolute/path').expandSssomCurie(7,[]);
createCanonicalApi(7);
createLegacyValidationApi(7);
createLegacyValidationApi('/absolute/path').validateLegacyDocument({}, {nativePacks:'invalid'});
createLegacyValidationApi('/absolute/path').validateLegacyDocument({}, {registry:{}});
createLegacyValidationApi('/absolute/path').validateLegacyDocument({}, {legacyPacks:'invalid'});
createLegacyValidationApi('/absolute/path').validateLegacyDocument({}, {legacyPacks:[],nativePacks:[]});
createLegacyValidationApi('/absolute/path').importLegacyRelationPack({}).nativeView.schemaVersion = '1.0.0';
createLegacyValidationApi('/absolute/path').importLegacyRelationPack({}).admitted = true;
createLegacyValidationApi('/absolute/path').loadLegacyRelationPack(7);
createLegacyValidationApi('/absolute/path').loadLegacyRelationPack('/pack.json').relations;
createLegacyValidationApi('/absolute/path').parseLegacyRelationPack({}).relations.push({id:'test:edge',cyclePolicy:'allow'});
createLegacyValidationApi('/absolute/path').parseLegacyRelationPack({}).relations[0].sourceKinds?.push('other');
const executable = createLegacyValidationApi('/absolute/path').parseLegacyRelationPack({}); if(executable.schemaVersion === '2.0.0') executable.laws[0].operands[0] = 'other';
new (createLegacyValidationApi('/absolute/path').LegacyRelationRegistry)().getLaw(7);
new (createLegacyValidationApi('/absolute/path').LegacyRelationRegistry)().hasPack('pack',false);
new (createLegacyValidationApi('/absolute/path').LegacyRelationRegistry)('invalid');
new (createLegacyValidationApi('/absolute/path').LegacyRelationRegistry)().registerPack({});
new (createLegacyValidationApi('/absolute/path').LegacyGraph)({});
createLegacyValidationApi('/absolute/path').LegacyGraph.from({}, {validate:'false'});
createLegacyValidationApi('/absolute/path').LegacyGraph.from({}).trace('id',{direction:'sideways'});
createLegacyValidationApi('/absolute/path').LegacyGraph.from({}).neighbors('id',{relations:[7]});
createLegacyValidationApi('/absolute/path').LegacyGraph.from({}).resolveAuthority('id',7);
createLegacyValidationApi('/absolute/path').LegacyGraph.from({}).getEntity(7);
createLegacyValidationApi('/absolute/path').composeLegacyDocuments({}, {id:'id',namespace:'ns'});
createLegacyValidationApi('/absolute/path').composeLegacyDocuments([], {id:7,namespace:'ns'});
createLegacyValidationApi('/absolute/path').composeLegacyDocuments([], {id:'id'});
createLegacyValidationApi('/absolute/path').diffLegacyDocuments({},{});
createLegacyValidationApi('/absolute/path').emptyLegacyGraphDiff().changes.push({change:'unknown',kind:'entity',id:'id'});
createLegacyValidationApi('/absolute/path').renderLegacyDriftReport({});
createLegacyValidationApi('/absolute/path').renderLegacyGraphDocumentation({},[{id:7}]);
createLegacyValidationApi('/absolute/path').renderLegacyGraphDocumentation({} as any,'invalid');
createLegacyValidationApi('/absolute/path').materializeLegacyCorrespondences(7,'id',{} as any,[],'r');
createLegacyValidationApi('/absolute/path').materializeLegacyCorrespondences('n','id',{} as any,'invalid','r');
createLegacyValidationApi('/absolute/path').loadLegacyMetamapConfig(7);
createLegacyValidationApi('/absolute/path').loadLegacyMetamapConfig('/config.json').repositoryRoot;
const wrongConfigVersion:import('patamaps-native-sdk-draft').LegacyMetamapConfig['schemaVersion']='2.0.0';
const wrongConfigPolicy:import('patamaps-native-sdk-draft').LegacyMetamapPolicyConfig={baselineChanges:'silent'};
const wrongSourceRoots:import('patamaps-native-sdk-draft').LegacyTypeScriptZodSourceConfig={id:'i',adapter:'typescript-zod',roots:'src'};
const wrongCollection:import('patamaps-native-sdk-draft').LegacyJsonCollectionConfig={pointer:'/items',idProperty:'id'};
createLegacyValidationApi('/absolute/path').makeLegacyUrn('n','mapping',7);
createLegacyValidationApi('/absolute/path').makeLegacyRepositoryUri(7);
createLegacyValidationApi('/absolute/path').hasLegacyAmbiguousPathLanguage({});
createLegacyValidationApi('/absolute/path').isLegacyPathPattern(7);
createLegacyValidationApi('/absolute/path').materializeLegacyCorrespondences('n','id',{} as any,[{id:'c',source:{sourceId:'s',kind:'model',name:'S'},target:{sourceId:'t',kind:'model',name:'T'},authority:{side:'both',facts:[]}}],'r');
createLegacyValidationApi('/absolute/path').materializeLegacyCorrespondences('n','id',{} as any,[{id:'c',source:{sourceId:'s',kind:'model',name:'S'},target:{sourceId:'t',kind:'model',name:'T'},fields:{pairs:[{source:'s',target:'t',compare:['storage']}]}}],'r');
createLegacyValidationApi('/absolute/path').discoverLegacyWorkspace({config:7});
createLegacyValidationApi('/absolute/path').legacyWorkspaceHasErrors({validation:{valid:true}});
createLegacyValidationApi('/absolute/path').makeLegacyWorkspaceSnapshot({},[],7);
createLegacyValidationApi('/absolute/path').createDefaultLegacyAdapterRegistry().register({id:'bad',version:7});
createLegacyValidationApi('/absolute/path').checkLegacyWorkspace({} as import('patamaps-native-sdk-draft').LegacyLoadedMetamapConfig,{writeCache:'yes'});
createLegacyValidationApi('/absolute/path').adaptLegacySourcesOfTruth({sourcesOfTruth:[{id:'x',label:'X',paths:[7],outputs:[]}]});
createLegacyValidationApi('/absolute/path').adaptLegacySourcesOfTruth({sourcesOfTruth:[]},{namespace:7});
createLegacyValidationApi('/absolute/path').runLegacyCli([7]);
createLegacyValidationApi('/absolute/path').runLegacyCli([]).stdout;
createLegacyValidationApi('/absolute/path').evaluateLegacyContextExpression({key:'x',operator:'unknown',value:1},{});
createLegacyValidationApi('/absolute/path').evaluateLegacyContextExpression({key:'x',operator:'equals',value:1},{x:{nested:true}});
createLegacyValidationApi('/absolute/path').requiredLegacyContextKeys({all:7});
createLegacyValidationApi('/absolute/path').legacyInactiveReason({when:{any:[]}},[]);
createLegacyValidationApi('/absolute/path').legacySelectorMatches({} as import('patamaps-native-sdk-draft').LegacyStructuralMapping,{provenanceStatuses:['unknown']},new Map());
createLegacyValidationApi('/absolute/path').analyzeLegacyImpact({} as import('patamaps-native-sdk-draft').LegacyGraphDocument,{changedSubjects:[7]});
createLegacyValidationApi('/absolute/path').analyzeLegacyImpact({} as import('patamaps-native-sdk-draft').LegacyGraphDocument,{changedSubjects:[],activeMappings:[]});
const badViabilitySeverity:import('patamaps-native-sdk-draft').LegacyViabilitySeverity='fatal';
const badGenerationVersion:import('patamaps-native-sdk-draft').LegacyViableGeneration['schemaVersion']='2.0.0';
const badMappingCoverage:import('patamaps-native-sdk-draft').LegacyMappingCoverage='all';
createLegacyValidationApi('/absolute/path').compileLegacyMetamap({},{});
createLegacyValidationApi('/absolute/path').compileLegacyMetamap({} as import('patamaps-native-sdk-draft').LegacyGraphDocument,{} as import('patamaps-native-sdk-draft').LegacyMetamapViabilityPolicy,{evaluatedAt:7});
const badIssueMessage:import('patamaps-native-sdk-draft').LegacyViabilityIssue={severity:'warning',code:'X',message:7};
''')
environment = {**os.environ, 'PATH': ''}
commands = []

def run(label, command):
    result = subprocess.run(command, cwd=stage, env=environment, text=True, capture_output=True)
    (output / f'{label}.stdout.log').write_text(result.stdout)
    (output / f'{label}.stderr.log').write_text(result.stderr)
    commands.append({'name':label,'command':list(map(str,command)),'exitCode':result.returncode})
    return result

options = ['--strict','--module','NodeNext','--moduleResolution','NodeNext','--target','ES2022','--lib','ES2022']
reference_types = stage / 'reference-contracts'
reference_types.mkdir()
(reference_types / 'package.json').write_text('{"type":"module"}\n')
modules = sorted({item['referenceModule'] for item in type_rows})
modules = sorted(set(modules + ['src/relations.ts','src/graph.ts','src/composer.ts']))
reference_declarations = run('reference-type-declarations', [NODE,TSC,*[reference / name for name in modules],*options,'--types','node','--typeRoots',reference/'node_modules/@types','--declaration','--emitDeclarationOnly','--outDir',reference_types])
contract_lines = ['import type * as Candidate from "patamaps-native-sdk-draft";',
                  'type Assert<T extends true> = T;',
                  'type Equivalent<L,R> = [L] extends [R] ? ([R] extends [L] ? true : false) : false;']
for index, module in enumerate(modules):
    contract_lines.append(f'import type * as Reference{index} from "./reference-contracts/{Path(module).relative_to('src').with_suffix('.js').as_posix()}";')
for item in type_rows:
    index = modules.index(item['referenceModule'])
    if item['referenceName'] == 'ImpactOptions':
        contract_lines.append(f'type ImpactOptionsPublicMatches = Assert<Equivalent<Omit<Reference{index}.ImpactOptions,"registry"> & {{registry?:Candidate.LegacyRelationRegistry}},Candidate.LegacyImpactOptions>>;')
        continue
    if item['referenceName'] == 'analyzeImpact':
        contract_lines.append(f'type ImpactPublicMatches = Assert<Equivalent<(document:Parameters<typeof Reference{index}.analyzeImpact>[0],options:Candidate.LegacyImpactOptions)=>ReturnType<typeof Reference{index}.analyzeImpact>,typeof Candidate.analyzeLegacyImpact>>;')
        continue
    if item['referenceName'] == 'MetamapGraphOptions':
        contract_lines.append(f'type GraphOptionsPublicContractMatches = Assert<Equivalent<Omit<Reference{index}.MetamapGraphOptions,"registry"> & {{registry?:Candidate.LegacyRelationRegistry}},Candidate.LegacyGraphOptions>>;')
        continue
    if item['referenceModule'] in ['src/workspace.ts','src/adapters/registry.ts']:
        name=item['referenceName'];candidate=item['candidateName']
        if name=='AdapterRegistry':
            config_index=modules.index('src/config.ts');types_index=modules.index('src/adapters/types.ts')
            contract_lines.append(f'interface ReferenceAdapterRegistryPublic extends Omit<Pick<Reference{index}.AdapterRegistry,keyof Candidate.LegacyAdapterRegistry>,"register"> {{register<TConfig extends Reference{config_index}.MetamapSourceConfig>(adapter:Reference{types_index}.MetamapAdapter<TConfig>):this;}}')
            contract_lines.append('type AdapterRegistryPublicMatches = Assert<Equivalent<ReferenceAdapterRegistryPublic,Candidate.LegacyAdapterRegistry>>;')
            continue
        if name=='WorkspaceOptions':
            contract_lines.append(f'type WorkspaceOptionsPublicMatches = Assert<Equivalent<Omit<Reference{index}.WorkspaceOptions,"adapterRegistry"|"relationRegistry"> & {{adapterRegistry?:Candidate.LegacyAdapterRegistry;relationRegistry?:Candidate.LegacyRelationRegistry}},Candidate.LegacyWorkspaceOptions>>;')
            continue
        if name in ['discoverWorkspace','checkWorkspace']:
            contract_lines.append(f'type {name}PublicMatches = Assert<Equivalent<(loaded:Parameters<typeof Reference{index}.{name}>[0],options?:Candidate.LegacyWorkspaceOptions)=>ReturnType<typeof Reference{index}.{name}>,typeof Candidate.{candidate}>>;')
            continue
        if name=='assembleWorkspace':
            contract_lines.append(f'type assembleWorkspacePublicMatches = Assert<Equivalent<(config:Parameters<typeof Reference{index}.{name}>[0],adapters:Parameters<typeof Reference{index}.{name}>[1],packs:Parameters<typeof Reference{index}.{name}>[2],registry:Candidate.LegacyRelationRegistry,options?:Parameters<typeof Reference{index}.{name}>[4])=>ReturnType<typeof Reference{index}.{name}>,typeof Candidate.{candidate}>>;')
            continue
        if name=='createDefaultAdapterRegistry':
            contract_lines.append(f'type createDefaultRegistryParametersMatch = Assert<Equivalent<Parameters<typeof Reference{index}.{name}>,Parameters<typeof Candidate.{candidate}>>>;')
            contract_lines.append(f'type createDefaultRegistryReturnPublicMatches = Assert<Equivalent<ReferenceAdapterRegistryPublic,ReturnType<typeof Candidate.{candidate}>>>;')
            continue
    prefix = "typeof " if item.get("valueComparison") or item["referenceName"] in ["diffMetamapDocuments","emptyGraphDiff","renderDriftReport","renderGraphDocumentation"] else ""
    contract_lines.append(f'type {item["referenceName"]}Matches = Assert<Equivalent<{prefix}Reference{index}.{item["referenceName"]},{prefix}Candidate.{item["candidateName"]}>>;')
registry_index=modules.index('src/relations.ts')
contract_lines.append(f'type RegistryPublicContractMatches = Assert<Equivalent<Pick<Reference{registry_index}.RelationRegistry,keyof Candidate.LegacyRelationRegistry>,Candidate.LegacyRelationRegistry>>;')
graph_index=modules.index('src/graph.ts')
contract_lines.append(f'type GraphPublicContractMatches = Assert<Equivalent<Omit<Pick<Reference{graph_index}.MetamapGraph,keyof Candidate.LegacyGraph>,"registry"> & {{readonly registry:Candidate.LegacyRelationRegistry}},Candidate.LegacyGraph>>;')
contract_lines.append(f'type GraphErrorPublicContractMatches = Assert<Equivalent<Reference{graph_index}.MetamapValidationError,Candidate.LegacyGraphValidationError>>;')
composition_index=modules.index('src/composer.ts')
contract_lines.append(f'type CompositionOptionsMatches = Assert<Equivalent<Reference{composition_index}.CompositionOptions,Candidate.LegacyCompositionOptions>>;')
contract_lines.append(f'type CompositionFunctionMatches = Assert<Equivalent<typeof Reference{composition_index}.composeMetamapDocuments,typeof Candidate.composeLegacyDocuments>>;')
contract_lines.append(f'type CompositionErrorMatches = Assert<Equivalent<Reference{composition_index}.MetamapCompositionError,Candidate.LegacyCompositionError>>;')
(stage / 'type-contracts.mts').write_text('\n'.join(contract_lines) + '\n')
type_contracts = run('pack-type-contracts', [NODE,TSC,'type-contracts.mts',*options,'--noEmit']) if reference_declarations.returncode == 0 else None
positive = run('compile', [NODE,TSC,'consumer.mts',*options])
execution = run('execute', [NODE,stage/'consumer.mjs']) if positive.returncode == 0 else None
negative = run('reject-types', [NODE,TSC,'negative.mts',*options,'--noEmit'])
engine = json.loads(subprocess.check_output([installed,'engine'],env=environment))
negative_expected_lines = {number for number,line in enumerate((stage/'negative.mts').read_text().splitlines(),1) if number > 1 and line.strip()}
negative_diagnostic_lines = {int(match) for match in re.findall(r"negative\.mts\((\d+),\d+\): error TS",negative.stdout + negative.stderr)}
negative_all_refused = negative_expected_lines <= negative_diagnostic_lines
passed = positive.returncode == 0 and execution is not None and execution.returncode == 0 and negative.returncode != 0 and negative_all_refused
passed = passed and all(f'negative.mts({line},' in negative.stdout for line in range(2,44))
passed = passed and reference_declarations.returncode == 0 and type_contracts is not None and type_contracts.returncode == 0
passed = passed and all(engine[key] == value for key,value in identities(ROOT).items()) and sha(installed) == sha(binary)
verify_reference()
receipt = {'uncheckedDigestCorpus':{'path':digest_fixture.relative_to(ROOT).as_posix(),'digest':sha(digest_fixture)},'schemaVersion':'1.0.0','status':'passed' if passed else 'failed','commands':commands,
           'candidate':{'binaryDigest':sha(binary),'engine':engine,'sdkSourceInventory':inventory},
           'host':{'platform':platform.platform(),'architecture':platform.machine()},'retainedStage':str(stage),
           'logs':{path.name:sha(path) for path in sorted(output.glob('*.log'))},
           'evaluationTypeContractComparison':{'mapping':evaluation_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(evaluation_mapping_path),'mappedDeclarations':len(evaluation_type_mapping['rows']),'comparison':'Bidirectional original-source-generated context/selector/impact declarations and wire models, with explicit public impact registry substitution; compiler/proof execution and private nominal classes remain outside this comparison.'},
           'viabilityTypeContractComparison':{'mapping':viability_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(viability_mapping_path),'mappedDeclarations':len(viability_type_mapping['rows']),'comparison':viability_type_mapping['scope']},
           'viabilityCorpus':{'path':viability_fixture.relative_to(ROOT).as_posix(),'digest':sha(viability_fixture),'installedControls':'Whole frozen original v1 baseline, direct compiler/validation/parser exports, caller identity/freezing, version constants and six additional invalid type uses.'},
           'migrationTypeContractComparison':{'mapping':migration_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(migration_mapping_path),'mappedDeclarations':len(migration_type_mapping['rows'])},
           'workspaceTypeContractComparison':{'mapping':workspace_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(workspace_mapping_path),'mappedDeclarations':len(workspace_type_mapping['rows']),'comparison':'Bidirectional workspace/adapter declarations with explicit public registry substitutions; private nominal class compatibility remains unverified.'},
           'typeContractComparison':{'mapping':mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(mapping_path),'mappedDeclarations':len(type_mapping['rows']),'comparison':'Original-source-generated pack/model declarations and candidate aliases are assignable in both directions under strict TypeScript checking; graph registry properties/options explicitly substitute the separately compared public registry interface. Original private nominal fields remain outside this public interface comparison.','sourceInventory':[{'path':name,'digest':sha(reference / name)} for name in modules],'retainedProbe':str(stage / 'type-contracts.mts'),'probeDigest':sha(stage / 'type-contracts.mts'),'generatedOriginalDeclarations':[{'path':str(path),'digest':sha(path)} for path in sorted(reference_types.rglob('*.d.ts'))],'referenceGitBlobsVerifiedBeforeAndAfter':len(supplement['referenceTree'])},
           'negativeTypeControls':len(negative_expected_lines),'negativeTypeDiagnosticLines':sorted(negative_diagnostic_lines),'allNegativeControlsRefused':negative_all_refused,'configDeclarationsCompared':19,'configTypeContractComparison':{'mapping':config_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(config_mapping_path),'mappedDeclarations':len(config_type_mapping['rows'])},'configCorpus':{'path':config_fixture.relative_to(ROOT).as_posix(),'digest':sha(config_fixture),'installedControls':3},'correspondenceDeclarationsCompared':16,'correspondenceTypeContractComparison':{'mapping':correspondence_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(correspondence_mapping_path),'mappedDeclarations':len(correspondence_type_mapping['rows'])},'correspondenceCorpus':{'path':correspondence_fixture.relative_to(ROOT).as_posix(),'digest':sha(correspondence_fixture),'installedControls':3},'reportingDeclarationsCompared':9,'reportingTypeContractComparison':{'mapping':reporting_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(reporting_mapping_path),'mappedDeclarations':len(reporting_type_mapping['rows'])},'reportingCorpus':{'path':reporting_fixture.relative_to(ROOT).as_posix(),'digest':sha(reporting_fixture),'installedControls':3},
           'registryPublicDeclarationCompared':True,'graphPublicDeclarationCompared':True,'compositionDeclarationsCompared':3,
           'graphTypeContractComparison':{'mapping':graph_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(graph_mapping_path),'mappedDeclarations':len(graph_type_mapping['rows']),'registryComparison':'Graph registry property/options use the separately compared public registry contract. Original private nominal fields are not equivalent across classes; complete nominal package substitution remains unresolved.'},
           'scope':'Copied canonical, scientific and legacy JSON graph/pack/registry SDK interfaces compiled and executed outside the checkout with empty PATH, including asynchronous file loading, version-specific duplicates, UTF-16, UTF-8 replacement, missing-file refusals, live registry identities, frozen executable copies, query arrays and dependency drift. All 57 negative type controls receive independent compiler diagnostics. Eighteen workspace/adapter declarations receive bidirectional comparisons with explicit public registry substitutions. An installed custom registry and pure workspace assembly preserve source object identities. Sixteen correspondence/configuration/reference declarations receive bidirectional comparisons; three installed complete correspondence outputs plus shared-provenance/array identities, Set/own-field order, URI encoding/refusal and identifier/path checks use native operations. Nine diff/report declarations receive bidirectional comparisons; installed diff ordinal, documentation UTF-16, grouping and fresh empty-result controls use frozen expectations. Unchecked digest controls include locale order, integer-key enumeration, UTF-16 keys, invalid executable shapes and null TypeError dispatch. Three composition function/options/error declarations also receive bidirectional comparisons and installed merge/conflict/cross-shard checks. Eleven mapped pack/context and eighteen graph declarations plus the public registry/graph methods receive bidirectional type comparisons against declarations generated from unchanged original source. This closes no full-package or obligation-level parity gate. Reference types are comparison inputs only; no MetaMap runtime package is present in the copied consumer.'}
(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':receipt['status'],'receipt':str((output/'receipt.json').relative_to(ROOT)),'retainedStage':str(stage)},indent=2))
raise SystemExit(0 if passed else 1)
