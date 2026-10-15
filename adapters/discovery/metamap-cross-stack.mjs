/** Explicit cross-stack envelope conversion and the real MetaMap evaluator.
 * Consumer code lives outside the pinned reference and never copies native
 * generations, approvals or captures into MetaMap records.
 */
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {join, isAbsolute} from 'node:path';
import {spawnWithInputSync} from '../../sdk/typescript/native-input.mjs';

const digest = bytes => 'sha256:' + createHash('sha256').update(bytes).digest('hex');
const missing = Symbol('missing');
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const exactKeys = (value, names) => object(value) && Object.keys(value).length === names.length && names.every(v => Object.hasOwn(value, v));
function equal(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null) return false;
  if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => equal(v, b[i]));
  return object(a) && object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => Object.hasOwn(b, key) && equal(a[key], b[key]));
}

export function nativeJson(executable, operation, bytes, observe) {
  if (!isAbsolute(executable)) throw new Error('ABSOLUTE_NATIVE_EXECUTABLE_REQUIRED');
  const argv = ['json', operation];
  const result = spawnWithInputSync(executable, argv, {input: bytes, encoding: 'utf8', env: {}, timeout: 65000, maxBuffer: 16777217});
  observe?.({argv: [executable, ...argv], inputDigest: digest(bytes), exitCode: result.status, stdout: result.stdout, stderr: result.stderr});
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error('NATIVE_JSON_REFUSAL: ' + result.stdout);
  return result.stdout;
}

export function parseLossless(bytes, executable, observe) {
  nativeJson(executable, 'parse', bytes, observe);
  const originalCanonical = nativeJson(executable, 'canonical', bytes, observe);
  const value = JSON.parse(bytes.toString('utf8'));
  if (nativeJson(executable, 'canonical', JSON.stringify(value), observe) !== originalCanonical)
    throw new Error('METAMAP_LOSSLESS_JSON_REQUIRED');
  return value;
}

/** A fresh registry per compile prevents extension/registration state leakage.
 * The WeakMap shares the fixed work bound across all constraints in one actual
 * MetaMap admission (its active-mapping set), without weakening that bound.
 */
export function observationRegistry(metamap) {
  const registry = new metamap.ConstraintRegistry();
  const budgets = new WeakMap();
  registry.register('build:observation-binding-v1', (constraint, context) => {
    const issue = (code, subjectId = constraint.id) => ({severity: 'error', code, subjectId,
      message: constraint.id + ': ' + code});
    const step = () => {
      const used = budgets.get(context.activeMappings) ?? 0;
      if (used >= 2000000) throw new Error('BUILD_OBSERVATION_RESOURCE_LIMIT');
      budgets.set(context.activeMappings, used + 1);
    };
    try {
      const p = constraint.parameters;
      if (!exactKeys(p, ['relation', 'targetKind', 'conditions']) || typeof p.relation !== 'string' || !context.graph.registry.get(p.relation) ||
          typeof p.targetKind !== 'string' || !p.targetKind.length || Buffer.byteLength(p.targetKind) > 256 ||
          !Array.isArray(p.conditions) || !p.conditions.length || p.conditions.length > 64 ||
          !constraint.subjects.length || constraint.subjects.length > 128 || new Set(constraint.subjects).size !== constraint.subjects.length)
        return [issue('INVALID_CONSTRAINT_PARAMETERS')];
      for (const condition of p.conditions) {
        step();
        if (!exactKeys(condition, ['path', 'equals']) || !Array.isArray(condition.path) || !condition.path.length || condition.path.length > 32 ||
            !condition.path.every(v => typeof v === 'string' && Buffer.byteLength(v) <= 256) || Buffer.byteLength(JSON.stringify(condition.equals)) > 65536)
          return [issue('INVALID_CONSTRAINT_PARAMETERS')];
      }
      const observed = new Set();
      for (const entity of context.document.entities) {
        step();
        if (entity.kind !== p.targetKind) continue;
        step();
        let matches = true;
        for (const condition of p.conditions) {
          let value = entity;
          for (const component of condition.path) {
            step();
            if (Array.isArray(value)) {
              const index = /^\+?[0-9]+$/.test(component) ? Number(component) : -1;
              value = Number.isSafeInteger(index) && index >= 0 && index < value.length ? value[index] : missing;
            } else value = object(value) && Object.hasOwn(value, component) ? value[component] : missing;
          }
          if (value === missing || !equal(value, condition.equals)) { matches = false; break; }
          step();
        }
        if (matches) observed.add(entity.id);
      }
      return constraint.subjects.flatMap(subject => {
        step();
        const bound = new Set();
        for (const mapping of context.graph.mappingsFor(subject)) {
          step();
          if (context.activeMappings.has(mapping.id) && mapping.relation === p.relation && mapping.sources.includes(subject))
            for (const target of mapping.targets) { step(); bound.add(target); }
        }
        return bound.size === observed.size && [...bound].every(v => observed.has(v)) ? [] : [issue('BUILD_OBSERVATION_BINDING_MISMATCH', subject)];
      });
    } catch (error) {
      if (error.message === 'BUILD_OBSERVATION_RESOURCE_LIMIT') return [issue(error.message)];
      throw error;
    }
  });
  return registry;
}

