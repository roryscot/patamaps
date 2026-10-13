"""Execute an installed typed discovery consumer and real refusal controls."""
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
from retained_copy import copy_tree, copy_file, install_discovery_tools
from storage_guard import ensure_guarded

ensure_guarded()

ROOT = Path(__file__).resolve().parents[2]
NODE = Path('/Users/admin/.nvm/versions/node/v22.16.0/bin/node')
ORACLE = ROOT / json.loads((ROOT / '.tools/parity/oracles/current.json').read_text())['source']
SUPPLEMENT = json.loads((ROOT / 'fixtures/parity/supplement.json').read_text())

def verify_reference_tree():
    for item in SUPPLEMENT['referenceTree']:
        raw = (ORACLE / item['path']).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        assert blob == item['gitBlob'], 'Pinned reference changed: ' + item['path']

verify_reference_tree()
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
output = ROOT / 'docs/acceptance/parity' / ('discovery-api-' + stamp)
output.mkdir(parents=True)
work = Path(tempfile.mkdtemp(prefix='patamaps-discovery-api-'))
package = work / 'node_modules/patamaps-discovery-draft'
copy_tree(ROOT / 'adapters/discovery', package)
copy_tree(ROOT / 'sdk/typescript', work / 'node_modules/patamaps-native-sdk-draft')
native = work / 'patamaps'
copy_file(ROOT / 'target/debug/patamaps', native)
tooling = work / 'node_modules/typescript'
tooling_record = install_discovery_tools(ORACLE, work / 'node_modules')
assert json.loads((tooling / 'package.json').read_text())['version'] == '5.9.3'
installed_packages = sorted(['patamaps-discovery-draft', 'patamaps-native-sdk-draft'] + [item['name'] for item in tooling_record['packages']])
assert sorted(path.name for path in (work / 'node_modules').iterdir()) == installed_packages
(work / 'package.json').write_text('{"type":"module"}\n')
data = work / 'data'
data.mkdir()
fixtures = {
    'schema.prisma': 'model Item {\n id String @id\n}\n',
    'schemas/domain.ts': 'import {z} from "zod"; export const Item=z.object({id:z.string()});',
    'app/layout.tsx': 'export default function Layout({children}){return <main>{children}</main>;}',
    'app/page.tsx': 'export default function Page(){return <main>Home</main>;}',
    'collections.json': json.dumps({'items': [{'id': 'one', 'privatePayload': {'ignored': True}}]}),
    'sources.json': json.dumps({'sourcesOfTruth': [{'id': 'schema', 'label': 'Schema', 'paths': ['schema.prisma'], 'outputs': ['generated/client.ts']}]}),
    'mapping.data': (ROOT / 'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv').read_text(),
    'shard.json': json.dumps({'schemaVersion':'2.0.0','id':'urn:installed:shard','namespace':'installed','entities':[{'id':'urn:installed:item','kind':'item','label':'Item','attributes':{'sourceExtension':{'preserved':True}}}],'mappings':[],'authorities':[],'metadata':{'declaredOnly':True}}),
}
for name, content in fixtures.items():
    path = data / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

sha = lambda raw: 'sha256:' + hashlib.sha256(raw).hexdigest()
commands = []
def execute(label, argv, stdin=None, expected=0):
    result = subprocess.run([str(value) for value in argv], cwd=work, input=stdin,
                            capture_output=True, env={'PATH': ''}, timeout=60)
    stdout = output / (label + '.stdout')
    stderr = output / (label + '.stderr')
    stdout.write_bytes(result.stdout)
    stderr.write_bytes(result.stderr)
    commands.append({'label': label, 'argv': [str(value) for value in argv], 'cwd': str(work),
                     'exitCode': result.returncode, 'stdinDigest': None if stdin is None else sha(stdin),
                     'stdout': stdout.relative_to(ROOT).as_posix(), 'stdoutDigest': sha(result.stdout),
                     'stderr': stderr.relative_to(ROOT).as_posix(), 'stderrDigest': sha(result.stderr)})
    assert result.returncode == expected, (label, result.returncode, result.stdout.decode(errors='replace'), result.stderr.decode(errors='replace'))
    return result

