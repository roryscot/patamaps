/** Freeze complete original correspondence results and host identities. */
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
const corpusPath = join(root, "fixtures/parity/correspondence-controls.json");
function observe(action, materialize) {
  const input = JSON.parse(action.input);
  const before = JSON.stringify(input);
  try {
    const result = materialize(
      input.namespace,
      input.documentId,
      input.discovered,
      input.configurations,
      input.configRevision,
    );
    const records = [
      ...result.document.entities,
      ...result.document.mappings,
      ...result.document.authorities,
    ];
    const pairs = input.configurations.flatMap((c) => c.fields?.pairs ?? []);
    const facts = input.configurations
      .filter((c) => c.authority)
      .map((c) => c.authority.facts);
    return {
      status: "observed",
      value: {
        document: JSON.parse(JSON.stringify(result.document)),
        issues: JSON.parse(JSON.stringify(result.issues)),
        configuredStructureIds: [...result.configuredStructureIds],
      },
      host: {
        resultKeys: Object.keys(result),
        documentKeys: Object.keys(result.document),
        entityKeys: result.document.entities.map(Object.keys),
        mappingKeys: result.document.mappings.map(Object.keys),
        authorityKeys: result.document.authorities.map(Object.keys),
        issueKeys: result.issues.map(Object.keys),
        configuredIsSet: result.configuredStructureIds instanceof Set,
        sharedProvenance: records.every(
          (record) => record.provenance === records[0]?.provenance,
        ),
        authorityFactsRetained: result.document.authorities.map((a) =>
          facts.some((f) => f === a.facts),
        ),
        comparedFactsRetained: result.document.mappings
          .filter(
            (m) => m.attributes && Object.hasOwn(m.attributes, "comparedFacts"),
          )
          .map((m) =>
            pairs.some((p) => p.compare === m.attributes.comparedFacts),
          ),
        allowedDifferencesRetained: result.document.mappings
          .filter(
            (m) =>
              m.attributes && Object.hasOwn(m.attributes, "allowedDifferences"),
          )
          .map((m) =>
            pairs.some(
              (p) => p.allowDifferences === m.attributes.allowedDifferences,
            ),
          ),
        inputUnchanged: JSON.stringify(input) === before,
      },
    };
  } catch (error) {
    return {
      status: "threw",
      error: { name: error.name, message: error.message },
      inputUnchanged: JSON.stringify(input) === before,
    };
  }
}
if (!existsSync(corpusPath)) {
  const { materializeCorrespondences } = await import(
    pathToFileURL(join(oracle, "dist/correspondence.js"))
  );
  const cases = [];
  const entity = (id, attributes) => ({ id, kind: "discovered", attributes });
  const base = () => ({
    namespace: "test",
    documentId: "declared",
    configRevision: "sha256:config",
    discovered: {
      schemaVersion: "2.0.0",
      id: "discovered",
      namespace: "test",
      entities: [
        entity("S", {
          sourceId: "source",
          structureKind: "model",
          name: "Source",
        }),
        entity("T", {
          sourceId: "target",
          structureKind: "model",
          name: "Target",
        }),
        entity("S.id", {
          structureId: "S",
          name: "id",
          dataType: "string",
          presenceRequired: true,
          nullable: false,
          cardinality: "one",
          relation: false,
        }),
        entity("T.id", {
          structureId: "T",
          name: "id",
          dataType: "string",
          presenceRequired: true,
          nullable: false,
          cardinality: "one",
          relation: false,
        }),
      ],
      mappings: [],
      authorities: [],
    },
    configurations: [
      {
        id: "mapping",
        source: { sourceId: "source", kind: "model", name: "Source" },
        target: { sourceId: "target", kind: "model", name: "Target" },
        fields: {
          pairs: [{ source: "id", target: "id" }],
          requireSourceCoverage: true,
          requireTargetCoverage: true,
        },
        authority: { side: "target", facts: ["storage", "type"] },
      },
    ],
  });
  function add(name, change) {
    const input = base();
    change?.(input);
    const action = { input: JSON.stringify(input) };
    cases.push({
      name,
      action,
      expected: observe(action, materializeCorrespondences),
    });
  }
  add("matching-fields-authority");
  add("empty-configurations", (v) => (v.configurations = []));
  add("structures-only", (v) => delete v.configurations[0].fields);
  add("no-authority", (v) => delete v.configurations[0].authority);
  add(
    "source-authority",
    (v) => (v.configurations[0].authority.side = "source"),
  );
  add(
    "empty-authority-facts",
    (v) => (v.configurations[0].authority.facts = []),
  );
  add("duplicate-configurations", (v) =>
    v.configurations.push(structuredClone(v.configurations[0])),
  );
  add(
    "same-source-target",
    (v) => (v.configurations[0].target = { ...v.configurations[0].source }),
  );
  for (const side of ["source", "target", "both"]) {
    add("missing-" + side, (v) => {
      if (side !== "target") v.configurations[0].source.name = "missing";
      if (side !== "source") v.configurations[0].target.name = "missing";
    });
    add("ambiguous-" + side, (v) => {
      if (side !== "target")
        v.discovered.entities.push(
          entity("S-copy", { ...v.discovered.entities[0].attributes }),
        );
      if (side !== "source")
        v.discovered.entities.push(
          entity("T-copy", { ...v.discovered.entities[1].attributes }),
        );
    });
  }
  add("entity-kind-does-not-resolve-structure", (v) => {
    v.discovered.entities[0].kind = "wrong-kind";
    v.discovered.entities[1].kind = "other-kind";
  });
  add(
    "attribute-kind-mismatch",
    (v) => (v.discovered.entities[0].attributes.structureKind = "schema"),
  );
  for (const side of ["source", "target", "both"])
    add("missing-pair-" + side, (v) => {
      const p = v.configurations[0].fields.pairs[0];
      if (side !== "target") p.source = "missing";
      if (side !== "source") p.target = "missing";
    });
  add("duplicate-field-name-last-wins", (v) =>
    v.discovered.entities.push(
      entity("S.last", {
        ...v.discovered.entities[2].attributes,
        dataType: "integer",
      }),
    ),
  );
  add("duplicate-child-id-does-not-deduplicate", (v) =>
    v.discovered.entities.push(
      entity("S.id", { structureId: "S", name: "extra", dataType: "integer" }),
    ),
  );
  add("all-facts-drift", (v) =>
    Object.assign(v.discovered.entities[2].attributes, {
      dataType: "integer",
      presenceRequired: false,
      nullable: true,
      cardinality: "many",
    }),
  );
  for (const [fact, key, value] of [
    ["type", "dataType", "integer"],
    ["presence", "presenceRequired", false],
    ["nullability", "nullable", true],
    ["cardinality", "cardinality", "many"],
  ]) {
    add("only-" + fact, (v) => {
      v.discovered.entities[2].attributes[key] = value;
      v.configurations[0].fields.pairs[0].compare = [fact];
    });
    add("waived-" + fact, (v) => {
      v.discovered.entities[2].attributes[key] = value;
      Object.assign(v.configurations[0].fields.pairs[0], {
        compare: [fact],
        allowDifferences: [fact],
        note: "allowed note",
      });
    });
  }
  add("empty-comparison-keeps-coverage", (v) => {
    v.configurations[0].fields.pairs[0].compare = [];
    v.discovered.entities[2].attributes.dataType = "integer";
  });
  add("repeated-compares-and-waivers", (v) => {
    v.discovered.entities[2].attributes.dataType = "integer";
    Object.assign(v.configurations[0].fields.pairs[0], {
      compare: ["type", "type", "presence"],
      allowDifferences: ["type", "type"],
    });
  });
  add("explicit-arrays-and-transform", (v) =>
    Object.assign(v.configurations[0].fields.pairs[0], {
      compare: ["type"],
      allowDifferences: [],
      transform: "adapter:normalize",
      note: "note",
    }),
  );
  add("empty-transform-and-note", (v) =>
    Object.assign(v.configurations[0].fields.pairs[0], {
      transform: "",
      note: "",
    }),
  );
  add("nullish-optionals", (v) =>
    Object.assign(v.configurations[0].fields.pairs[0], {
      compare: null,
      allowDifferences: null,
      transform: null,
      note: null,
    }),
  );
  add("missing-vs-false-facts", (v) => {
    delete v.discovered.entities[2].attributes.nullable;
    delete v.discovered.entities[2].attributes.presenceRequired;
  });
  add("non-boolean-facts-are-unknown", (v) => {
    v.discovered.entities[2].attributes.nullable = "false";
    v.discovered.entities[2].attributes.presenceRequired = 1;
  });
  add("unknown-facts-equal", (v) => {
    for (const entity of v.discovered.entities.slice(2))
      delete entity.attributes;
  });
  for (const [i, types] of [
    ["schema", ["reference:UserSchema", "enum:USER"]],
    ["punctuation", ["enum:user-id", "reference:USER_idSchema"]],
    ["prefix-case", ["Reference:User", "enum:User"]],
    ["unicode", ["reference:ÜserSchema", "enum:Ser"]],
    ["utf8-boundary", ["reference:日abcd", "enum:abcD"]],
    ["surrogate", ["reference:\ud800UserSchema", "enum:user"]],
    ["empty", ["", "string"]],
    ["missing", [null, "string"]],
  ])
    add("symbolic-type-" + i, (v) => {
      v.discovered.entities[2].attributes.dataType = types[0];
      v.discovered.entities[3].attributes.dataType = types[1];
    });
  add("coverage-order-duplicates-and-stale-ignores", (v) => {
    v.discovered.entities.push(
      entity("S.a", { structureId: "S", name: "a" }),
      entity("S.z", { structureId: "S", name: "z" }),
      entity("S.duplicate", { structureId: "S", name: "a" }),
      entity("T.b", { structureId: "T", name: "b" }),
    );
    v.configurations[0].fields.ignoreSource = ["missing", "z", "missing"];
    v.configurations[0].fields.ignoreTarget = ["gone", "b", "gone"];
  });
  add("coverage-relation-boolean-filter", (v) => {
    v.discovered.entities.push(
      entity("S.relation", {
        structureId: "S",
        name: "relation",
        relation: true,
      }),
      entity("S.string", {
        structureId: "S",
        name: "string-relation",
        relation: "true",
      }),
    );
  });
  add("coverage-empty-field-name", (v) =>
    v.discovered.entities.push(
      entity("S.empty", { structureId: "S", name: "" }),
    ),
  );
  add("coverage-disabled-stale-ignore-remains", (v) => {
    v.configurations[0].fields.requireSourceCoverage = false;
    v.configurations[0].fields.requireTargetCoverage = false;
    v.configurations[0].fields.ignoreSource = ["stale"];
    v.discovered.entities.push(
      entity("S.unmapped", { structureId: "S", name: "unmapped" }),
    );
  });
  add("repeated-pairs-preserve-mappings", (v) =>
    v.configurations[0].fields.pairs.push({
      ...v.configurations[0].fields.pairs[0],
    }),
  );
  add("custom-relation-and-encoded-ids", (v) => {
    v.namespace = "n:space";
    v.documentId = "doc /α";
    v.configurations[0].id = "map:α /♥";
    v.configurations[0].relation = "custom:maps";
  });
  function enums(v) {
    for (const i of [0, 1]) {
      v.discovered.entities[i].attributes.structureKind = "enum";
    }
    v.configurations[0].source.kind = "enum";
    v.configurations[0].target.kind = "enum";
    delete v.configurations[0].fields;
    v.discovered.entities.push(
      entity("S.only", { structureId: "S", name: "source-only" }),
      entity("T.only", { structureId: "T", name: "target-only" }),
    );
  }
  add("enum-drift", enums);
  add("enum-waivers", (v) => {
    enums(v);
    v.configurations[0].enumValues = {
      allowSourceOnly: ["source-only", "source-only"],
      allowTargetOnly: ["target-only"],
    };
  });
  add("enum-duplicate-name", (v) => {
    enums(v);
    v.discovered.entities.push(
      entity("S.last", { structureId: "S", name: "id" }),
    );
  });
  add("enum-empty-name-skipped", (v) => {
    enums(v);
    v.discovered.entities.push(
      entity("S.empty", { structureId: "S", name: "" }),
    );
  });
  add("enum-with-field-comparison", (v) => {
    const fields = v.configurations[0].fields;
    enums(v);
    v.configurations[0].fields = fields;
  });
  add("enum-one-side-does-not-enumerate", (v) => {
    enums(v);
    v.configurations[0].target.kind = "model";
    v.discovered.entities[1].attributes.structureKind = "model";
  });
  add("unpaired-source-ids-and-provenance", (v) => {
    v.namespace = "n\ud800";
    v.configRevision = "r\udfff\ue000";
    v.discovered.entities[0].id = "S\ud800";
    v.discovered.entities[2].attributes.structureId = "S\ud800";
  });
  add(
    "unpaired-diagnostic-name-before-encoding",
    (v) => (v.configurations[0].fields.pairs[0].source = "missing\ud800"),
  );
  add(
    "unpaired-config-id-URI-error",
    (v) => (v.configurations[0].id = "id\ud800"),
  );
  add("unpaired-document-id-URI-error", (v) => (v.documentId = "doc\udfff"));
  add("null-fields-and-authority", (v) => {
    v.configurations[0].fields = null;
    v.configurations[0].authority = null;
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
          "dist/correspondence.js",
          "dist/references.js",
          "dist/model.js",
        ].map((path) => ({
          path,
          digest: sha(readFileSync(join(oracle, path))),
        })),
        scope:
          "Complete finite JSON correspondence outputs, ordered diagnostics/Set, own property order, shared provenance and retained configuration arrays. Arbitrary JS/prototypes/accessors, malformed shapes/errors, resource, package and platform obligations remain open.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpus = JSON.parse(readFileSync(corpusPath));
for (const item of corpus.originalArtifacts)
  assert.equal(sha(readFileSync(join(oracle, item.path))), item.digest);
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
if (process.argv.includes("--freeze-only")) {
  console.log(
    JSON.stringify({
      status: "original-observations-frozen",
      cases: corpus.cases.length,
      corpusDigest: sha(readFileSync(corpusPath)),
    }),
  );
  process.exit(0);
}
assert.equal(process.argv.length, 2);
const output = join(
  root,
  "docs/acceptance/parity",
  `correspondence-controls-${new Date().toISOString().replaceAll(":", "-")}`,
);
mkdirSync(output, { recursive: true });
const trace = join(output, "native-executions.ndjson");
const cli = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
let caseName;
const api = createLegacyValidationApi(cli, (e) =>
  appendFileSync(trace, JSON.stringify({ caseName, ...e }) + "\n"),
);
const results = corpus.cases.map((test) => {
  caseName = test.name;
  const observed = observe(test.action, api.materializeLegacyCorrespondences);
  let matched = true;
  try {
    assert.deepEqual(observed, test.expected);
  } catch {
    matched = false;
  }
  return { name: test.name, matched, observed };
});
verifyTree();
const executions = readFileSync(trace, "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
assert.equal(executions.length, corpus.cases.length);
assert(
  executions.every(
    (call) =>
      call.command[0] === cli &&
      call.command.slice(1).join(" ") === "legacy correspondence json" &&
      !call.processError &&
      !call.signal,
  ),
);
const matched = results.filter((r) => r.matched).length;
const receipt = {
  schemaVersion: "1.0.0",
  status: matched === results.length ? "matched" : "differences",
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
      "legacy-correspondence.mjs",
      "legacy-correspondence.d.ts",
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
  originalGitBlobsVerifiedBeforeAndAfter: supplement.referenceTree.length,
  scope:
    corpus.scope +
    " Error stacks and supplemental error.report are outside this comparison.",
  results,
  traceDigest: sha(readFileSync(trace)),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(root, ".tools/parity/current-correspondence-controls.json"),
  JSON.stringify(
    { receipt: relative(root, join(output, "receipt.json")) },
    null,
    2,
  ) + "\n",
);
console.log(
  JSON.stringify({
    receipt: relative(root, join(output, "receipt.json")),
    counts: receipt.counts,
  }),
);
process.exitCode = matched === results.length ? 0 : 1;
