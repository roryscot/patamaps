import assert from 'node:assert/strict';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {convertWorkspace, observationRegistry} from '../../../adapters/discovery/metamap-cross-stack.mjs';
import {spawnWithInputSync} from '../../../sdk/typescript/native-input.mjs';

const input = JSON.parse(await readFile(process.argv[2], 'utf8'));
const metamap = await import(pathToFileURL(join(input.referenceRuntime, 'dist/index.js')).href);
const expected = JSON.parse(await readFile(new URL('../acceptance/m7-expected.json', import.meta.url), 'utf8'));
const result = {profile: 'patamaps-cross-stack-metamap-acceptance-1', controls: [], fullReleaseAccepted: false};
await mkdir(input.output);
function facts(graph) {
  const id = 'urn:example:operation:create-item';
  return {
    operationIds: graph.entities.filter(v => v.kind === 'routing:command').map(v => v.id).sort(),
    nextPages: graph.entities.filter(v => v.kind === 'topology:page' && v.attributes?.adapter === 'nextjs-app-router').map(v => v.attributes.routePath).sort(),
    cargoBins: graph.entities.filter(v => v.kind === 'cargo-target' && v.attributes?.kind?.includes('bin')).map(v => v.attributes.name).sort(),
    rustModulePath: graph.entities.find(v => v.id === id + ':handler')?.attributes?.http?.modulePath,
    linuxArtifactObservations: graph.entities.filter(v => v.kind === 'build:artifact' && v.attributes?.compilationEstablished === true).length,
  };
}
let supported;
for (const item of input.cases) {
  const destination = join(input.output, item.control);
  if (item.control === 'm7-malformed-config') {
    // This is a real unavailable source record, not a fabricated graph. The
    // original MetaMap shard adapter must refuse it rather than invent facts.
    await mkdir(destination);
    const adapter = new metamap.MetamapShardAdapter();
    await assert.rejects(adapter.discover({adapter: 'metamap-shard', id: 'urn:test:unavailable', path: item.unavailablePath},
      {namespace: 'cross-stack', repository: 'cross-stack-fixture', repositoryRoot: item.sourceRoot}), /not a portable Metamap graph shard/);
    result.controls.push({control: item.control, native: 'source-refused', metamap: 'source-refused', graphManufactured: false,
      independentTOMLParserComparison: false, sharedNativeProviderDiagnostic: item.nativeDiagnostic});
    continue;
  }
  const commands = [];
  const converted = await convertWorkspace({...item, destination, executable: input.executable, metamap,
    evaluationContext: input.context, evaluatedAt: input.evaluatedAt, observe: event => commands.push(event)});
  await writeFile(join(destination, 'native-json-commands.json'), JSON.stringify(commands, null, 2) + '\n', {flag: 'wx'});
  const argv = ['compile', item.graphPath, item.policyPath, '--context', input.contextPath, '--as-of', input.evaluatedAt,
    ...item.packPaths.flatMap(path => ['--relation-pack', path])];
  const native = spawnWithInputSync(input.executable, argv, {input: '', encoding: 'utf8', env: {}, timeout: 65000, maxBuffer: 16777217});
  if (native.error) throw native.error;
  await writeFile(join(destination, 'native.stdout.json'), native.stdout, {flag: 'wx'});
  await writeFile(join(destination, 'native.stderr.log'), native.stderr, {flag: 'wx'});
  await writeFile(join(destination, 'native-invocation.json'), JSON.stringify({argv: [input.executable, ...argv], exitCode: native.status}, null, 2) + '\n', {flag: 'wx'});
  const wanted = expected.decisions[item.control];
  assert.equal(native.status === 0 ? 'viable' : 'rejected', wanted, item.control + ' native decision');
  assert.equal(converted.compiled.status, wanted, item.control + ' MetaMap decision');
  const observed = facts(converted.graph);
  const original = JSON.parse(await readFile(item.graphPath, 'utf8'));
  assert.deepEqual(observed, facts(original), item.control + ' conversion changed observed/owned facts');
  assert.deepEqual(observed.operationIds, expected.facts.operationIds);
  assert.deepEqual(observed.nextPages, expected.facts.nextPages);
  assert.deepEqual(observed.cargoBins, expected.facts.cargoBins);
  assert.equal(observed.rustModulePath, item.control === 'm7-moved-handler' ? 'handlers/moved_create_item.rs' : 'handlers/create_item.rs');
  if (item.code) {
    assert(native.stdout.includes(item.code) || native.stderr.includes(item.code), item.control + ' wrong native refusal');
    assert(converted.compiled.issues.some(v => v.code === item.code), item.control + ' wrong MetaMap refusal');
  }
  // All changed fields are declared envelope/rebinding addresses. Facts and
  // semantics cannot be silently dropped to satisfy a different engine schema.
  for (const record of converted.records) {
    for (const change of record.changes) {
      const allowed = record.kind === 'relation-pack' ? /^\/(schemaVersion|documentType)$/ :
        record.kind === 'policy' ? /^\/(schemaVersion|documentType|\$schema|graph(?:\/.*)?)$/ :
        /^\/(schemaVersion|documentType|revision|\$schema|relationPacks\/[0-9]+\/(digest|uri))$/;
      assert.match(change.path, allowed, 'Unexpected conversion address');
    }
  }
  result.controls.push({control: item.control, native: wanted, metamap: converted.compiled.status, facts: observed,
    conversionRecords: converted.records.length, adapter: converted.adapter, commonIssue: item.code ?? null,
    compared: 'independent facts and decisions; no cross-engine hash equality'});
  if (item.control === 'm7-supported') supported = converted;
}
assert(supported);
const unregistered = metamap.compileMetamap(supported.graph, supported.policy, {relationRegistry: supported.registry,
  context: input.context, evaluatedAt: input.evaluatedAt});
assert.equal(unregistered.status, 'rejected');
assert(unregistered.issues.some(v => v.code === 'UNKNOWN_CONSTRAINT_KIND'));
result.controls.push({control: 'm7-unregistered-evaluator', result: 'refused', code: 'UNKNOWN_CONSTRAINT_KIND'});
const negative = input.cases.find(v => v.control === 'm7-missing-artifact');
const badPolicy = JSON.parse(await readFile(join(input.output, negative.control, 'converted/policy.json'), 'utf8'));
const badGraph = JSON.parse(await readFile(join(input.output, negative.control, 'converted/graph.json'), 'utf8'));
badPolicy.waivers = [{id: 'urn:test:forbidden-waiver', codes: ['BUILD_OBSERVATION_BINDING_MISMATCH'],
  subjects: badPolicy.constraints.filter(v => v.kind === 'build:observation-binding-v1').flatMap(v => v.subjects),
  reason: 'Independent refusal control; this must not grant acceptance', assertedBy: 'fixture-owner', expiresAt: '2026-11-15T00:00:00Z'}];
const waived = metamap.compileMetamap(badGraph, badPolicy, {relationRegistry: supported.registry,
  constraintRegistry: observationRegistry(metamap), context: input.context, evaluatedAt: input.evaluatedAt});
assert.equal(waived.status, 'rejected');
result.controls.push({control: 'm7-protected-observation-waiver', result: 'refused'});
assert.deepEqual(result.controls.map(v => v.control).sort(), [...expected.controls].sort());
result.status = 'passed-portable-facts-metamap-scope';
await writeFile(join(input.output, 'receipt.json'), JSON.stringify(result, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify(result));