common = [NODE, tooling / 'bin/tsc', '--strict', '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext']
positive = '''import {PrismaAdapter,TypeScriptZodAdapter,NextjsAppRouterAdapter,JsonCollectionsAdapter,LegacySourcesAdapter,SssomTsvAdapter,MetamapShardAdapter,configureDiscoveryNative,type AdapterContext,type AdapterResult,type PrismaSourceConfig} from "patamaps-discovery-draft";
import type {SssomExecution} from "patamaps-native-sdk-draft/sssom";
declare const process: {argv:string[]};
const nativeExecutions:SssomExecution[]=[];
configureDiscoveryNative(process.argv[3]!,execution=>nativeExecutions.push(execution));
const context:AdapterContext={namespace:"installed",repository:"fixture",repositoryRoot:process.argv[2]!};
const prisma:PrismaSourceConfig={id:"db",adapter:"prisma",path:"schema.prisma"};
const results:AdapterResult[]=await Promise.all([
  new PrismaAdapter().discover(prisma,context),
  new TypeScriptZodAdapter().discover({id:"zod",adapter:"typescript-zod",roots:["schemas"]},context),
  new NextjsAppRouterAdapter().discover({id:"web",adapter:"nextjs-app-router",root:"app"},context),
  new JsonCollectionsAdapter().discover({id:"json",adapter:"json-collections",path:"collections.json",collections:[{pointer:"/items",idProperty:"id",entityKind:"item"}]},context),
  new LegacySourcesAdapter().discover({id:"legacy",adapter:"legacy-sources",path:"sources.json"},context),
  new SssomTsvAdapter().discover({id:"scientific",adapter:"sssom-tsv",path:"mapping.data",formatVersion:"1.0.0",sourceRevision:"fixture-r1"},context),
  new MetamapShardAdapter().discover({id:"shard",adapter:"metamap-shard",path:"shard.json"},context)
]);
const fingerprint=await new PrismaAdapter().fingerprint(prisma,context);
console.log(JSON.stringify({results,fingerprint,nativeExecutions}));
'''
(work / 'positive.ts').write_text(positive)
execute('typed-positive', [*common, '--outDir', 'dist', 'positive.ts'])
runtime = execute('typed-runtime', [NODE, work / 'dist/positive.js', data, native])
result = json.loads(runtime.stdout)
assert len(result['results']) == 7
assert all(value['document']['entities'] for value in result['results'])
assert [value['adapter'] for value in result['results']] == ['prisma', 'typescript-zod', 'nextjs-app-router', 'json-collections', 'legacy-sources', 'sssom-tsv', 'metamap-shard']
assert result['fingerprint'] == result['results'][0]['inputs']
for value in result['results']:
    for input_ in value['inputs']:
        assert input_['digest'] == sha((data / input_['path']).read_bytes())
assert all('privatePayload' not in entity.get('attributes', {}) for entity in result['results'][3]['document']['entities'])
assert len(result['results'][5]['document']['mappings']) == 7
assert all(mapping['lossiness'] == 'unknown' for mapping in result['results'][5]['document']['mappings'])
assert result['results'][5]['document']['authorities'] == []
assert result['results'][6]['document'] == json.loads(fixtures['shard.json'])

