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

const corpusPath = join(root, "fixtures/parity/workspace-controls.json");
const base = () => ({
  schemaVersion: "1.0.0",
  id: "urn:test:workspace",
  namespace: "test",
  repository: "fixture",
  repositoryRoot: ".",
  sources: [
    { id: "source", adapter: "custom" },
    { id: "target", adapter: "custom" },
  ],
  correspondences: [],
  outputs: {
    graph: "generated/graph.json",
    snapshot: "generated/snapshot.json",
    report: "generated/report.md",
    documentation: "generated/graph.md",
  },
});
const correspondence = JSON.parse(
  readFileSync(join(root, "fixtures/parity/correspondence-controls.json")),
).cases[0];
const seed = JSON.parse(correspondence.action.input);
function adapters() {
  return ["source", "target"].map((sourceId, i) => ({
    sourceId,
    adapter: "fixture",
    adapterVersion: "1.0.0",
    inputs: [
      { path: sourceId + ".txt", digest: "sha256:" + String(i).repeat(64) },
    ],
    diagnostics: [],
    document: {
      schemaVersion: "2.0.0",
      id: "urn:test:shard:" + sourceId,
      namespace: "test",
      entities: seed.discovered.entities
        .filter((e) => e.id.startsWith(i ? "T" : "S"))
        .map((e) => ({
          ...structuredClone(e),
          id: "urn:test:" + e.id,
          attributes: {
            ...e.attributes,
            ...(e.attributes.structureId
              ? { structureId: "urn:test:" + e.attributes.structureId }
              : {}),
          },
        })),
      mappings: [],
      authorities: [],
    },
  }));
}
function host(result, input) {
  return {
    keys: Object.keys(result),
    graphKeys: result.graph ? Object.keys(result.graph) : undefined,
    adapterArrayFresh: result.adapters
      ? result.adapters !== input.adapters
      : undefined,
    adapterIdentities: result.adapters?.map((a, i) => a === input.adapters[i]),
    snapshotInputIdentities: result.snapshot?.sources.map(
      (s, i) => s.inputs === input.adapters[i].inputs,
    ),
    entityIdentities: result.graph?.entities.map((e) =>
      input.adapters.flatMap((a) => a.document.entities).includes(e),
    ),
    mappingKeys: result.graph?.mappings.map(Object.keys),
    authorityKeys: result.graph?.authorities.map(Object.keys),
  };
}
function observe(action, api, Registry) {
  const input = JSON.parse(action.input);
  try {
    let value;
    if (action.operation === "assemble") {
      const reg = new Registry();
      for (const p of input.registeredPacks ?? []) reg.registerPack(p);
      value = api.assembleWorkspace(
        input.config,
        input.adapters,
        input.configuredPacks,
        reg,
        input.options ?? {},
      );
    } else if (action.operation === "snapshot")
      value = api.makeWorkspaceSnapshot(
        input.graph,
        input.adapters,
        input.configDigest,
      );
    else value = api.workspaceHasErrors(input.discovery);
    return {
      status: "observed",
      value,
      ...(action.operation === "assemble"
        ? { host: host(value, input) }
        : action.operation === "snapshot"
          ? {
              inputIdentities: value.sources.map(
                (s, i) => s.inputs === input.adapters[i].inputs,
              ),
            }
          : {}),
    };
  } catch (error) {
    return {
      status: "threw",
      error: {
        name: error.name,
        message: error.message,
        identifier: error.identifier ?? null,
      },
    };
  }
}
if (!existsSync(corpusPath)) {
  const api = await import(pathToFileURL(join(oracle, "dist/workspace.js")));
  const { RelationRegistry } = await import(
    pathToFileURL(join(oracle, "dist/relations.js"))
  );
  const cases = [];
  const add = (name, operation, input) => {
    const action = { operation, input: JSON.stringify(input) };
    cases.push({
      name,
      action,
      expected: observe(action, api, RelationRegistry),
    });
  };
  const input = () => ({
    config: base(),
    adapters: adapters(),
    configuredPacks: [],
    options: {},
  });
  add("empty-correspondences", "assemble", input());
  {
    let v = input();
    v.config.correspondences = seed.configurations;
    add("complete-correspondence", "assemble", v);
    v.adapters[1].document.entities[1].attributes.dataType = "number";
    add("field-drift", "assemble", v);
    v.config.correspondences[0].fields.pairs[0].allowDifferences = ["type"];
    add("waived-field-drift", "assemble", v);
  }
  for (const severity of ["ignore", "warning", "error"]) {
    let v = input();
    v.config.policy = { unconfiguredStructures: severity };
    add("unconfigured-" + severity, "assemble", v);
    for (const external of [true, false, "true", null]) {
      v = input();
      v.config.policy = { unconfiguredStructures: severity };
      v.adapters[0].document.entities[0].attributes.externalReference =
        external;
      add("external-" + severity + "-" + cases.length, "assemble", v);
    }
  }
  for (const count of [0, 1, 12, 13, 32]) {
    let v = input();
    v.config.policy = { unconfiguredStructures: "warning" };
    v.adapters[0].document.entities = Array.from({ length: count }, (_, i) => ({
      id: "urn:test:extra:" + i,
      kind: "discovered",
      attributes: {
        sourceId: i % 2 ? "first" : "second",
        structureKind: "model",
        name: "m" + i,
      },
    }));
    add("coverage-threshold-" + count, "assemble", v);
  }
  for (const label of [undefined, "", null, "é", "\ud800"]) {
    let v = input();
    if (label !== undefined) v.config.label = label;
    add("label-" + cases.length, "assemble", v);
  }
  for (const id of ["urn:test:é", "urn:test:\ue000", "urn:test:\ud800"]) {
    let v = input();
    v.config.id = id;
    add("config-id-" + cases.length, "assemble", v);
  }
  {
    let v = input();
    v.adapters = [];
    add("no-shards", "assemble", v);
    v = input();
    v.adapters[1].document.id = v.adapters[0].document.id;
    add("duplicate-shard", "assemble", v);
    v = input();
    v.adapters[0].document.schemaVersion = "3.0.0";
    add("unsupported-shard", "assemble", v);
  }
  {
    let v = input();
    v.adapters[1].document.entities.push(v.adapters[0].document.entities[0]);
    add("identical-entity-merge", "assemble", v);
    v.adapters[1].document.entities.at(-1).label = "changed";
    add("conflicting-entity-merge", "assemble", v);
  }
  const pack = {
    schemaVersion: "1.0.0",
    id: "urn:test:pack",
    version: "1.0.0",
    relations: [{ id: "custom:edge", cyclePolicy: "allow" }],
  };
  for (const portable of [false, true]) {
    let v = input();
    v.configuredPacks = [{ configuredPath: "a b/relations.json", pack }];
    v.registeredPacks = [pack];
    v.options.portablePackUris = portable;
    add("configured-pack-" + portable, "assemble", v);
  }
  {
    let v = input();
    v.adapters[0].document.relationPacks = [{ id: pack.id, version: "2.0.0" }];
    v.configuredPacks = [{ configuredPath: "pack.json", pack }];
    v.registeredPacks = [pack];
    add("conflicting-pack-version", "assemble", v);
  }
  {
    let v = input();
    v.adapters[0].document.entities.push({ id: "bad id", kind: "" });
    add("validation-errors", "assemble", v);
    v = input();
    v.adapters[0].document.mappings = [
      {
        id: "urn:test:unknown",
        relation: "missing:edge",
        source: ["urn:test:S"],
        target: ["urn:absent"],
        cardinality: "one-to-one",
        lossiness: "unknown",
      },
    ];
    add("validation-missing-semantics", "assemble", v);
  }
  for (const revision of [undefined, "", null, "r1", "\ud800"]) {
    const graph = {
      schemaVersion: "2.0.0",
      id: "urn:snapshot",
      namespace: "test",
      entities: [],
      mappings: [],
      authorities: [],
      ...(revision === undefined ? {} : { revision }),
    };
    add("snapshot-revision-" + cases.length, "snapshot", {
      graph,
      adapters: adapters(),
      configDigest: "sha256:config",
    });
  }
  for (const valid of [true, false])
    for (const severity of ["warning", "error", "ignore"])
      for (const group of ["adapter", "drift"]) {
        const discovery = {
          validation: { valid, issues: [] },
          adapters: [
            {
              diagnostics:
                group === "adapter"
                  ? [{ severity, code: "D", message: "m" }]
                  : [],
            },
          ],
          driftIssues:
            group === "drift" ? [{ severity, code: "D", message: "m" }] : [],
        };
        add("has-errors-" + cases.length, "has-errors", { discovery });
      }
  verifyTree();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        originalRuntime: process.version,
        originalArtifacts: [
          "dist/workspace.js",
          "dist/composer.js",
          "dist/correspondence.js",
          "dist/relations.js",
          "dist/report.js",
          "dist/stable.js",
        ].map((path) => ({
          path,
          digest: sha(readFileSync(join(oracle, path))),
        })),
        scope:
          "Original complete workspace assembly/snapshot/error decisions, including whole graph/adapters/diagnostics/validation/hash/order and retained source identities. Discovery/cache/baseline/output IO and registry are separately compared on retained fixtures. Complete public accepted-domain/package/platform obligations remain open.",
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
  `workspace-controls-${new Date().toISOString().replaceAll(":", "-")}`,
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
  assembleWorkspace: facade.assembleLegacyWorkspace,
  makeWorkspaceSnapshot: facade.makeLegacyWorkspaceSnapshot,
  workspaceHasErrors: facade.legacyWorkspaceHasErrors,
};
const results = corpus.cases.map((test) => {
  caseName = test.name;
  const observed = observe(test.action, api, facade.LegacyRelationRegistry);
  let matched = true;
  try {
    assert.deepEqual(observed, test.expected);
  } catch {
    matched = false;
  }
  return { name: test.name, matched, observed };
});
verifyTree();
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
      "legacy-workspace.mjs",
      "legacy-workspace.d.ts",
      "canonical.mjs",
    ].map((name) => ({
      path: "sdk/typescript/" + name,
      digest: sha(readFileSync(join(root, "sdk/typescript", name))),
    })),
  },
  counts: {
    cases: results.length,
    matched,
    differences: results.length - matched,
  },
  results,
  traceDigest: sha(readFileSync(trace)),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
);
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(root, ".tools/parity/current-workspace-controls.json"),
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
process.exitCode = matched === results.length ? 0 : 1;
