/** Freeze independent expectations from the pinned reference, before comparisons.
 * Never replace an existing corpus or derive expectations from Patamaps. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const pointer = JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")));
const source = join(root, pointer.source);
const supplement = JSON.parse(readFileSync(join(root, "fixtures/parity/supplement.json")));
const sha = raw => "sha256:" + createHash("sha256").update(raw).digest("hex");
function verifyTree() {
  for (const file of supplement.referenceTree) {
    const raw = readFileSync(join(source, file.path));
    assert.equal(createHash("sha1").update(`blob ${raw.length}\0`).update(raw).digest("hex"), file.gitBlob, file.path);
  }
}
verifyTree();
const { validateDocumentShape, validateMetamapDocument } = await import(pathToFileURL(join(source, "dist/validator.js")));
const { RelationRegistry, coreRelationPack } = await import(pathToFileURL(join(source, "dist/relations.js")));
assert.deepEqual(JSON.parse(readFileSync(join(root, "crates/patamaps-core/src/legacy_core.json"))), coreRelationPack);
const original = JSON.parse(readFileSync(join(source, "examples/example-authority-graph.json")));
const cases = [];
function add(name, document, referencePacks) {
  const registry = referencePacks === undefined ? new RelationRegistry() : new RelationRegistry(referencePacks);
  const row = { name, document };
  if (referencePacks !== undefined) {
    row.referencePacks = referencePacks;
    // Named test-only schema-envelope map. Every pack identity, definition,
    // optional field and ordering remains unchanged for semantic validation.
    row.nativePacks = referencePacks.map(pack => ({ ...pack, schemaVersion: "0.1.0", documentType: "relation-pack" }));
  }
  row.expectedShape = validateDocumentShape(document);
  row.expectedValidation = validateMetamapDocument(document, registry);
  cases.push(row);
}
function change(name, mutate) {
  const document = structuredClone(original);
  mutate(document);
  add(name, document);
}
add("neutral-original-example", original);
for (const value of [null, false, 0, "", [], {}]) add(`root-${JSON.stringify(value)}`, value);
const invalids = [null, false, 0, "", [], {}];
const paths = [
  ["schemaVersion"], ["id"], ["namespace"], ["relationPacks"],
  ["relationPacks", 0], ["relationPacks", 0, "id"], ["relationPacks", 0, "version"],
  ["entities"], ["entities", 0], ["entities", 0, "id"], ["entities", 0, "kind"],
  ["entities", 1, "locators"], ["entities", 1, "locators", 0], ["entities", 1, "locators", 0, "uri"],
  ["entities", 3, "provenance"], ["entities", 3, "provenance", "status"], ["entities", 3, "provenance", "assertedBy"],
  ["mappings"], ["mappings", 0], ["mappings", 0, "id"], ["mappings", 0, "relation"],
  ["mappings", 0, "sources"], ["mappings", 0, "targets"], ["mappings", 0, "sources", 0],
  ["mappings", 0, "cardinality"], ["mappings", 0, "lossiness"], ["mappings", 0, "provenance"],
  ["authorities"], ["authorities", 0], ["authorities", 0, "id"], ["authorities", 0, "concept"],
  ["authorities", 0, "source"], ["authorities", 0, "facts"], ["authorities", 0, "facts", 0],
  ["authorities", 0, "mode"], ["authorities", 0, "provenance"],
];
for (const path of paths) {
  for (const value of [undefined, ...invalids]) {
    change(`shape-${path.join(".")}-${value === undefined ? "absent" : JSON.stringify(value)}`, document => {
      let parent = document;
      for (const key of path.slice(0, -1)) parent = parent[key];
      const key = path.at(-1);
      if (value === undefined && typeof key !== "number") delete parent[key];
      else parent[key] = value === undefined ? null : value;
    });
  }
}
for (const suffix of ["", "\n", "\r", "\r\n", "\t", " ", "\u00a0", "\u0085", "\u200e", "\u001c", "\u2028", "\u2029", "\ufeff"]) {
  change(`identifier-suffix-${JSON.stringify(suffix)}`, document => { document.id += suffix; });
}
for (const identifier of ["urn:x", "HTTP:x", "a+.-1:x", "1:x", ":x", "urn:", "urn:😀", "u_rn:x", "urñ:x"]) {
  change(`identifier-${identifier}`, document => { document.id = identifier; });
}
for (const confidence of [null, false, "0.5", -0.1, 0, 0.5, 1, 1.1]) {
  change(`confidence-${JSON.stringify(confidence)}`, document => { document.authorities[0].provenance.confidence = confidence; });
}
change("open-metadata-unknown-fields", document => {
  document.namespace = " legacy namespace with spaces ";
  document.attrs = [true, 42, null, { nested: ["😀"] }];
  document.entities[0].attrs = "open-json";
  document.entities[0].extension = { nullable: null };
  document.authorities[0].provenance.extension = [false];
});
change("duplicate-locator-warning", d => { d.entities[1].locators.push(d.entities[1].locators[0]); });
change("global-duplicate-ids", d => { d.entities.push(d.entities[0]); d.mappings[0].id = d.entities[0].id; d.authorities[0].id = d.entities[0].id; });
change("unknown-relation-and-missing-endpoints", d => { d.mappings[0].relation = "custom:unknown"; d.mappings[0].sources = ["urn:missing:source", "urn:missing:source"]; d.mappings[0].targets = ["urn:missing:target"]; });
change("unsupported-cardinality-and-mismatch", d => { d.mappings[0].cardinality = "many-to-one"; d.mappings[0].targets.push(d.mappings[0].targets[0]); });
change("missing-relation-pack", d => { d.relationPacks[0].version = "other"; });
change("authority-unknown-references-and-duplicate-facts", d => { d.authorities[0].source = "urn:missing:source"; d.authorities[0].concept = "urn:missing:concept"; d.authorities[0].facts = ["type", "type"]; });
change("candidate-authority-warning", d => { d.authorities[0].mode = "candidate"; });
change("canonical-wildcard-overlap", d => { d.authorities.push({ ...d.authorities[0], id: "urn:authority:second", facts: ["*"] }); });
const delegated = (id, parent, facts = ["type"]) => ({
  id, concept: original.authorities[0].concept, source: original.entities[4].id, facts,
  mode: "delegated", delegatedFrom: parent, provenance: {status: "declared", assertedBy: "independent-control"},
});
change("missing-delegation-parent", d => { d.authorities.push(delegated("urn:d:a", "urn:missing:parent")); });
change("candidate-parent-concept-change-fact-widening", d => {
  d.authorities[0].mode = "candidate";
  const child = delegated("urn:d:a", d.authorities[0].id, ["*"]);
  child.concept = d.entities[1].id;
  d.authorities.push(child);
});
change("delegation-cycle", d => { d.authorities.push(delegated("urn:d:a", "urn:d:b"), delegated("urn:d:b", "urn:d:a")); });
change("delegation-ancestor-is-not-branch-conflict", d => { d.authorities.push(delegated("urn:d:a", d.authorities[0].id), delegated("urn:d:b", "urn:d:a")); });
change("delegated-sibling-overlap", d => { d.authorities.push(delegated("urn:d:a", d.authorities[0].id), delegated("urn:d:b", d.authorities[0].id)); });
change("duplicate-authority-parent-last-entry-wins", d => { d.authorities.push({ ...d.authorities[0], facts: ["other"] }, delegated("urn:d:a", d.authorities[0].id)); });
change("nondelegated-present-parent-null", d => { d.authorities[0].delegatedFrom = null; });
for (const value of [null, "", "no-scheme", "urn:missing"]) change(`delegated-parent-${JSON.stringify(value)}`, d => { d.authorities[0].mode = "delegated"; d.authorities[0].delegatedFrom = value; });
const custom = {schemaVersion: "1.0.0", id: "urn:independent:pack", version: "1", relations: [
  {id: "test:restricted", cyclePolicy: "forbid", sourceKinds: ["concept"], targetKinds: ["field"], cardinalities: ["one-to-one"]},
  {id: "test:wildcard", cyclePolicy: "allow", sourceKinds: ["*"], targetKinds: ["*"]},
]};
for (const relation of ["test:restricted", "test:wildcard"]) {
  const document = structuredClone(original);
  document.mappings[0].relation = relation;
  add(`registered-kind-${relation}`, document, [coreRelationPack, custom]);
}
add("explicit-empty-registry", original, []);

// Reproducible mixed findings: declaration order, duplicate IDs/endpoints,
// n-ary cardinalities, multiple relation cycles and authority/delegation branches.
let seed = 0x73843ad1;
const pick = list => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return list[seed % list.length]; };
for (let trial = 0; trial < 160; trial++) {
  const entities = Array.from({length: 8}, (_, i) => ({id: `urn:e:${i}`, kind: pick(["field", "concept", "structure"])}));
  const endpoints = [...entities.map(e => e.id), "urn:e:missing"];
  const mappings = Array.from({length: pick([0, 1, 2, 4, 8])}, (_, i) => ({
    id: pick([`urn:m:${i}`, "urn:m:duplicate"]), relation: pick(["core:contains", "core:derives_from", "core:mirrors", "core:references", "other:unknown"]),
    sources: Array.from({length: pick([1, 2, 3])}, () => pick(endpoints)), targets: Array.from({length: pick([1, 2, 3])}, () => pick(endpoints)),
    cardinality: pick(["one-to-one", "one-to-many", "many-to-one", "many-to-many"]), lossiness: pick(["lossless", "lossy", "unknown"]), provenance: {status: "declared", assertedBy: "frozen-control"},
  }));
  const authorities = Array.from({length: pick([0, 1, 3, 6])}, (_, i) => {
    const mode = pick(["canonical", "candidate", "delegated"]);
    return {id: `urn:a:${i}`, concept: pick(endpoints.slice(0, 3)), source: pick(endpoints), facts: pick([["type"], ["*"], ["storage", "type"], ["type", "type"]]), mode,
      ...(mode === "delegated" ? {delegatedFrom: pick(["urn:a:0", "urn:a:1", "urn:a:3", "urn:missing:parent"])} : {}), provenance: {status: "declared", assertedBy: "frozen-control"}};
  });
  add(`mixed-semantic-${trial}`, {schemaVersion: "2.0.0", id: `urn:graph:${trial}`, namespace: "control", entities, mappings, authorities});
}
verifyTree();
const corpus = {
  schemaVersion: "1.0.0", referenceEngine: supplement.referenceEngine,
  scope: "Complete legacy validation outputs for JSON graph 2.0 controls. Custom typed packs use only an explicit test schema-envelope map. Non-JSON JS values, full legacy pack ingestion, admission, larger transport bounds and other registry contracts remain open.",
  referenceTreeFilesVerified: supplement.referenceTree.length,
  sourceFiles: ["src/validator.ts", "src/references.ts", "src/relations.ts", "src/model.ts", "examples/example-authority-graph.json"].map(path => ({path, digest: sha(readFileSync(join(source, path)))})),
  generatorDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
  generatedAt: new Date().toISOString(), cases,
};
const output = join(root, "fixtures/parity/legacy-validation-controls.json");
writeFileSync(output, JSON.stringify(corpus, null, 2) + "\n", {flag: "wx"});
console.log(JSON.stringify({corpus: "fixtures/parity/legacy-validation-controls.json", cases: cases.length, digest: sha(readFileSync(output))}));