# The oracle runs separately against the same captured bytes. Compare the
# complete JSON-visible result, retaining array order and every metadata field.
reference_source = '''import {pathToFileURL} from "node:url";
import {join} from "node:path";
const oracle=process.argv[2],root=process.argv[3];
const context={namespace:"installed",repository:"fixture",repositoryRoot:root};
const cases=[
 ["prisma","PrismaAdapter",{id:"db",adapter:"prisma",path:"schema.prisma"}],
 ["typescript-zod","TypeScriptZodAdapter",{id:"zod",adapter:"typescript-zod",roots:["schemas"]}],
 ["nextjs-app-router","NextjsAppRouterAdapter",{id:"web",adapter:"nextjs-app-router",root:"app"}],
 ["json-collections","JsonCollectionsAdapter",{id:"json",adapter:"json-collections",path:"collections.json",collections:[{pointer:"/items",idProperty:"id",entityKind:"item"}]}],
 ["legacy-sources","LegacySourcesAdapter",{id:"legacy",adapter:"legacy-sources",path:"sources.json"}],
 ["sssom-tsv","SssomTsvAdapter",{id:"scientific",adapter:"sssom-tsv",path:"mapping.data",formatVersion:"1.0.0",sourceRevision:"fixture-r1"}],
 ["metamap-shard","MetamapShardAdapter",{id:"shard",adapter:"metamap-shard",path:"shard.json"}]
];
const adapters=await Promise.all(cases.map(async([module,name])=>new (await import(pathToFileURL(join(oracle,"dist/adapters",module+".js"))))[name]()));
const results=await Promise.all(adapters.map((adapter,index)=>adapter.discover(cases[index][2],context)));
const fingerprint=await adapters[0].fingerprint(cases[0][2],context);
console.log(JSON.stringify({results,fingerprint}));
'''
reference_script = work / 'reference.mjs'
reference_script.write_text(reference_source)
reference = json.loads(execute('reference-runtime', [NODE, reference_script, ORACLE, data]).stdout)
verify_reference_tree()
differences = []
def compare_json(actual, expected, path='$'):
    numeric = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
    if type(actual) is not type(expected) and not (numeric(actual) and numeric(expected)):
        differences.append({'path':path,'actual':actual,'expected':expected})
    elif isinstance(actual, dict):
        if actual.keys() != expected.keys():
            differences.append({'path':path,'actualKeys':sorted(actual),'expectedKeys':sorted(expected)})
        for key in actual.keys() & expected.keys():
            compare_json(actual[key], expected[key], path + '.' + key)
    elif isinstance(actual, list):
        if len(actual) != len(expected):
            differences.append({'path':path,'actualLength':len(actual),'expectedLength':len(expected)})
        for index, (a, e) in enumerate(zip(actual, expected)):
            compare_json(a, e, path + '[' + str(index) + ']')
    elif actual != expected:
        differences.append({'path':path,'actual':actual,'expected':expected})
compare_json({'results':result['results'],'fingerprint':result['fingerprint']}, reference)
comparison = {'referenceEngine':SUPPLEMENT['referenceEngine'],
              'originalTreeFilesVerified':len(SUPPLEMENT['referenceTree']),
              'providers':[value['adapter'] for value in reference['results']],
              'referenceScriptDigest':sha(reference_script.read_bytes()),
              'referenceResultDigest':sha(json.dumps(reference,sort_keys=True,separators=(',',':')).encode()),
              'candidateResultDigest':sha(json.dumps({'results':result['results'],'fingerprint':result['fingerprint']},sort_keys=True,separators=(',',':')).encode()),
              'differences':differences,
              'scope':'Complete JSON-visible adapter results and Prisma fingerprint for these seven fixtures; array order is significant. No broader workflow or original-case closure.'}
