import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { resolve, dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const oracle = join(
  root,
  JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")))
    .source,
);
const spec = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const sha = (b) => "sha256:" + createHash("sha256").update(b).digest("hex");
function verify() {
  for (const f of spec.referenceTree) {
    const b = readFileSync(join(oracle, f.path));
    assert.equal(
      createHash("sha1").update(`blob ${b.length}\0`).update(b).digest("hex"),
      f.gitBlob,
    );
  }
}
verify();
const out = join(
  root,
  "docs/acceptance/parity",
  "migration-controls-" + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(out, { recursive: true });
const corpusPath = join(root, "fixtures/parity/migration-controls.json");
const binary = join(root, "target/debug/patamaps");
const entry = {
  id: "a",
  label: "A",
  paths: ["src/a.rs"],
  outputs: ["generated/a.ts"],
  updateSteps: "build",
  note: "N",
  specDoc: "docs/spec.md",
};
const cases = [];
function add(name, operation, input) {
  cases.push({ name, action: { operation, input: JSON.stringify(input) } });
}
for (const [i, value] of [
  null,
  false,
  0,
  "x",
  [],
  {},
  { sourcesOfTruth: null },
  { sourcesOfTruth: [] },
  { sourcesOfTruth: [null] },
  { sourcesOfTruth: [entry] },
  ...["id", "label", "paths", "outputs"].flatMap((k) =>
    [undefined, 1, null, true, {}, ["ok", 1]].map((v) => ({
      sourcesOfTruth: [{ ...entry, [k]: v }],
    })),
  ),
].entries())
  add("predicate-" + i, "is-migration", { value });
const base = { description: "Legacy", sourcesOfTruth: [entry] };
add("ordinary", "migration", { legacy: base });
add("empty", "migration", { legacy: { sourcesOfTruth: [] } });
for (const paths of [
  [],
  ["one"],
  ["a", "b"],
  ["a OR b", "src/*.rs"],
  ["a\\b", "./a/b", "././a"],
  ["é😀/a", "a b", "a//b"],
])
  add("paths-" + JSON.stringify(paths), "migration", {
    legacy: { sourcesOfTruth: [{ ...entry, paths }] },
  });
for (const outputs of [
  [],
  ["description"],
  ["a/b"],
  ["a /b", "a\\b", "/a", "a/b?x"],
])
  add("outputs-" + JSON.stringify(outputs), "migration", {
    legacy: { sourcesOfTruth: [{ ...entry, outputs }] },
  });
for (const options of [
  {},
  {
    namespace: "other",
    repository: "repo/é",
    documentId: "urn:custom",
    label: "custom",
  },
  { namespace: "", repository: "", documentId: "", label: "" },
  { namespace: null, repository: null, documentId: null, label: null },
  { namespace: "\ud800\ue000", label: "\udfff\ue001" },
  { repository: "\ud800" },
])
  add("options-" + JSON.stringify(options), "migration", {
    legacy: base,
    options,
  });
for (const [key, values] of Object.entries({
  id: ["é/😀", "\ud800"],
  label: ["\ud800", ""],
  updateSteps: ["", null, 0, "\ue000\ud800"],
  note: ["", null, false, "\udfff"],
  specDoc: ["", null, "é/spec", "\ud800"],
}))
  for (const [i, v] of values.entries())
    add("entry-" + key + "-" + i, "migration", {
      legacy: { sourcesOfTruth: [{ ...entry, [key]: v }] },
    });
add("duplicate-concept-last-value-first-position", "migration", {
  legacy: { sourcesOfTruth: [entry, { ...entry, label: "Last", outputs: [] }] },
});
add("shared-artifacts-last-definition-first-position", "migration", {
  legacy: {
    sourcesOfTruth: [
      entry,
      {
        ...entry,
        id: "b",
        specDoc: "src/a.rs",
        outputs: ["generated/a.ts", "description"],
      },
    ],
  },
});
function observe(action, api) {
  const input = JSON.parse(action.input);
  try {
    const value =
      action.operation === "is-migration"
        ? api.isLegacySourceOfTruthDocument(input.value)
        : api.adaptLegacySourcesOfTruth(input.legacy, input.options);
    return {
      status: "observed",
      value: JSON.parse(JSON.stringify(value)),
      ...(action.operation === "migration"
        ? {
            host: {
              resultKeys: Object.keys(value),
              documentKeys: Object.keys(value.document),
              entityKeys: value.document.entities.map(Object.keys),
              mappingKeys: value.document.mappings.map(Object.keys),
              authorityKeys: value.document.authorities.map(Object.keys),
              allProvenanceShared: [
                ...value.document.entities,
                ...value.document.mappings,
                ...value.document.authorities,
              ].every((v, i, all) => v.provenance === all[0].provenance),
              provenanceFrozen: value.document.entities.length
                ? Object.isFrozen(value.document.entities[0].provenance)
                : false,
            },
          }
        : {}),
    };
  } catch (e) {
    return {
      status: "threw",
      error: {
        name: e.name,
        message: e.message,
        ...(e.code ? { code: e.code } : {}),
      },
    };
  }
}
let receipt;
if (process.argv.includes("--freeze")) {
  const original = await import(
    pathToFileURL(join(oracle, "dist/adapters/source-of-truth.js"))
  );
  for (const c of cases) c.expected = observe(c.action, original);
  verify();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: spec.referenceEngine,
        cases,
        scope:
          "Complete frozen JSON values/errors and own-member order/shared provenance for these source catalog fixtures; no full arbitrary-JavaScript/package/platform closure.",
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  receipt = {
    status: "frozen-original",
    cases: cases.length,
    corpusDigest: sha(readFileSync(corpusPath)),
  };
} else {
  const corpus = JSON.parse(readFileSync(corpusPath));
  const { createLegacyValidationApi } =
    await import("../../sdk/typescript/legacy-validation.mjs");
  const calls = [];
  const api = createLegacyValidationApi(binary, (c) => calls.push(c));
  const results = corpus.cases.map((c) => ({
    name: c.name,
    expected: c.expected,
    observed: observe(c.action, api),
  }));
  const diffs = results.filter(
    (c) => JSON.stringify(c.expected) !== JSON.stringify(c.observed),
  );
  receipt = {
    schemaVersion: "1.0.0",
    status: diffs.length ? "different" : "matched",
    supervision,
    referenceEngine: spec.referenceEngine,
    driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
    corpus: {
      path: relative(root, corpusPath),
      digest: sha(readFileSync(corpusPath)),
    },
    candidate: {
      binaryDigest: sha(readFileSync(binary)),
      engine: JSON.parse(execFileSync(binary, ["engine"])),
      sdkSourceInventory: [
        "legacy-cli.mjs",
        "legacy-cli.d.ts",
        "legacy-validation.mjs",
        "legacy-validation.d.ts",
        "canonical.mjs",
      ].map((n) => ({
        path: "sdk/typescript/" + n,
        digest: sha(readFileSync(join(root, "sdk/typescript", n))),
      })),
    },
    counts: {
      cases: results.length,
      matched: results.length - diffs.length,
      differences: diffs.length,
    },
    differences: diffs,
    scope: corpus.scope,
  };
  writeFileSync(
    join(out, "native-executions.ndjson"),
    calls.map((c) => JSON.stringify(c)).join("\n") + "\n",
  );
}
writeFileSync(
  join(out, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(out, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
);
writeFileSync(
  join(root, ".tools/parity/current-migration-controls.json"),
  JSON.stringify({ receipt: relative(root, join(out, "receipt.json")) }) + "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    receipt: relative(root, join(out, "receipt.json")),
    counts: receipt.counts ?? { cases: receipt.cases },
    differences: receipt.differences?.map((c) => c.name),
  }),
);
assert.notEqual(receipt.status, "different");
