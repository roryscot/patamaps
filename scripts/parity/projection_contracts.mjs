/** Differential v1 projection contracts against the pinned original implementation. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, join, dirname } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const oracle = join(
  root,
  JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")))
    .source,
);
const lock = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
for (const f of lock.referenceTree) {
  const b = readFileSync(join(oracle, f.path));
  assert.equal(
    createHash("sha1")
      .update("blob " + b.length + "\0")
      .update(b)
      .digest("hex"),
    f.gitBlob,
    f.path,
  );
}
const original = await import(pathToFileURL(join(oracle, "dist/index.js")));
const sdk = await import(pathToFileURL(join(root, "sdk/typescript/index.mjs")));
const { marshalLegacyNumericObservationJson } = await import(
  pathToFileURL(join(root, "sdk/typescript/canonical.mjs"))
);
const executable = join(root, "target/debug/patamaps");
const candidate = sdk.createLegacyValidationApi(executable);
const routing = JSON.parse(
  readFileSync(join(oracle, "relation-packs/routing.json")),
);
const registry = () => {
  const r = new original.RelationRegistry();
  r.registerPack(routing);
  return r;
};
const nativeRegistry = () => {
  const r = new candidate.LegacyRelationRegistry();
  r.registerPack(routing);
  return r;
};
const graph = {
  schemaVersion: "2.0.0",
  id: "urn:projection:test:graph",
  namespace: "projection-test",
  revision: "1",
  relationPacks: [
    { id: "urn:metamap:relation-pack:core", version: "1.0.0" },
    { id: routing.id, version: routing.version },
  ],
  entities: [
    {
      id: "urn:test:command:z",
      kind: "routing:command",
      label: "Z",
      attributes: { path: "/z", nested: { x: 1 } },
    },
    {
      id: "urn:test:command:a",
      kind: "routing:command",
      label: "A",
      provenance: { status: "declared", assertedBy: "test:owner" },
    },
    {
      id: "urn:test:handler:z",
      kind: "routing:handler",
      locators: [{ uri: "typescript:src/z.ts#handler" }],
    },
    { id: "urn:test:handler:a", kind: "routing:handler" },
    { id: "urn:test:policy:a", kind: "routing:policy" },
  ],
  mappings: [
    ["z", "urn:test:command:z", "urn:test:handler:z"],
    ["a", "urn:test:command:a", "urn:test:handler:a"],
  ].map(([id, source, target]) => ({
    id: "urn:test:link:" + id,
    relation: "routing:handled_by",
    sources: [source],
    targets: [target],
    cardinality: "one-to-one",
    lossiness: "lossless",
    provenance: { status: "declared", assertedBy: "test:owner" },
  })),
  authorities: [],
};
const policy = {
  schemaVersion: "1.0.0",
  id: "urn:projection:test:policy",
  graph: { id: graph.id, revision: graph.revision },
  mappings: graph.mappings.map((m) => ({
    mapping: m.id,
    coverage: "total",
    determinism: "deterministic",
    reversibility: "irreversible",
  })),
  constraints: [],
  evidence: [],
};
const options = { evaluatedAt: "2026-09-02T00:00:00.000Z" };
const g = original.compileMetamap(graph, policy, {
  ...options,
  relationRegistry: registry(),
});
assert.equal(g.status, "viable", JSON.stringify(g));
assert.deepStrictEqual(
  candidate.compileLegacyMetamap(graph, policy, {
    ...options,
    relationRegistry: nativeRegistry(),
  }),
  g,
);
const spec = {
  schemaVersion: "1.0.0",
  id: "urn:projection:test:spec",
  select: { kinds: ["routing:command"] },
  slots: [
    {
      name: "handler",
      relation: "routing:handled_by",
      direction: "outgoing",
      cardinality: "exactly-one",
      targetKinds: ["routing:handler"],
    },
  ],
};
const copy = (v) => structuredClone(v);
const cases = [];
function add(name, operation, value) {
  cases.push({ name, operation, value });
}
function compilation(name, edit) {
  const value = copy({ document: graph, generation: g.generation, spec });
  edit?.(value);
  add(name, "compile", value);
}
compilation("baseline");
compilation("incoming", (v) => {
  v.spec.select = { kinds: ["routing:handler"] };
  v.spec.slots[0].direction = "incoming";
  v.spec.slots[0].targetKinds = ["routing:command"];
});
compilation(
  "intersect-selection",
  (v) => (v.spec.select.ids = ["urn:test:command:z", "urn:test:handler:a"]),
);
compilation(
  "missing-subject",
  (v) => (v.spec.select.ids = ["urn:test:absent"]),
);
compilation("empty-selection", (v) => (v.spec.select.kinds = ["missing:kind"]));
compilation("duplicate-slot", (v) => v.spec.slots.push(copy(v.spec.slots[0])));
compilation(
  "unknown-relation",
  (v) => (v.spec.slots[0].relation = "routing:unknown"),
);
compilation("stale-graph", (v) => (v.document.entities[0].label = "changed"));
compilation("wrong-graph-id", (v) => (v.document.id = "urn:test:other-graph"));
compilation(
  "invalid-generation-digest",
  (v) => (v.generation.digest = "sha256:" + "0".repeat(64)),
);
compilation("missing-required", (v) => {
  v.generation.activeMappings = [];
  readdress(v.generation, "generation");
});
compilation("optional-missing", (v) => {
  v.generation.activeMappings = [];
  readdress(v.generation, "generation");
  v.spec.slots[0].cardinality = "zero-or-one";
});
compilation("unknown-active", (v) => {
  v.generation.activeMappings.push("urn:test:absent");
  readdress(v.generation, "generation");
});
compilation(
  "wrong-target-kind",
  (v) => (v.spec.slots[0].targetKinds = ["routing:policy"]),
);
compilation("lossy-rejected", (v) => {
  v.document.mappings[0].lossiness = "lossy";
  regraph(v);
});
compilation("lossy-allowed", (v) => {
  v.document.mappings[0].lossiness = "lossy";
  v.spec.slots[0].allowLossy = true;
  regraph(v);
});
compilation("multiple-targets", (v) => {
  v.document.mappings.push({
    ...copy(v.document.mappings[0]),
    id: "urn:test:link:second",
    targets: ["urn:test:handler:a"],
  });
  v.generation.activeMappings.push("urn:test:link:second");
  regraph(v);
});
compilation("many-targets", (v) => {
  v.spec.slots[0].cardinality = "many";
  v.spec.slots.push({
    name: "authorization",
    relation: "routing:authorized_by",
    direction: "outgoing",
    cardinality: "zero-or-one",
    targetKinds: ["routing:policy"],
  });
});
compilation("version-mismatch", (v) => (v.spec.schemaVersion = "2.0.0"));
compilation("executable-policy", (v) => (v.semanticPolicy = {}));
compilation(
  "proof-claim",
  (v) =>
    (v.document.mappings[0].attributes = {
      "metamap:derivation": "urn:test:proof",
    }),
);
compilation("unordered-input", (v) => {
  v.document.entities.reverse();
  v.document.mappings.reverse();
  regraph(v);
});
compilation("unicode-private-metadata", (v) => {
  v.document.entities[0].attributes = {
    nested: { "\uE000": "\ud800", numeric: -0, other: { "\uE000": -0 } },
  };
  regraph(v);
});
// Canonically equivalent identifiers remain distinct graph identifiers, but
// compare equal under the original locale sort. Stable sorting must preserve
// the first encounter order.
for (const reversed of [false, true]) {
  compilation("collation-equal-targets-" + (reversed ? "reverse" : "forward"), (v) => {
    const ids = ["urn:test:handler:é", "urn:test:handler:e\u0301"];
    if (reversed) ids.reverse();
    v.document.entities.push(...ids.map((id) => ({ id, kind: "routing:handler" })));
    v.document.mappings[0].targets = [ids[0]];
    const second = { ...copy(v.document.mappings[0]), id: "urn:test:link:zz", targets: [ids[1]] };
    v.document.mappings.push(second);
    v.generation.activeMappings.push(second.id);
    v.spec.slots[0].cardinality = "many";
    regraph(v);
  });
}

function readdress(v, type) {
  const { $schema, id, digest, ...content } = v;
  v.digest = original.valueDigest(content);
  v.id = "urn:metamap:" + type + ":" + v.digest.slice(7);
}
function regraph(v) {
  v.generation.graph.digest = original.valueDigest(v.document);
  readdress(v.generation, "generation");
}
for (const value of [
  null,
  false,
  0,
  "bad",
  [],
  {},
  { ...spec, unknown: 1 },
  { ...spec, select: {} },
  { ...spec, select: { ids: [] } },
  { ...spec, slots: [{}] },
  { ...spec, slots: [{ ...spec.slots[0], direction: "sideways" }] },
  { ...spec, slots: [{ ...spec.slots[0], cardinality: "all" }] },
  { ...spec, slots: [{ ...spec.slots[0], targetKinds: [] }] },
  { ...spec, pathTree: { delimiter: ":" } },
  { ...spec, id: "bad" },
]) {
  add("invalid-spec-" + cases.length, "validate-spec", value);
  add("invalid-spec-parse-" + cases.length, "parse-spec", value);
}
add("valid-spec-parse", "parse-spec", copy(spec));
const baseline = original.compileProjection(graph, g.generation, spec, {
  relationRegistry: registry(),
});
assert.equal(baseline.status, "projected");
for (const value of [
  baseline.projection,
  { ...baseline.projection, digest: "sha256:" + "0".repeat(64) },
  { ...baseline.projection, id: "urn:test:wrong" },
  null,
  {},
  { ...baseline.projection, entries: [] },
]) {
  add("record-validate-" + cases.length, "validate-record", copy(value));
  add("record-parse-" + cases.length, "parse-record", copy(value));
}
function evaluate(api, native, c) {
  const value = copy(c.value);
  try {
    let result;
    switch (c.operation) {
      case "compile":
        result = (native ? api.compileLegacyProjection : api.compileProjection)(
          value.document,
          value.generation,
          value.spec,
          {
            relationRegistry: native ? nativeRegistry() : registry(),
            ...(value.semanticPolicy
              ? { semanticPolicy: value.semanticPolicy }
              : {}),
          },
        );
        break;
      case "validate-spec":
        result = (
          native ? api.validateLegacyProjectionSpec : api.validateProjectionSpec
        )(value);
        break;
      case "validate-record":
        result = (
          native ? api.validateLegacyProjection : api.validateProjection
        )(value);
        break;
      case "parse-spec":
        result = (
          native ? api.parseLegacyProjectionSpec : api.parseProjectionSpec
        )(value);
        assert.equal(result, value);
        break;
      case "parse-record":
        result = (native ? api.parseLegacyProjection : api.parseProjection)(
          value,
        );
        assert.equal(result, value);
        break;
    }
    if (result.projection) {
      assert(Object.isFrozen(result.projection));
      assert(Object.isFrozen(result.projection.entries));
    }
    return { status: "returned", value: result };
  } catch (e) {
    return { status: "threw", name: e.name, message: e.message };
  }
}
const out = resolve(
  process.argv[2] ??
    join(
      root,
      ".tools/project-adoption/legacy-projection-controls-" + Date.now(),
    ),
);
mkdirSync(out, { recursive: false });
if (process.env.PATAMAPS_PROJECTION_COLLATION_ONLY === "1") {
  const selected = cases.filter((c) => c.name.startsWith("collation-equal-targets-"));
  cases.splice(0, cases.length, ...selected);
}
const corpus = cases.map((c) => {
  const expected = evaluate(original, false, c);
  const operation = {
    compile: "projection-compile",
    "validate-spec": "projection-spec-validate",
    "parse-spec": "projection-spec-parse",
    "validate-record": "projection-validate",
    "parse-record": "projection-parse",
  }[c.operation];
  const input =
    c.operation === "compile"
      ? { ...c.value, registry: undefined }
      : { value: c.value };
  if (c.operation === "compile") {
    input.registry = {
      packs: [
        { key: "urn:metamap:relation-pack:core", version: "1.0.0" },
        { key: routing.id, version: routing.version },
      ],
      definitions: [
        ...original.coreRelationPack.relations,
        ...routing.relations,
      ].map((v) => ({ key: v.id, value: v })),
    };
    input.executablePackCount = 0;
    input.semanticPolicyPresent = Boolean(c.value.semanticPolicy);
  }
  return {
    name: c.name,
    operation,
    input: marshalLegacyNumericObservationJson(input),
    expected,
  };
});
if (process.argv[3]) {
  const frozen = corpus.map((c) => ({
    name: c.name,
    operation: c.operation,
    input: c.input,
    expectedWire:
      c.expected.status === "returned"
        ? JSON.parse(marshalLegacyNumericObservationJson(c.expected.value))
        : null,
    expectedError:
      c.expected.status === "threw"
        ? { name: c.expected.name, message: c.expected.message }
        : null,
  }));
  writeFileSync(
    resolve(process.argv[3]),
    JSON.stringify(
      {
        referenceLockDigest: createHash("sha256")
          .update(readFileSync(join(root, "fixtures/parity/supplement.json")))
          .digest("hex"),
        cases: frozen,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}

const results = [];
let failed = 0;
for (const c of cases) {
  const expected = evaluate(original, false, c),
    actual = evaluate(candidate, true, c);
  let matches = true;
  try {
    assert.deepStrictEqual(actual, expected, c.name);
  } catch {
    matches = false;
    failed++;
  }
  results.push({ ...c, expected, actual, matches });
}
writeFileSync(
  join(out, "results.json"),
  JSON.stringify(results, null, 2) + "\n",
  { flag: "wx" },
);
writeFileSync(
  join(out, "receipt.json"),
  JSON.stringify(
    {
      status: failed ? "failed" : "passed",
      cases: cases.length,
      failed,
      referenceSource: lock.referenceTree.find(
        (v) => v.path === "src/projection.ts",
      ),
      compilerDigest: createHash("sha256")
        .update(readFileSync(executable))
        .digest("hex"),
    },
    null,
    2,
  ) + "\n",
  { flag: "wx" },
);
console.log(
  JSON.stringify({
    status: failed ? "failed" : "passed",
    cases: cases.length,
    failed,
    output: out,
  }),
);
assert.equal(failed, 0, "Projection differential controls");
