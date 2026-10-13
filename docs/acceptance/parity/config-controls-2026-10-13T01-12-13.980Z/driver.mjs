/** Freeze original identifier/path/URI observations before native comparison. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  appendFileSync,
} from "node:fs";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
function verifyTree() {
  for (const item of supplement.referenceTree) {
    const raw = readFileSync(join(oracle, item.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${raw.length}\0`)
        .update(raw)
        .digest("hex"),
      item.gitBlob,
      item.path,
    );
  }
}
verifyTree();

const corpusPath = join(root, "fixtures/parity/config-controls.json");
const base = () => ({
  schemaVersion: "1.0.0",
  id: "urn:test:config",
  namespace: "test",
  repository: "fixture",
  repositoryRoot: ".",
  sources: [{ id: "db", adapter: "prisma", path: "schema.prisma" }],
  correspondences: [],
  outputs: {
    graph: "generated/graph.json",
    snapshot: "generated/snapshot.json",
    report: "generated/report.md",
    documentation: "generated/graph.md",
  },
});
async function observe(action, api, folder) {
  let value;
  try {
    if (action.operation === "load") {
      const path = resolve(folder, action.path);
      if (action.bytes)
        writeFileSync(path, Buffer.from(action.bytes, "base64"));
      else if (action.text !== undefined) writeFileSync(path, action.text);
      const promise = api.loadMetamapConfig(path);
      const isPromise = promise instanceof Promise;
      const result = await promise;
      return {
        status: "observed",
        value: result,
        isPromise,
        keys: Object.keys(result),
        configKeys: Object.keys(result.config),
      };
    }
    value = JSON.parse(action.input);
    const before = JSON.stringify(value);
    const result = api.parseMetamapConfig(value);
    return {
      status: "observed",
      value: result,
      same: result === value,
      unchanged: JSON.stringify(value) === before,
      keys: Object.keys(result),
      sourceKeys: result.sources.map(Object.keys),
    };
  } catch (error) {
    return {
      status: "threw",
      error: {
        name: error.name,
        message: error.message,
        code: error.code ?? null,
        ...Object.fromEntries(
          ["path", "errno", "syscall"]
            .filter((k) => error[k] !== undefined)
            .map((k) => [k, error[k]]),
        ),
      },
    };
  }
}
if (!existsSync(corpusPath)) {
  const api = await import(pathToFileURL(join(oracle, "dist/config.js")));
  const cases = [];
  const add = async (name, value) => {
    const action = { operation: "parse", input: JSON.stringify(value) };
    cases.push({ name, action, expected: await observe(action, api) });
  };
  await add("minimal", base());
  for (const value of [null, true, false, 0, "", [], {}, { extra: 1 }])
    await add("root-" + cases.length, value);
  for (const key of Object.keys(base())) {
    let v = base();
    delete v[key];
    await add("missing-" + key, v);
    for (const x of [null, true, 0, "", [], {}]) {
      v = base();
      v[key] = x;
      await add("root-" + key + "-" + cases.length, v);
    }
  }
  for (const key of [
    "id",
    "label",
    "namespace",
    "repository",
    "repositoryRoot",
  ])
    for (const x of [" ", "é", "\ud800", "\ue000", "😀"]) {
      let v = base();
      v[key] = x;
      await add(key + "-unicode-" + cases.length, v);
    }
  for (const x of [
    "",
    "./schemas/config.json",
    "https://x.test/a",
    "a b",
    '"quoted"',
    "urn:\ud800",
  ]) {
    let v = base();
    v.$schema = x;
    await add("schema-uri-" + cases.length, v);
  }
  for (const x of [
    [],
    ["a"],
    ["a", "a"],
    ["__proto__", "__proto__"],
    ["a", "b", "a", "b"],
    [""],
    [1],
    null,
  ]) {
    let v = base();
    v.relationPacks = x;
    await add("packs-" + cases.length, v);
  }
  const sources = [
    { id: "p", adapter: "prisma", path: "p" },
    { id: "z", adapter: "typescript-zod", roots: ["src"], exclude: [] },
    { id: "l", adapter: "legacy-sources", path: "l" },
    {
      id: "j",
      adapter: "json-collections",
      path: "j",
      collections: [
        {
          pointer: "",
          idProperty: "id",
          entityKind: "item",
          references: [{ property: "ref", targetKind: "item" }],
        },
      ],
    },
    { id: "m", adapter: "metamap-shard", path: "m" },
    {
      id: "n",
      adapter: "nextjs-app-router",
      root: "src/app",
      extensions: ["ts", "tsx"],
      exclusions: [
        {
          path: "src/app/legacy/page.tsx",
          reason: "Migration",
          assertedBy: "team:web",
          relations: ["topology:implemented_by"],
        },
      ],
    },
    {
      id: "custom",
      adapter: "custom-plugin",
      payload: { 2: 2, 1: 1, z: [null, true, "x"], a: { x: 2 } },
    },
    {
      id: "s",
      adapter: "sssom-tsv",
      path: "s.tsv",
      formatVersion: "1.0.0",
      sourceRevision: "r1",
    },
  ];
  for (const source of sources) {
    let v = base();
    v.sources = [source];
    await add("source-valid-" + source.adapter, v);
    for (const key of Object.keys(source)) {
      v = base();
      v.sources = [structuredClone(source)];
      delete v.sources[0][key];
      await add("source-missing-" + source.adapter + "-" + key, v);
      v = base();
      v.sources = [{ ...source, [key]: null }];
      await add("source-null-" + source.adapter + "-" + key, v);
    }
    v = base();
    v.sources = [{ ...source, unexpected: true }];
    await add("source-extra-" + source.adapter, v);
  }
  {
    let v = base();
    v.sources = sources;
    v.sources[3].collections[0].pointer = "/items";
    await add("all-adapters", v);
  }
  for (const ids of [
    ["db", "db"],
    ["__proto__", "__proto__"],
    ["\ud800", "\ud800"],
    ["a", "b", "a"],
  ]) {
    let v = base();
    v.sources = ids.map((id) => ({ id, adapter: "prisma", path: "x" }));
    await add("duplicate-source-" + cases.length, v);
  }
  const correspondence = {
    id: "c",
    source: { sourceId: "db", kind: "model", name: "Item" },
    target: { sourceId: "db", kind: "model", name: "Item" },
    fields: {
      pairs: [
        {
          source: "x",
          target: "y",
          compare: ["type", "presence"],
          allowDifferences: [],
          note: "",
        },
      ],
      ignoreSource: [],
      ignoreTarget: [],
      requireSourceCoverage: true,
    },
    enumValues: { allowSourceOnly: [], allowTargetOnly: [] },
    authority: { side: "source", facts: ["shape"] },
  };
  {
    let v = base();
    v.correspondences = [correspondence];
    await add("complete-correspondence", v);
  }
  for (const key of Object.keys(correspondence)) {
    let v = base();
    v.correspondences = [structuredClone(correspondence)];
    delete v.correspondences[0][key];
    await add("correspondence-missing-" + key, v);
    v = base();
    v.correspondences = [{ ...correspondence, [key]: null }];
    await add("correspondence-null-" + key, v);
  }
  for (const side of ["source", "target"])
    for (const id of ["unknown", "\ud800", "db"]) {
      let v = base();
      v.correspondences = [structuredClone(correspondence)];
      v.correspondences[0][side].sourceId = id;
      await add("reference-" + side + "-" + cases.length, v);
    }
  {
    let v = base();
    v.correspondences = [correspondence, correspondence];
    await add("duplicate-correspondence", v);
    v.outputs.extra = true;
    await add("schema-before-semantic", v);
  }
  for (const value of [
    null,
    {},
    { baselineChanges: "ignore", unconfiguredStructures: "warning" },
    { baselineChanges: "bad" },
    { unexpected: "x" },
  ]) {
    let v = base();
    v.policy = value;
    await add("policy-" + cases.length, v);
  }
  {
    let v = base();
    v.sources = [
      {
        id: "s",
        adapter: "sssom-tsv",
        path: "s.tsv",
        formatVersion: "1.0.0",
        sourceRevision: "r",
        provenance: { x: "\ud800" },
      },
    ];
    await add("sssom-unpaired", v);
  }
  const text = JSON.stringify(base());
  cases.push({
    name: "duplicate-root-last-wins",
    action: {
      operation: "parse",
      input: text.replace(
        '"schemaVersion":"1.0.0"',
        '"schemaVersion":"wrong","schemaVersion":"1.0.0"',
      ),
    },
    expected: await observe(
      {
        operation: "parse",
        input: text.replace(
          '"schemaVersion":"1.0.0"',
          '"schemaVersion":"wrong","schemaVersion":"1.0.0"',
        ),
      },
      api,
    ),
  });
  verifyTree();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        originalRuntime: process.version,
        originalArtifacts: [
          "dist/config.js",
          "dist/sssom.js",
          "schemas/metamap-config.schema.json",
        ].map((path) => ({
          path,
          digest: sha(readFileSync(join(oracle, path))),
        })),
        scope:
          "Complete pinned config parser on finite JSON controls, schema/semantic ordering, return identity/order and SSSOM validation. Async loading is separately compared on retained fixture files. Arbitrary JS, resource, package and platform contracts remain open.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpus = JSON.parse(readFileSync(corpusPath));
for (const a of corpus.originalArtifacts)
  assert.equal(sha(readFileSync(join(oracle, a.path))), a.digest);
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
if (process.argv.includes("--freeze-only")) {
  console.log(
    JSON.stringify({
      status: "original-observations-frozen",
      cases: corpus.cases.length,
      digest: sha(readFileSync(corpusPath)),
    }),
  );
  process.exit(0);
}
const output = join(
  root,
  "docs/acceptance/parity",
  `config-controls-${new Date().toISOString().replaceAll(":", "-")}`,
);
mkdirSync(output, { recursive: true });
const trace = join(output, "native-executions.ndjson");
const cli = join(root, "target/debug/patamaps");
let caseName;
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
const facade = createLegacyValidationApi(cli, (e) =>
  appendFileSync(trace, JSON.stringify({ caseName, ...e }) + "\n"),
);
const api = {
  parseMetamapConfig: facade.parseLegacyMetamapConfig,
  loadMetamapConfig: facade.loadLegacyMetamapConfig,
};
const results = [];
for (const test of corpus.cases) {
  caseName = test.name;
  const observed = await observe(test.action, api);
  let matched = true;
  try {
    assert.deepEqual(observed, test.expected);
  } catch {
    matched = false;
  }
  results.push({ name: test.name, matched, observed });
}
const ref = await import(pathToFileURL(join(oracle, "dist/config.js")));
const files = [
  ["valid", "valid.json", JSON.stringify(base())],
  [
    "relative-root",
    "relative.json",
    JSON.stringify({ ...base(), repositoryRoot: "../repository/./src/.." }),
  ],
  [
    "absolute-root",
    "absolute.json",
    JSON.stringify({ ...base(), repositoryRoot: "/tmp/config-absolute" }),
  ],
  ["empty", "empty.json", ""],
  ["syntax", "syntax.json", '{"schemaVersion":'],
  [
    "last-wins",
    "last.json",
    JSON.stringify(base()).replace(
      '"id":"urn:test:config"',
      '"id":"wrong","id":"urn:test:config"',
    ),
  ],
  [
    "utf16",
    "utf16.json",
    JSON.stringify({ ...base(), id: "\ud800", repositoryRoot: "../\udfff" }),
  ],
  ["wrong-shape", "shape.json", "{}"],
  ["missing", "missing.json", undefined],
  ["directory", ".", undefined],
  ["not-directory", "valid.json/child", undefined],
];
for (const [name, path, text] of files) {
  const action = {
    operation: "load",
    path,
    ...(text === undefined ? {} : { text }),
  };
  const expected = await observe(action, ref, output);
  caseName = "load-" + name;
  const observed = await observe(action, api, output);
  let matched = true;
  try {
    assert.deepEqual(observed, expected);
  } catch {
    matched = false;
  }
  results.push({ name: caseName, matched, expected, observed });
}
const action = {
  operation: "load",
  path: "replacement.json",
  bytes: Buffer.concat([
    Buffer.from(
      JSON.stringify(base())
        .replace('"id":"urn:test:config"', '"id":"MARKER"')
        .split("MARKER")[0],
    ),
    Buffer.from([0xff]),
    Buffer.from(
      JSON.stringify(base())
        .replace('"id":"urn:test:config"', '"id":"MARKER"')
        .split("MARKER")[1],
    ),
  ]).toString("base64"),
};
const expected = await observe(action, ref, output);
caseName = "load-utf8-replacement";
const observed = await observe(action, api, output);
let matched = true;
try {
  assert.deepEqual(observed, expected);
} catch {
  matched = false;
}
results.push({ name: caseName, matched, expected, observed });
verifyTree();
const executions = readFileSync(trace, "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
assert.equal(executions.length, results.length);
assert(
  executions.every(
    (call) =>
      call.command[0] === cli &&
      call.command[1] === "legacy" &&
      ["config", "config-file"].includes(call.command[2]) &&
      !call.processError &&
      !call.signal,
  ),
);
const matchedCount = results.filter((r) => r.matched).length;
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
);
const loaderInputs = [
  ...files.filter(([, , text]) => text !== undefined).map(([, path]) => path),
  "replacement.json",
].map((path) => ({
  path,
  digest: sha(readFileSync(join(output, path))),
  bytes: readFileSync(join(output, path)).length,
}));
const receipt = {
  schemaVersion: "1.0.0",
  status: matchedCount === results.length ? "matched" : "differences",
  supervision,
  referenceEngine: corpus.referenceEngine,
  corpus: {
    path: relative(root, corpusPath),
    digest: sha(readFileSync(corpusPath)),
  },
  candidate: {
    binaryDigest: sha(readFileSync(cli)),
    engine: JSON.parse(execFileSync(cli, ["engine"])),
    sdkSourceInventory: [
      "legacy-validation.mjs",
      "legacy-validation.d.ts",
      "legacy-config.mjs",
      "legacy-config.d.ts",
      "canonical.mjs",
    ].map((name) => ({
      path: "sdk/typescript/" + name,
      digest: sha(readFileSync(join(root, "sdk/typescript", name))),
    })),
  },
  counts: {
    cases: results.length,
    frozenParserCases: corpus.cases.length,
    loaderCases: files.length + 1,
    matched: matchedCount,
    differences: results.length - matchedCount,
    nativeExecutions: executions.length,
  },
  originalGitBlobsVerifiedBeforeAndAfter: supplement.referenceTree.length,
  scope: corpus.scope,
  results,
  traceDigest: sha(readFileSync(trace)),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
  loaderInputs,
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(root, ".tools/parity/current-config-controls.json"),
  JSON.stringify({ receipt: relative(root, join(output, "receipt.json")) }) +
    "\n",
);
console.log(
  JSON.stringify(
    {
      status: receipt.status,
      receipt: relative(root, join(output, "receipt.json")),
      ...receipt.counts,
      differences: results.filter((r) => !r.matched),
    },
    null,
    2,
  ),
);
process.exitCode = matchedCount === results.length ? 0 : 1;