(output / 'reference-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
assert not differences, ('Full provider result differs from the pinned reference', differences[:8])
assert all(call['command'][0] == str(native) and not call['processError'] and call['exitCode'] == 0 for call in result['nativeExecutions'])
for operation in ['source-config','parse','interpret']:
    assert any(call['command'][1:4] == ['sssom','json',operation] for call in result['nativeExecutions'])
assert any(call['command'][1:3] == ['json','digest'] for call in result['nativeExecutions'])

negative_types = {
    'wrong-adapter': 'import {TypeScriptZodAdapter} from "patamaps-discovery-draft"; new TypeScriptZodAdapter().discover({id:"x",adapter:"prisma",roots:["schemas"]},{namespace:"x",repository:"x",repositoryRoot:"."});',
    'wrong-path-type': 'import {PrismaAdapter} from "patamaps-discovery-draft"; new PrismaAdapter().discover({id:"x",adapter:"prisma",path:123},{namespace:"x",repository:"x",repositoryRoot:"."});',
    'unimplemented-config-loader': 'import {parseMetamapConfig} from "patamaps-discovery-draft"; parseMetamapConfig({});',
    'private-config-module': 'import {parseMetamapConfig} from "patamaps-discovery-draft/config"; parseMetamapConfig({});',
}
for name, source in negative_types.items():
    path = work / (name + '.ts')
    path.write_text(source)
    refused = execute('typed-negative-' + name, [*common, '--noEmit', path.name], expected=2)
    assert b'error TS' in refused.stdout

raw = fixtures['schema.prisma']
input_ = {'receipt': {'path': 'schema.prisma', 'digest': sha(raw.encode()), 'byteLength': len(raw.encode())}, 'content': raw}
request = {'schemaVersion': '0.1.0', 'documentType': 'adapter-request', 'profile': 'patamaps-workspace-draft-1',
           'sourceId': 'urn:installed:source', 'namespace': 'installed', 'config': {'adapter': 'prisma', 'path': 'schema.prisma'},
           'inputs': [input_], 'invocationDigest': 'sha256:' + '0'*64, 'requestDigest': 'sha256:' + '1'*64}
outside = work / 'outside.prisma'
outside.write_text('OUTSIDE_CAPTURE_NEVER_READ')
negative_requests = {
    'absolute-config': {**request, 'config': {'adapter': 'prisma', 'path': str(outside)}},
    'relative-escape': {**request, 'config': {'adapter': 'prisma', 'path': '../outside.prisma'}},
    'source-path-escape': {**request, 'inputs': [{**input_, 'receipt': {**input_['receipt'], 'path': '../outside.prisma'}}]},
    'digest-mismatch': {**request, 'inputs': [{**input_, 'receipt': {**input_['receipt'], 'digest': 'sha256:' + '0'*64}}]},
    'duplicate-source': {**request, 'inputs': [input_, input_]},
}
for name, value in negative_requests.items():
    encoded = json.dumps(value, separators=(',', ':')).encode()
    (output / (name + '.request.json')).write_bytes(encoded)
    for mode,arguments in [('ordinary',[]),('native',['--native',native])]:
        before = sorted(work.glob('.patamaps-discovery-*'))
        refused = execute('process-negative-' + mode + '-' + name, [NODE, package / 'process.mjs',*arguments], encoded, expected=1)
        assert not refused.stdout and b'OUTSIDE_CAPTURE_NEVER_READ' not in refused.stderr
        assert sorted(work.glob('.patamaps-discovery-*')) == before, 'Invalid input must refuse before staging or file discovery'
inventory = [{'path': path.relative_to(package).as_posix(), 'digest': sha(path.read_bytes())} for path in sorted(package.rglob('*')) if path.is_file()]
sdk = work / 'node_modules/patamaps-native-sdk-draft'
sdk_inventory = [{'path':path.relative_to(sdk).as_posix(),'digest':sha(path.read_bytes())} for path in sorted(sdk.rglob('*')) if path.is_file()]
engine = json.loads(execute('native-description', [native, 'engine']).stdout)
assert all(engine[key] == value for key,value in identities(ROOT).items())
assert sha(native.read_bytes()) == sha((ROOT / 'target/debug/patamaps').read_bytes())
receipt = {'schemaVersion': '1.0.0', 'status': 'passed', 'driverDigest': sha(Path(__file__).read_bytes()), 'host': {'platform': platform.platform(), 'architecture': platform.machine()},
           'providerSourceInventory': inventory, 'typescriptVersion': '5.9.3', 'retainedRun': str(work), 'commands': commands,
           'positiveTypedConsumer': 'compiled and executed all seven fact providers with PATH empty and a copied native binary',
           'tooling': tooling_record,
           'referenceComparison':{'path':(output/'reference-comparison.json').relative_to(ROOT).as_posix(),'digest':sha((output/'reference-comparison.json').read_bytes()),'differences':len(differences)},
           'candidate':{'binaryDigest':sha(native.read_bytes()),'engine':engine,'sdkSourceInventory':sdk_inventory,'nativeExecutions':len(result['nativeExecutions'])},
           'negativeTypeChecks': list(negative_types), 'processRefusalsBeforeStaging': list(negative_requests),
           'processRefusalModes':['ordinary','native-helper'], 'processRefusalExecutions':len(negative_requests)*2,
           'installedPackages': installed_packages, 'originalCasesClosed': 0,
           'scope': 'Independent installed discovery API and transport controls. No whole scientific/workspace, policy, governance or complete replacement acceptance is inferred.'}
(output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'receipt': (output / 'receipt.json').relative_to(ROOT).as_posix(),
                  'typedNegatives': len(negative_types), 'processRefusals': len(negative_requests)*2, 'retainedRun': str(work)}), flush=True)
