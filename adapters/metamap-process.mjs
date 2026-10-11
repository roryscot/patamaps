// Optional discovery bridge. MetaMap owns parsing knowledge; Rust owns decisions.
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const supported = new Map([
  ['typescript-zod', ['typescript-zod.js', 'TypeScriptZodAdapter']],
  ['nextjs-app-router', ['nextjs-app-router.js', 'NextjsAppRouterAdapter']],
  ['prisma', ['prisma.js', 'PrismaAdapter']],
  ['json-collections', ['json-collections.js', 'JsonCollectionsAdapter']],
  ['legacy-sources', ['legacy-sources.js', 'LegacySourcesAdapter']],
]);
const referenceRoot = process.argv[2];
if (!referenceRoot || !isAbsolute(referenceRoot) || process.argv.length !== 3) throw new Error('Configure an absolute installed MetaMap package directory');
let raw = '';
for await (const chunk of process.stdin) {
  raw += chunk.toString('utf8');
  if (Buffer.byteLength(raw) > 16 * 1024 * 1024) throw new Error('Request byte limit exceeded');
}
const request = JSON.parse(raw);
if (request.schemaVersion !== '0.1.0' || request.documentType !== 'adapter-request' || request.profile !== 'patamaps-workspace-draft-1') throw new Error('Unsupported process protocol');
const selected = supported.get(request.config.adapter);
if (!selected) throw new Error('Unsupported optional discovery adapter');
const root = await mkdtemp(join(tmpdir(), 'patamaps-discovery-'));
try {
  const expected = new Map();
  for (const input of request.inputs) {
    const path = input.receipt.path;
    if (!path || path.includes('\\') || path.split('/').some(s => !s || s === '.' || s === '..' || s.includes(':'))) throw new Error('Invalid captured source path');
    const digest = 'sha256:' + createHash('sha256').update(input.content).digest('hex');
    if (digest !== input.receipt.digest || Buffer.byteLength(input.content) !== input.receipt.byteLength || expected.has(path)) throw new Error('Invalid captured source receipt');
    expected.set(path, digest);
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), input.content, { flag: 'wx' });
  }
  const module = await import(pathToFileURL(join(referenceRoot, 'dist/adapters', selected[0])).href);
  const adapter = new module[selected[1]]();
  const result = await adapter.discover({ ...request.config, id: request.sourceId }, {
    namespace: request.namespace, repository: 'captured-workspace', repositoryRoot: root,
  });
  if (result.inputs.length !== expected.size || result.inputs.some(i => expected.get(i.path) !== i.digest)) throw new Error('Discovery did not consume the exact supplied source inventory');
  const shard = { ...result.document };
  if (!['1.0.0', '2.0.0'].includes(shard.schemaVersion)) throw new Error('Unsupported legacy envelope');
  // The sole envelope migration: retain every other property. Rust rejects any
  // unsupported shape rather than quietly dropping attributes or semantic data.
  delete shard.$schema;
  shard.schemaVersion = '0.1.0';
  shard.documentType = 'graph';
  process.stdout.write(JSON.stringify({
    schemaVersion: '0.1.0', documentType: 'adapter-response', profile: request.profile,
    sourceId: request.sourceId, adapterVersion: `${adapter.id}@${adapter.version}+patamaps-envelope-1`,
    requestDigest: request.requestDigest, inputs: request.inputs.map(i => i.receipt), shard,
    diagnostics: result.diagnostics.map(d => ({ severity: d.severity, code: d.code, message: d.message })),
  }));
} finally { await rm(root, { recursive: true, force: true }); }
