/** Freeze original registry observations before candidate comparison. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  appendFileSync,
} from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
import { scenarios } from "../../fixtures/parity/registry-scenarios.mjs";
const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
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
const corpusPath = join(root, "fixtures/parity/registry-controls.json");
const scenariosPath = join(root, "fixtures/parity/registry-scenarios.mjs");
function observe(scenario, api) {
  try {
    return {
      status: "observed",
      value: JSON.parse(JSON.stringify(scenario(api))),
    };
  } catch (error) {
    return {
      status: "threw",
      error: { name: error.name, message: error.message },
    };
  }
}
if (!existsSync(corpusPath)) {
  const relations = await import(
    pathToFileURL(join(oracle, "dist/relations.js"))
  );
  const pack = await import(
    pathToFileURL(join(oracle, "dist/relation-pack.js"))
  );
  const original = { ...relations, ...pack };
  const cases = scenarios.map(([name, scenario]) => ({
    name,
    expected: observe(scenario, original),
  }));
  verifyTree();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        scenarioDigest: sha(readFileSync(scenariosPath)),
        originalRuntime: process.version,
        originalArtifacts: [
          "dist/relations.js",
          "dist/relation-pack.js",
          "dist/stable.js",
        ].map((path) => ({
          path,
          digest: sha(readFileSync(join(oracle, path))),
        })),
        scope:
          "Frozen original outcomes for finite portable-data registration, queries, identity, mutations and executable law decisions; arbitrary JS objects and complete public contracts remain unresolved.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpus = JSON.parse(readFileSync(corpusPath));
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
assert.equal(corpus.scenarioDigest, sha(readFileSync(scenariosPath)));
assert.equal(corpus.cases.length, scenarios.length);
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(
  root,
  "docs/acceptance/parity",
  `registry-controls-${stamp}`,
);
mkdirSync(output, { recursive: true });
const trace = join(output, "native-executions.ndjson");
const cli = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
let caseName;
const results = [];
for (let index = 0; index < scenarios.length; index++) {
  const [name, scenario] = scenarios[index];
  caseName = name;
  assert.equal(name, corpus.cases[index].name);
  const api = createLegacyValidationApi(cli, (execution) =>
    appendFileSync(trace, JSON.stringify({ caseName, ...execution }) + "\n"),
  );
  const candidate = {
    RelationRegistry: api.LegacyRelationRegistry,
    coreRelationPack: api.legacyCoreRelationPack,
    relationPackDigest: (value) => api.digestLegacyRelationPack(value),
  };
  const observed = observe(scenario, candidate);
  let matched = true;
  try {
    assert.deepEqual(observed, corpus.cases[index].expected);
  } catch {
    matched = false;
  }
  results.push({
    name,
    matched,
    observed,
    expected: corpus.cases[index].expected,
  });
}
verifyTree();
const executions = readFileSync(trace, "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
assert(
  executions.every(
    (call) => call.command[0] === cli && !call.processError && !call.signal,
  ),
);
assert(
  results.every((row) =>
    executions.some(
      (call) => call.caseName === row.name && call.command[2] === "registry",
    ),
  ),
);
const matched = results.filter((row) => row.matched).length;
const receipt = {
  schemaVersion: "1.0.0",
  status: matched === results.length ? "matched" : "differences",
  supervision,
  referenceEngine: corpus.referenceEngine,
  corpus: {
    path: relative(root, corpusPath),
    digest: sha(readFileSync(corpusPath)),
  },
  scenarios: {
    path: relative(root, scenariosPath),
    digest: sha(readFileSync(scenariosPath)),
  },
  candidate: {
    binaryDigest: sha(readFileSync(cli)),
    engine: JSON.parse(execFileSync(cli, ["engine"])),
    sdkSourceInventory: [
      "legacy-registry.mjs",
      "legacy-validation.mjs",
      "legacy-validation.d.ts",
      "canonical.mjs",
    ].map((name) => ({
      path: `sdk/typescript/${name}`,
      digest: sha(readFileSync(join(root, "sdk/typescript", name))),
    })),
  },
  counts: {
    cases: results.length,
    matched,
    differences: results.length - matched,
    nativeExecutions: executions.length,
  },
  scope:
    "Component comparison only; no full export or arbitrary-JavaScript registry obligation is closed. Reference observations were frozen first; candidate registration/law/selection requests execute Rust. SDK identity and freeze observations are compared as booleans. Supplemental error.report and stack details remain outside this comparison.",
  originalGitBlobsVerifiedBeforeAndAfter: supplement.referenceTree.length,
  results,
  traceDigest: sha(readFileSync(trace)),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
  { flag: "wx" },
);
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
  { flag: "wx" },
);
console.log(
  JSON.stringify(
    {
      status: receipt.status,
      receipt: relative(root, join(output, "receipt.json")),
      ...receipt.counts,
    },
    null,
    2,
  ),
);
process.exitCode = matched === results.length ? 0 : 1;
