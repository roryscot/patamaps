"""Compile and execute a copied SDK/native subset outside the checkout."""
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
type_rows = type_mapping['rows'] + graph_type_mapping['rows']
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
const graph = {schemaVersion:'2.0.0',id:'urn:installed:graph',namespace:'installed',relationPacks:[{id:'urn:metamap:relation-pack:core',version:'1.0.0'}],entities:[{id:'urn:installed:a',kind:'field'},{id:'urn:installed:b',kind:'field'}],mappings:[{id:'urn:installed:m',relation:'core:references',sources:['urn:installed:a'],targets:['urn:installed:b'],cardinality:'one-to-one',lossiness:'lossless',provenance:{status:'declared',assertedBy:'installed-consumer'}}],authorities:[]};
const validated:LegacyValidationResult = legacy.validateLegacyDocument(graph);
if(!validated.valid || validated.issues.length || legacy.validateLegacyDocumentShape(graph).length) throw new Error('Legacy validation mismatch');
graph.mappings[0].targets = ['urn:installed:missing'];
const invalid = legacy.validateLegacyDocument(graph);
if(invalid.valid || invalid.issues.length !== 1 || invalid.issues[0].code !== 'UNRESOLVED_ENDPOINT' || invalid.issues[0].path !== '$.mappings[0].targets[0]' || invalid.issues[0].subjectId !== 'urn:installed:m') throw new Error('Legacy semantic diagnostic mismatch');
if(legacy.validateLegacyDocument(null).issues[0].code !== 'INVALID_DOCUMENT') throw new Error('Legacy shape diagnostic mismatch');
const portableInput = {schemaVersion:'1.0.0',id:'urn:installed:pack',version:'1',relations:[{id:'test:edge',cyclePolicy:'allow'}]};
const portable = legacy.parseLegacyRelationPack(portableInput);
if(portable !== portableInput) throw new Error('Pack parser changed caller identity');
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
'''.replace('__PATAMAPS_EXECUTABLE__', json.dumps(str(installed))).replace('__PATAMAPS_SSSOM_TEXT__', json.dumps(raw)).replace('PLACEHOLDER', hashlib.sha256(b'{"a":2,"z":1}').hexdigest()).replace('__PATAMAPS_LEGACY_FILE__', json.dumps(str(legacy_file))).replace('__PATAMAPS_LEGACY_DIGEST__', json.dumps('sha256:' + hashlib.sha256(legacy_expected_bytes).hexdigest())).replace('__PATAMAPS_DUPLICATE_FILE__', json.dumps(str(executable_duplicate_file))).replace('__PATAMAPS_REPLACEMENT_FILE__', json.dumps(str(replacement_file))).replace('__PATAMAPS_MISSING_FILE__', json.dumps(str(stage / 'missing-pack.json')))
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
    contract_lines.append(f'import type * as Reference{index} from "./reference-contracts/{Path(module).stem}.js";')
for item in type_rows:
    index = modules.index(item['referenceModule'])
    if item['referenceName'] == 'MetamapGraphOptions':
        contract_lines.append(f'type GraphOptionsPublicContractMatches = Assert<Equivalent<Omit<Reference{index}.MetamapGraphOptions,"registry"> & {{registry?:Candidate.LegacyRelationRegistry}},Candidate.LegacyGraphOptions>>;')
        continue
    contract_lines.append(f'type {item["referenceName"]}Matches = Assert<Equivalent<Reference{index}.{item["referenceName"]},Candidate.{item["candidateName"]}>>;')
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
passed = positive.returncode == 0 and execution is not None and execution.returncode == 0 and negative.returncode != 0
passed = passed and all(f'negative.mts({line},' in negative.stdout for line in range(2,31))
passed = passed and reference_declarations.returncode == 0 and type_contracts is not None and type_contracts.returncode == 0
passed = passed and all(engine[key] == value for key,value in identities(ROOT).items()) and sha(installed) == sha(binary)
verify_reference()
receipt = {'schemaVersion':'1.0.0','status':'passed' if passed else 'failed','commands':commands,
           'candidate':{'binaryDigest':sha(binary),'engine':engine,'sdkSourceInventory':inventory},
           'host':{'platform':platform.platform(),'architecture':platform.machine()},'retainedStage':str(stage),
           'logs':{path.name:sha(path) for path in sorted(output.glob('*.log'))},
           'typeContractComparison':{'mapping':mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(mapping_path),'mappedDeclarations':len(type_mapping['rows']),'comparison':'Original-source-generated pack/model declarations and candidate aliases are assignable in both directions under strict TypeScript checking; graph registry properties/options explicitly substitute the separately compared public registry interface. Original private nominal fields remain outside this public interface comparison.','sourceInventory':[{'path':name,'digest':sha(reference / name)} for name in modules],'retainedProbe':str(stage / 'type-contracts.mts'),'probeDigest':sha(stage / 'type-contracts.mts'),'generatedOriginalDeclarations':[{'path':str(path),'digest':sha(path)} for path in sorted(reference_types.glob('*.d.ts'))],'referenceGitBlobsVerifiedBeforeAndAfter':len(supplement['referenceTree'])},
           'negativeTypeControls':29,
           'registryPublicDeclarationCompared':True,'graphPublicDeclarationCompared':True,'compositionDeclarationsCompared':3,
           'graphTypeContractComparison':{'mapping':graph_mapping_path.relative_to(ROOT).as_posix(),'mappingDigest':sha(graph_mapping_path),'mappedDeclarations':len(graph_type_mapping['rows']),'registryComparison':'Graph registry property/options use the separately compared public registry contract. Original private nominal fields are not equivalent across classes; complete nominal package substitution remains unresolved.'},
           'scope':'Copied canonical, scientific and legacy JSON graph/pack/registry SDK interfaces compiled and executed outside the checkout with empty PATH, including asynchronous file loading, version-specific duplicates, UTF-16, UTF-8 replacement, missing-file refusals, live registry identities, frozen executable copies, query arrays and dependency drift. Twenty-nine negative type controls reject. Three composition function/options/error declarations also receive bidirectional comparisons and installed merge/conflict/cross-shard checks. Eleven mapped pack/context and eighteen graph declarations plus the public registry/graph methods receive bidirectional type comparisons against declarations generated from unchanged original source. This closes no full-package or obligation-level parity gate. Reference types are comparison inputs only; no MetaMap runtime package is present in the copied consumer.'}
(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':receipt['status'],'receipt':str((output/'receipt.json').relative_to(ROOT)),'retainedStage':str(stage)},indent=2))
raise SystemExit(0 if passed else 1)
