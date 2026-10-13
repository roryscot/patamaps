/** Freeze the pinned original v1 compiler before implementing its candidate. */
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
      f.path,
    );
  }
}
verify();
const out = join(
  root,
  "docs/acceptance/parity",
  "viability-controls-" + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(out, { recursive: true });
const corpusPath = join(root, "fixtures/parity/viability-controls.json");
const binary = join(root, "target/debug/patamaps");
const read = (n) => JSON.parse(readFileSync(join(oracle, n)));
const document = read("examples/example-authority-graph.json");
const policy = read("examples/example-viability-policy.json");
const options = {
  context: { environment: "production", maintenance: false },
  evaluatedAt: "2026-09-02T00:00:00.000Z",
};
const copy = (v) => structuredClone(v);
const cases = [];
function add(name, operation, input) {
  cases.push({ name, action: { operation, input: JSON.stringify(input) } });
}
function compile(name, edit) {
  const input = copy({ document, policy, options });
  edit?.(input);
  add(name, "compile", input);
}
compile("baseline");
for (const [k, v] of Object.entries(policy)) {
  for (const bad of [undefined, null, false, 0, [], {}]) {
    const p = copy(policy);
    if (bad === undefined) delete p[k];
    else p[k] = bad;
    add(
      `policy-${k}-${bad === undefined ? "absent" : JSON.stringify(bad)}`,
      "validate-policy",
      { value: p },
    );
    add(
      `parse-policy-${k}-${bad === undefined ? "absent" : JSON.stringify(bad)}`,
      "parse-policy",
      { value: p },
    );
  }
}
for (const field of ["constraints", "evidence", "waivers"]) {
  const p = copy(policy);
  if (field === "waivers")
    p.waivers = [
      {
        id: p.id,
        subjects: [document.id],
        codes: ["X"],
        reason: "test",
        assertedBy: "test:team",
        expiresAt: "2027-01-01T00:00:00Z",
      },
    ];
  else p[field][0].id = p.id;
  add("duplicate-" + field, "validate-policy", { value: p });
}
for (const t of [
  "2026-09-02",
  "",
  "bad",
  "2026-02-30T00:00:00Z",
  "2026-04-31T00:00:00Z",
  "2026-01-32T00:00:00Z",
  "0000-01-01T00:00:00Z",
  "2026-09-02T24:00:00.0000Z",
  "2026-09-02T24:00:00.0001Z",
  "2026-09-02T23:59:60Z",
  "2026-09-02T00:00:00+23:59",
  "2026-09-02T00:00:00+24:00",
  "2026-09-02T00:00:00.123456789-04:00",
])
  compile("timestamp-" + t, (i) => (i.options.evaluatedAt = t));
for (const ctx of [
  {},
  { environment: "staging" },
  { environment: "production", maintenance: true },
  { environment: "development", maintenance: false },
  { environment: "production", maintenance: false, x: [null, false, 3] },
])
  compile("context-" + JSON.stringify(ctx), (i) => (i.options.context = ctx));
for (const key of ["id", "revision", "digest"])
  compile(
    "binding-" + key,
    (i) =>
      (i.policy.graph[key] =
        key === "digest" ? "sha256:" + "0".repeat(64) : "urn:missing:binding"),
  );
compile("missing-declaration", (i) => i.policy.mappings.pop());
compile("duplicate-declaration", (i) =>
  i.policy.mappings.push(copy(i.policy.mappings[0])),
);
compile(
  "unknown-declaration",
  (i) => (i.policy.mappings[0].mapping = "urn:missing:mapping"),
);
for (const select of [
  {},
  { ids: [] },
  { ids: [document.mappings[0].id] },
  { ids: ["urn:missing:mapping"] },
  { relations: ["core:contains"] },
  { sourceKinds: [document.entities[0].kind] },
  { targetKinds: [] },
  { provenanceStatuses: ["verified"] },
])
  compile("selector-" + JSON.stringify(select), (i) => {
    const d = i.policy.mappings[0];
    delete d.mapping;
    d.select = select;
  });
for (const lossiness of ["unknown", "lossy", "lossless"])
  for (const reversible of [false, true])
    compile(`semantics-${lossiness}-${reversible}`, (i) => {
      i.document.mappings[0].lossiness = lossiness;
      i.document.mappings[0].transform = {
        ...copy(document.mappings.find((m) => m.transform).transform),
        deterministic: false,
        reversible: false,
      };
      if (reversible) i.policy.mappings[0].reversibility = "reversible";
    });
for (const result of ["supports", "contradicts", "inconclusive"])
  compile("evidence-" + result, (i) => (i.policy.evidence[0].result = result));
compile("unknown-policy-subject", (i) =>
  i.policy.evidence[0].subjects.push("urn:missing:subject"),
);
compile(
  "unknown-waiver-subject",
  (i) =>
    (i.policy.waivers = [
      {
        id: "urn:test:waiver",
        subjects: ["urn:missing:subject"],
        codes: ["CONTRADICTING_EVIDENCE"],
        reason: "test",
        assertedBy: "test:team",
        expiresAt: "2027-01-01T00:00:00Z",
      },
    ]),
);
for (const expiry of [
  "2027-01-01T00:00:00Z",
  "2026-09-02T00:00:00Z",
  "2020-01-01T00:00:00Z",
  "bad",
])
  for (const repeat of [false, true])
    compile("waiver-" + expiry + "-" + repeat, (i) => {
      i.policy.evidence[0].result = "contradicts";
      i.policy.waivers = [
        {
          id: "urn:test:waiver",
          subjects: i.policy.evidence[0].subjects,
          codes: ["CONTRADICTING_EVIDENCE"],
          reason: "test",
          assertedBy: "test:team",
          expiresAt: expiry,
        },
      ];
      if (repeat)
        i.policy.waivers.push({
          ...copy(i.policy.waivers[0]),
          id: "urn:test:waiver-two",
        });
    });
compile(
  "stale-waiver",
  (i) =>
    (i.policy.waivers = [
      {
        id: "urn:test:waiver",
        subjects: [document.id],
        codes: ["CONTRADICTING_EVIDENCE"],
        reason: "test",
        assertedBy: "test:team",
        expiresAt: "2027-01-01T00:00:00Z",
      },
    ]),
);
compile(
  "proof-v1-precheck",
  (i) =>
    (i.document.mappings[0].attributes = {
      "metamap:derivation": "urn:test:proof",
    }),
);
compile("bad-graph-shape", (i) => (i.document.extra = true));
compile("bad-policy-shape", (i) => (i.policy.extra = true));
for (const changed of [
  [],
  [document.entities[0].id],
  [document.mappings[0].id],
  [policy.constraints[0].id],
  ["urn:missing:seed"],
])
  compile(
    "changed-" + JSON.stringify(changed),
    (i) => (i.options.changedSubjects = changed),
  );
const params = {
  "core:requires-evidence": [
    {},
    { minimumConfidence: 0.95 },
    { minimumConfidence: 1.1 },
    { minimumConfidence: "1" },
    { kinds: [] },
    { kinds: ["conformance-test"] },
    { kinds: [2] },
  ],
  "core:requires-mapping": [
    {},
    { relation: "core:contains" },
    { target: document.entities[0].id },
    { direction: "target" },
    { direction: "either" },
    { direction: "bad" },
    { relation: "bad" },
    { target: "" },
  ],
  "core:forbids-mapping": [
    {},
    { direction: "target" },
    { direction: "either" },
  ],
  "core:unique-target": [{}, { direction: "target" }, { direction: "either" }],
  "core:requires-authority": [
    {},
    { fact: "type" },
    { fact: "missing" },
    { fact: "" },
    { fact: 3 },
  ],
  "topology:relation-totality": [
    {},
    {
      subjectKinds: [document.entities[0].kind],
      relation: "core:contains",
      direction: "source",
      cardinality: "exactly-one",
    },
    {
      subjectKinds: [],
      relation: "core:contains",
      direction: "source",
      cardinality: "many",
    },
  ],
  "topology:reachable": [
    {},
    {
      root: document.entities[0].id,
      relation: "core:contains",
      subjectKinds: document.entities.map((e) => e.kind),
    },
  ],
  "topology:context-satisfied": [
    {},
    {
      subjectKinds: [document.entities[0].kind],
      requiresRelation: "core:contains",
      providesRelation: "core:implements",
      renderedInRelation: "core:references",
      parentRelation: "core:contains",
      hostsProviderRelation: "core:derives_from",
    },
  ],
};
for (const [kind, ps] of Object.entries(params))
  for (const p of [...ps, { z: 1, a: 2 }])
    for (const subjects of [
      [document.entities[0].id],
      [document.mappings[0].id],
    ])
      compile("constraint-" + cases.length, (i) => {
        i.policy.constraints = [
          { id: "urn:test:constraint", kind, subjects, parameters: p },
        ];
      });
for (const kind of ["bad", "urn:test:kind", "test:unknown"])
  compile(
    "unknown-kind-" + kind,
    (i) =>
      (i.policy.constraints = [
        { id: "urn:test:constraint", kind, subjects: [document.id] },
      ]),
  );
function host(result, input) {
  return {
    keys: Object.keys(result),
    issueKeys: result.issues?.map((i) => Object.keys(i)) ?? [],
    ...(result.generation
      ? {
          generationKeys: Object.keys(result.generation),
          graphKeys: Object.keys(result.generation.graph),
          sharedContext: result.generation.context === input.options.context,
          frozen: Object.isFrozen(result.generation),
          contextFrozen: Object.isFrozen(input.options.context),
          activeFrozen: Object.isFrozen(result.generation.activeMappings),
        }
      : {}),
  };
}
function observe(c, api) {
  const input = JSON.parse(c.action.input);
  try {
    let result;
    if (c.action.operation === "compile")
      result = api.compileMetamap(input.document, input.policy, input.options);
    if (c.action.operation === "validate-policy")
      result = api.validateViabilityPolicy(input.value);
    if (c.action.operation === "parse-policy") {
      result = api.parseViabilityPolicy(input.value);
      return {
        status: "observed",
        value: result,
        host: {
          shared: result === input.value,
          frozen: Object.isFrozen(result),
        },
      };
    }
    if (c.action.operation === "validate-generation")
      result = api.validateViableGeneration(input.value);
    if (c.action.operation === "parse-generation") {
      result = api.parseViableGeneration(input.value);
      return {
        status: "observed",
        value: result,
        host: {
          shared: result === input.value,
          frozen: Object.isFrozen(result),
        },
      };
    }
    return { status: "observed", value: result, host: host(result, input) };
  } catch (e) {
    return { status: "threw", error: { name: e.name, message: e.message } };
  }
}
let receipt;
if (process.argv.includes("--freeze")) {
  const api = await import(pathToFileURL(join(oracle, "dist/viability.js")));
  const generation = api.compileMetamap(
    copy(document),
    copy(policy),
    copy(options),
  ).generation;
  assert.ok(generation);
  for (const [k, v] of Object.entries(generation))
    for (const bad of [undefined, null, false, 0, [], {}]) {
      const g = copy(generation);
      if (bad === undefined) delete g[k];
      else g[k] = bad;
      add(
        `generation-${k}-${bad === undefined ? "absent" : JSON.stringify(bad)}`,
        "validate-generation",
        { value: g },
      );
      add(
        `parse-generation-${k}-${bad === undefined ? "absent" : JSON.stringify(bad)}`,
        "parse-generation",
        { value: g },
      );
    }
  add("valid-generation", "validate-generation", { value: generation });
  add("parse-valid-generation", "parse-generation", { value: generation });
  const tampered = copy(generation);
  tampered.context.environment = "staging";
  add("generation-tampered", "validate-generation", { value: tampered });
  for (const c of cases) c.expected = observe(c, api);
  verify();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: spec.referenceEngine,
        locale: new Intl.Collator().resolvedOptions().locale,
        cases,
        scope:
          "Original JSON v1 policy/generation/compiler observations. V2 semantic compilation, custom callbacks, arbitrary accessors/proxies and resource/platform acceptance remain open.",
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
  const owner = createLegacyValidationApi(binary, (c) => calls.push(c));
  const api = {
    compileMetamap: owner.compileLegacyMetamap,
    validateViabilityPolicy: owner.validateLegacyViabilityPolicy,
    parseViabilityPolicy: owner.parseLegacyViabilityPolicy,
    validateViableGeneration: owner.validateLegacyViableGeneration,
    parseViableGeneration: owner.parseLegacyViableGeneration,
  };
  const results = corpus.cases.map((c) => ({
    name: c.name,
    expected: c.expected,
    observed: observe(c, api),
  }));
  const differences = results.filter(
    (c) => JSON.stringify(c.expected) !== JSON.stringify(c.observed),
  );
  receipt = {
    schemaVersion: "1.0.0",
    status: differences.length ? "different" : "matched",
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
    },
    counts: {
      cases: results.length,
      matched: results.length - differences.length,
      differences: differences.length,
    },
    differences,
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
  join(root, ".tools/parity/current-viability-controls.json"),
  JSON.stringify({ receipt: relative(root, join(out, "receipt.json")) }) + "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    receipt: relative(root, join(out, "receipt.json")),
    counts: receipt.counts ?? { cases: receipt.cases },
    differences: receipt.differences?.slice(0, 10).map((c) => c.name),
  }),
);
assert.notEqual(receipt.status, "different");