const address = component => String(component).replaceAll('~', '~0').replaceAll('/', '~1');
function differences(before, after, path = '') {
  if (equal(before, after)) return [];
  if (object(before) && object(after) || Array.isArray(before) && Array.isArray(after) && before.length === after.length) {
    return [...new Set([...Object.keys(before), ...Object.keys(after)])].sort().flatMap(key => {
      const at = path + '/' + address(key);
      if (!Object.hasOwn(after, key)) return [{op: 'remove', path: at, before: before[key]}];
      if (!Object.hasOwn(before, key)) return [{op: 'add', path: at, after: after[key]}];
      return differences(before[key], after[key], at);
    });
  }
  return [{op: 'replace', path, before, after}];
}

export async function convertWorkspace({graphPath, policyPath, packPaths, destination, executable, metamap, observe,
  evaluationContext = {mode: 'source-intent', platform: 'linux/amd64'}, evaluatedAt = '2026-10-15T00:00:00Z'}) {
  await mkdir(destination, {recursive: false});
  await mkdir(join(destination, 'original'));
  await mkdir(join(destination, 'converted'));
  const records = [];
  async function original(path, name) {
    const bytes = await readFile(path);
    await writeFile(join(destination, 'original', name), bytes, {flag: 'wx'});
    return {bytes, value: parseLossless(bytes, executable, observe), name};
  }
  async function save(input, converted, kind) {
    const bytes = Buffer.from(JSON.stringify(converted, null, 2) + '\n');
    await writeFile(join(destination, 'converted', input.name), bytes, {flag: 'wx'});
    records.push({kind, original: 'original/' + input.name, originalDigest: digest(input.bytes), converted: 'converted/' + input.name,
      convertedDigest: digest(bytes), changes: differences(input.value, converted), nativeApprovalsReused: false});
  }
  const convertedPacks = [];
  for (const [index, path] of packPaths.entries()) {
    const input = await original(path, 'pack-' + index + '.json');
    if (input.value.schemaVersion !== '0.1.0' || input.value.documentType !== 'relation-pack') throw new Error('NATIVE_PACK_ENVELOPE_REQUIRED');
    const pack = structuredClone(input.value);
    delete pack.documentType;
    pack.schemaVersion = '1.0.0';
    metamap.parseRelationPack(pack);
    await save(input, pack, 'relation-pack');
    convertedPacks.push({pack, name: input.name});
  }
  const registry = new metamap.RelationRegistry([]);
  for (const {pack} of convertedPacks) registry.registerPack(pack);
  const inputGraph = await original(graphPath, 'graph.json');
  const inputPolicy = await original(policyPath, 'policy.json');
  if (inputGraph.value.schemaVersion !== '0.1.0' || inputGraph.value.documentType !== 'graph' ||
      inputPolicy.value.schemaVersion !== '0.1.0' || inputPolicy.value.documentType !== 'policy') throw new Error('NATIVE_GRAPH_POLICY_ENVELOPES_REQUIRED');
  const graph = structuredClone(inputGraph.value);
  delete graph.documentType;
  graph.schemaVersion = '2.0.0';
  graph.revision = 'cross-stack-envelope-conversion-1';
  if (Object.hasOwn(graph, '$schema')) delete graph.$schema;
  for (const reference of graph.relationPacks ?? []) {
    const selected = convertedPacks.find(v => v.pack.id === reference.id && v.pack.version === reference.version);
    if (!selected) throw new Error('CONVERTED_PACK_UNAVAILABLE: ' + reference.id);
    reference.digest = metamap.relationPackDigest(selected.pack);
    reference.uri = 'repo:converted/' + selected.name;
  }
  const policy = structuredClone(inputPolicy.value);
  delete policy.documentType;
  policy.schemaVersion = '1.0.0';
  if (Object.hasOwn(policy, '$schema')) delete policy.$schema;
  policy.graph = {id: graph.id, revision: graph.revision};
  await save(inputGraph, graph, 'graph');
  await save(inputPolicy, policy, 'policy');
  const validation = metamap.validateMetamapDocument(graph, registry);
  if (!validation.valid) throw new Error('CONVERTED_GRAPH_INVALID: ' + JSON.stringify(validation.issues));
  const checkedPolicy = metamap.validateViabilityPolicy(policy);
  if (!checkedPolicy.valid) throw new Error('CONVERTED_POLICY_INVALID: ' + JSON.stringify(checkedPolicy.issues));
  await writeFile(join(destination, 'conversion.json'), JSON.stringify({profile: 'patamaps-cross-stack-envelope-conversion-1',
    records, nativeCapturesApprovalsGenerationsReused: false, reusedProviderBugsExcluded: false}, null, 2) + '\n', {flag: 'wx'});
  // Exercise the original portable-shard adapter, with its original config
  // envelope and fingerprint contract, outside the immutable reference tree.
  const adapter = new metamap.MetamapShardAdapter();
  const source = {id: graph.id + ':metamap-source', adapter: 'metamap-shard', path: 'converted/graph.json'};
  const context = {namespace: graph.namespace, repository: 'cross-stack-fixture', repositoryRoot: destination};
  const imported = await adapter.discover(source, context);
  if (!equal(imported.document, graph)) throw new Error('PORTABLE_SHARD_IMPORT_CHANGED_FACTS');
  const compiled = metamap.compileMetamap(imported.document, policy, {relationRegistry: registry,
    constraintRegistry: observationRegistry(metamap), context: evaluationContext, evaluatedAt});
  await writeFile(join(destination, 'metamap-result.json'), JSON.stringify(compiled, null, 2) + '\n', {flag: 'wx'});
  return {graph, policy, registry, compiled, records, adapter: {id: adapter.id, version: adapter.version, inputs: imported.inputs}};
}
