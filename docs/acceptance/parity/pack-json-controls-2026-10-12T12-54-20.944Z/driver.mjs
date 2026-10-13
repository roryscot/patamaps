/** Freeze original JSON pack observations before comparing the native API.
 * This component probe cannot close the full JavaScript/file/registry contract.
 */
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
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
function verifyTree() {
  for (const entry of supplement.referenceTree) {
    const raw = readFileSync(join(oracle, entry.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${raw.length}\0`)
        .update(raw)
        .digest("hex"),
      entry.gitBlob,
      entry.path,
    );
  }
}
verifyTree();
const corpusPath = join(root, "fixtures/parity/pack-json-controls.json");
if (!existsSync(corpusPath)) {
  const original = await import(
    pathToFileURL(join(oracle, "dist/relation-pack.js"))
  );
  const cases = [];
  function add(name, value) {
    let expected;
    try {
      const parsed = original.parseRelationPack(value);
      assert.equal(parsed, value, "Original parser identity");
      expected = {
        status: "accepted",
        digest: original.relationPackDigest(parsed),
      };
    } catch (error) {
      expected = {
        status: "refused",
        error: { name: error.name, message: error.message },
      };
    }
    cases.push({ name, value, expected });
  }
  const portable = {
    schemaVersion: "1.0.0",
    id: "urn:pack:control",
    version: "1",
    relations: [{ id: "test:edge", cyclePolicy: "allow" }],
  };
  const executable = { ...portable, schemaVersion: "2.0.0", laws: [] };
  for (const base of [portable, executable]) {
    const version = base.schemaVersion;
    add(`neutral-${version}`, structuredClone(base));
    for (const path of [
      ["schemaVersion"],
      ["id"],
      ["version"],
      ["relations"],
      ["relations", 0],
      ["relations", 0, "id"],
      ["relations", 0, "cyclePolicy"],
    ]) {
      for (const value of [undefined, null, false, 0, "", [], {}]) {
        const changed = structuredClone(base);
        let parent = changed;
        for (const key of path.slice(0, -1)) parent = parent[key];
        if (value === undefined && typeof path.at(-1) === "string")
          delete parent[path.at(-1)];
        else parent[path.at(-1)] = value === undefined ? null : value;
        add(
          `${version}-${path.join(".")}-${value === undefined ? "absent" : JSON.stringify(value)}`,
          changed,
        );
      }
    }
    for (const patch of [
      { newMandatoryFeature: true },
      { unknownA: true, unknownB: false },
      { id: null, version: false },
      { $schema: null, description: 0 },
      { $schema: 'relative/"quoted' },
      { $schema: "https://example.test/schema" },
      { $schema: "not a URI" },
      { description: "😀\u{e000}\u{e001}" },
      { description: "\ud800" },
      { version: "\udfff" },
    ])
      add(`${version}-patch-${JSON.stringify(patch)}`, {
        ...structuredClone(base),
        ...patch,
      });
    for (const fields of [
      { sourceKinds: [] },
      { sourceKinds: ["\ud800", "\u{e000}\u{e001}"] },
      { sourceKinds: ["x", "x"] },
      { sourceKinds: ["a", "b", "a", "b", "a"] },
      { sourceKinds: ["__proto__", "__proto__"] },
      { sourceKinds: ["constructor", "constructor"] },
      { sourceKinds: [null, null] },
      { sourceKinds: [0, 0] },
      { targetKinds: "x" },
      { cardinalities: ["invalid"] },
      {
        cardinalities: [
          "one-to-one",
          "many-to-one",
          "one-to-one",
          "many-to-one",
          "one-to-one",
        ],
      },
      { inverse: "INVALID" },
      { cyclePolicy: "unknown" },
      { id: false, cyclePolicy: "unknown" },
      { unknownA: true, unknownB: false },
      { transitive: "yes" },
    ]) {
      const changed = structuredClone(base);
      Object.assign(changed.relations[0], fields);
      add(`${version}-relation-${JSON.stringify(fields)}`, changed);
    }
  }
  for (const value of [null, false, 0, "", [], {}, { schemaVersion: "9.0.0" }])
    add(`root-${JSON.stringify(value)}`, value);
  verifyTree();
  const sourceFiles = [
    "src/relation-pack.ts",
    "src/canonical.ts",
    "src/stable.ts",
    "schemas/relation-pack.schema.json",
    "schemas/relation-pack-v2.schema.json",
  ].map((path) => ({ path, digest: sha(readFileSync(join(oracle, path))) }));
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        sourceFiles,
        scope:
          "Finite plain JSON pack shape, parser identity, version-specific valid digests and exact thrown name/message. Does not establish arbitrary JS objects, unchecked digest inputs, file parsing/errors or resource-bound equivalence.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpusBytes = readFileSync(corpusPath);
const corpus = JSON.parse(corpusBytes);
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
for (const entry of corpus.sourceFiles)
  assert.equal(sha(readFileSync(join(oracle, entry.path))), entry.digest);
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(
  root,
  "docs/acceptance/parity",
  `pack-json-controls-${stamp}`,
);
mkdirSync(output);
const binary = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
let currentCase,
  calls = 0;
const api = createLegacyValidationApi(binary, (execution) => {
  calls++;
  appendFileSync(
    join(output, "native-executions.ndjson"),
    JSON.stringify({ caseName: currentCase, ...execution }) + "\n",
  );
  assert.equal(execution.command[0], binary);
  assert.equal(execution.signal, null);
  assert.equal(execution.processError, null);
});
const results = [];
for (const row of corpus.cases) {
  currentCase = row.name;
  const before = JSON.stringify(row.value);
  let observed;
  try {
    const parsed = api.parseLegacyRelationPack(row.value);
    assert.equal(parsed, row.value, "Native-backed parser identity");
    observed = {
      status: "accepted",
      digest: api.digestLegacyRelationPack(parsed),
    };
  } catch (error) {
    observed = {
      status: "refused",
      error: { name: error.name, message: error.message },
    };
  }
  assert.equal(JSON.stringify(row.value), before, "Caller data changed");
  results.push({
    name: row.name,
    expected: row.expected,
    observed,
    equal: JSON.stringify(observed) === JSON.stringify(row.expected),
  });
}
verifyTree();
const differences = results.filter((row) => !row.equal);
const receipt = {
  schemaVersion: "1.0.0",
  status: differences.length
    ? "differences-observed"
    : "component-controls-passed",
  supervision,
  reference: {
    engine: corpus.referenceEngine,
    corpus: relative(root, corpusPath),
    corpusDigest: sha(corpusBytes),
    sourceFiles: corpus.sourceFiles,
  },
  candidate: {
    binaryDigest: sha(readFileSync(binary)),
    engine: JSON.parse(execFileSync(binary, ["engine"], { env: {} })),
    sdkSourceInventory: ["canonical.mjs", "legacy-validation.mjs"].map(
      (name) => ({
        path: `sdk/typescript/${name}`,
        digest: sha(readFileSync(join(root, "sdk/typescript", name))),
      }),
    ),
  },
  comparedCases: results.length,
  matchedCases: results.length - differences.length,
  nativeExecutions: calls,
  results,
  differences,
  originalCasesClosed: 0,
  scope: corpus.scope,
  traceDigest: sha(readFileSync(join(output, "native-executions.ndjson"))),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
  { flag: "wx" },
);
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    comparedCases: results.length,
    matchedCases: receipt.matchedCases,
    differences: differences.length,
    receipt: relative(root, join(output, "receipt.json")),
  }),
);
// Differences are retained diagnostic findings, never a successful parity gate.
process.exitCode = differences.length ? 1 : 0;
