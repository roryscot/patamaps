/** Original uncertainty/risk observations; expectations never use the candidate. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const reference = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const oracle = join(
  root,
  JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")))
    .source,
);
const sha = (b) => "sha256:" + createHash("sha256").update(b).digest("hex");
function verifyReference() {
  for (const file of reference.referenceTree) {
    const bytes = readFileSync(join(oracle, file.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${bytes.length}\0`)
        .update(bytes)
        .digest("hex"),
      file.gitBlob,
      file.path,
    );
  }
}
verifyReference();
const corpusPath = join(root, "fixtures/parity/uncertainty-risk-controls.json");
const output = join(
  root,
  "docs/acceptance/parity",
  "uncertainty-risk-" + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(output, { recursive: true });

// Independent observation encoding retains numeric facts and caller aliases.
function encode(value) {
  const numbers = [];
  function visit(value, path = []) {
    if (
      typeof value === "number" &&
      (!Number.isFinite(value) || Object.is(value, -0))
    ) {
      numbers.push({
        path,
        kind: Number.isNaN(value)
          ? "nan"
          : Object.is(value, -0)
            ? "negative-zero"
            : value > 0
              ? "positive-infinity"
              : "negative-infinity",
      });
      return 0;
    }
    if (Array.isArray(value))
      return value.map((entry, i) => visit(entry, [...path, String(i)]));
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, visit(v, [...path, k])]),
      );
    return value;
  }
  return { value: visit(value), numbers };
}
function hydrate(envelope) {
  const value = structuredClone(envelope.value);
  for (const fact of envelope.numbers) {
    const parent = fact.path.slice(0, -1).reduce((v, k) => v[k], value),
      key = fact.path.at(-1);
    parent[key] = {
      nan: NaN,
      "negative-zero": -0,
      "positive-infinity": Infinity,
      "negative-infinity": -Infinity,
    }[fact.kind];
  }
  return value;
}
function decode(action) {
  const input = hydrate(action.input);
  if (action.kind) {
    let value;
    switch (action.kind) {
      case "undefined":
        value = undefined;
        break;
      case "bigint":
        value = 1n;
        break;
      case "function":
        value = () => 1;
        break;
      case "date":
        value = new Date("2026-10-09T00:00:00Z");
        break;
      case "cycle":
        value = {};
        value.self = value;
        break;
      case "symbol":
        value = { [Symbol("extra")]: 1 };
        break;
      case "accessor":
        value = Object.defineProperty({}, "value", {
          enumerable: true,
          get() {
            throw new Error("must not execute");
          },
        });
        break;
      case "undefined-member":
        value = { value: undefined };
        break;
      case "unpaired":
        value = String.fromCharCode(0xd800);
        break;
      case "null-prototype":
        value = Object.assign(Object.create(null), {
          assessments: [],
          evidence: [],
        });
        break;
    }
    input.inputs = value;
  }
  return input;
}
function observe(action, api) {
  const input = decode(action);
  try {
    let result;
    switch (action.operation) {
      case "empty":
        result = api.empty;
        break;
      case "validate":
        result = api.validate(
          input.graph,
          input.inputs,
          input.prospective,
          input.proofIds,
        );
        break;
      case "unknown":
        result = api.unknown(input.dimension);
        break;
      case "combine":
        result = api.combine(input.dimension, input.values);
        break;
      case "mapping":
        result = api.mapping(
          input.graph,
          input.mapping,
          input.inputs,
          input.premises,
        );
        break;
      case "dependencies":
        result = api.dependencies(input.summary, input.inputs);
        break;
      case "graph":
        result = api.graph(input.graph, input.proofs, input.inputs);
        break;
      case "summary":
        result = api.summary(input.summaries);
        break;
      case "requirements":
        result = api.requirements(
          input.graph,
          new Set(input.active),
          input.summaries,
          input.requirements,
          input.inputs,
        );
        break;
      case "budgets":
        result = api.budgets(input.graph, input.budgets);
        break;
      case "risk":
        result = api.risk(
          input.graph,
          input.generation,
          input.spec,
          input.used,
        );
        break;
      default:
        throw new Error("Unknown control operation");
    }
    const host = {
      keys: result && typeof result === "object" ? Object.keys(result) : null,
    };
    if (Array.isArray(result))
      host.itemKeys = result.map((v) =>
        v && typeof v === "object" ? Object.keys(v) : null,
      );
    if (result?.issues)
      host.issueKeys = result.issues.map((v) => Object.keys(v));
    if (action.operation === "empty")
      host.frozen = [
        Object.isFrozen(result),
        Object.isFrozen(result.assessments),
        Object.isFrozen(result.evidence),
      ];
    if (action.operation === "graph")
      host.proofAliases = result.map((entry) => {
        const mapping = input.graph.mappings.find(
          (m) => m.id === entry.mapping,
        );
        const proof = [...input.proofs]
          .reverse()
          .find((p) => p.id === mapping.attributes?.["metamap:derivation"]);
        return proof ? entry.dimensions === proof.uncertainty : null;
      });
    if (action.operation === "risk")
      host.summaryAliases = result.risk.uncertainty.map(
        (entry) =>
          entry ===
          [...input.generation.semantic.uncertainty]
            .reverse()
            .find((v) => v.mapping === entry.mapping),
      );
    return { status: "observed", value: encode(result), host };
  } catch (error) {
    return {
      status: "threw",
      error: {
        name: error.name,
        message: error.message,
        constructor: error.constructor?.name,
        keys: Object.keys(error),
        ownNames: Object.getOwnPropertyNames(error),
      },
    };
  }
}
let receipt;
if (process.argv.includes("--freeze")) {
  const u = await import(pathToFileURL(join(oracle, "dist/uncertainty.js"))),
    r = await import(pathToFileURL(join(oracle, "dist/risk.js")));
  const api = {
    empty: u.emptyUncertaintyInputs,
    validate: u.validateUncertaintyInputs,
    unknown: u.unknownDimension,
    combine: u.combineUncertainty,
    mapping: u.mappingUncertainty,
    dependencies: u.uncertaintyDependencies,
    graph: u.graphUncertainty,
    summary: u.uncertaintySummaryIssues,
    requirements: u.uncertaintyRequirementIssues,
    budgets: r.consumerBudgetIssues,
    risk: r.evaluateConsumerRisk,
  };
  const graph = JSON.parse(
      readFileSync(join(oracle, "examples/uncertainty/generated/graph.json")),
    ),
    policy = JSON.parse(
      readFileSync(join(oracle, "examples/uncertainty/generated/policy.json")),
    ),
    generation = JSON.parse(
      readFileSync(
        join(oracle, "examples/uncertainty/generated/generation.json"),
      ),
    );
  const inputs = { assessments: policy.assessments, evidence: policy.evidence },
    dimensions = [
      "identity",
      "context",
      "provenance",
      "completeness",
      "causal-relevance",
      "conflicting-authority",
    ],
    states = ["supported", "contradicted", "unknown", "not-applicable"],
    cases = [];
  const add = (name, operation, input, kind) => {
    const action = {
      operation,
      input: encode(input),
      ...(kind ? { kind } : {}),
    };
    cases.push({ name, action, expected: observe(action, api) });
  };
  const unknown = (d) => ({
    dimension: d,
    status: "unknown",
    evidence: [],
    assessments: [],
    measurementModels: [],
    sourceRevisions: [],
  });
  add("empty-frozen", "empty", {});
  for (const dimension of dimensions) {
    add("unknown-" + dimension, "unknown", { dimension });
    add("empty-combine-" + dimension, "combine", { dimension, values: [] });
    for (const a of states)
      for (const b of states)
        for (const models of [[], ["model:one"], ["model:two"]])
          add(
            `meet-${dimension}-${a}-${b}-${models.length ? models[0] : "empty"}`,
            "combine",
            {
              dimension,
              values: [
                {
                  ...unknown(dimension),
                  status: a,
                  evidence: ["urn:z", "urn:z", "urn:\u{10000}"],
                  assessments: ["urn:a"],
                  measurementModels: ["model:one"],
                  sourceRevisions: ["rev:z"],
                },
                {
                  ...unknown(dimension),
                  status: b,
                  evidence: ["urn:\ue000", "urn:a"],
                  assessments: ["urn:b", "urn:a"],
                  measurementModels: models,
                  sourceRevisions: ["rev:a"],
                },
              ],
            },
          );
  }
  add("validate-original", "validate", { graph, inputs });
  for (const value of [
    null,
    false,
    1,
    "text",
    [],
    {},
    { assessments: [] },
    { evidence: [] },
    { assessments: [], evidence: [], extra: true },
  ])
    add("validate-root-" + JSON.stringify(value), "validate", {
      graph,
      inputs: value,
    });
  for (const kind of [
    "undefined",
    "bigint",
    "function",
    "date",
    "cycle",
    "symbol",
    "accessor",
    "undefined-member",
    "unpaired",
    "null-prototype",
  ])
    add("validate-host-" + kind, "validate", { graph, inputs }, kind);
  for (const [field, records] of Object.entries(inputs))
    for (const key of Object.keys(records[0] ?? {}))
      for (const replacement of [null, 17, "wrong", [], {}]) {
        const value = structuredClone(inputs);
        value[field][0][key] = replacement;
        add(
          `validate-${field}-${key}-${JSON.stringify(replacement)}`,
          "validate",
          { graph, inputs: value },
        );
      }
  for (const field of ["assessments", "evidence"])
    if (inputs[field].length) {
      const value = structuredClone(inputs);
      value[field].push(structuredClone(value[field][0]));
      add("duplicate-" + field, "validate", { graph, inputs: value });
    }
  if (inputs.assessments.length) {
    for (const change of [
      (a) => (a.subject = "urn:missing"),
      (a) => (a.sourceRevision = "stale"),
      (a) => (a.evidence = ["urn:missing"]),
    ]) {
      const value = structuredClone(inputs);
      change(value.assessments[0]);
      add("assessment-change-" + cases.length, "validate", {
        graph,
        inputs: value,
      });
    }
  }
  add("prospective-collision", "validate", {
    graph,
    inputs,
    prospective: "urn:prospective",
    proofIds: [graph.entities[0].id, graph.entities[0].id],
  });
  for (const mapping of graph.mappings) {
    add("mapping-original-" + mapping.id, "mapping", {
      graph,
      mapping,
      inputs,
      premises: [],
    });
    add("mapping-premise-" + mapping.id, "mapping", {
      graph,
      mapping,
      inputs,
      premises: [dimensions.map(unknown)],
    });
  }
  const summaries = u.graphUncertainty(graph, policy.derivations, inputs);
  add("graph-original", "graph", { graph, proofs: policy.derivations, inputs });
  add("graph-last-proof", "graph", {
    graph,
    proofs: [
      ...policy.derivations,
      ...policy.derivations.map((proof) => ({
        ...proof,
        uncertainty: dimensions.map(unknown),
      })),
    ],
    inputs,
  });
  for (const summary of summaries)
    add("dependencies-" + summary.mapping, "dependencies", {
      summary: summary.dimensions,
      inputs,
    });
  add("summary-original", "summary", { summaries });
  add("summary-duplicate", "summary", {
    summaries: [...summaries, ...summaries],
  });
  for (const change of [
    (s) => s.dimensions.pop(),
    (s) => (s.dimensions[0].status = "supported"),
    (s) => (s.dimensions[0].evidence = ["urn:x", "urn:x"]),
    (s) => (s.dimensions[0].assessments = ["urn:x", "urn:x"]),
    (s) => (s.dimensions[0].measurementModels = ["model", "model"]),
    (s) => (s.dimensions[0].sourceRevisions = ["rev", "rev"]),
  ]) {
    const value = [
      { mapping: graph.mappings[0].id, dimensions: dimensions.map(unknown) },
    ];
    change(value[0]);
    add("summary-mutation-" + cases.length, "summary", { summaries: value });
  }
  for (const dimension of dimensions)
    for (const allowedStates of [[], ["supported"], ["unknown"], states])
      for (const requireEvidence of [false, true])
        add(
          `require-${dimension}-${allowedStates.join("-")}-${requireEvidence}`,
          "requirements",
          {
            graph,
            active: graph.mappings.map((m) => m.id),
            summaries,
            requirements: [
              {
                id: "urn:requirement",
                select: { ids: graph.mappings.map((m) => m.id) },
                dimension,
                allowedStates,
                requireEvidence,
              },
            ],
            inputs,
          },
        );
  const req = {
    id: "urn:requirement",
    select: { ids: ["urn:missing"] },
    dimension: "identity",
    allowedStates: ["supported"],
    requireEvidence: true,
  };
  add("requirements-stale-duplicate", "requirements", {
    graph,
    active: [],
    summaries,
    requirements: [req, req],
    inputs,
  });
  const budget = {
    id: "urn:budget",
    consumer: "urn:consumer",
    maximumTotalCost: 5,
    requireCompleteClassification: true,
    requireCompleteDependencies: true,
    classifications: graph.mappings.map((m, i) => ({
      id: "urn:class:" + i,
      select: { ids: [m.id] },
      classification: "cost:" + i,
      cost: i,
    })),
  };
  const riskGeneration = {
      ...generation,
      semantic: {
        ...generation.semantic,
        riskBudgets: [budget],
        uncertainty: summaries,
      },
    },
    spec = {
      schemaVersion: "2.0.0",
      id: "urn:spec",
      consumer: budget.consumer,
      budget: budget.id,
      select: {},
      slots: [],
    },
    used = graph.mappings.map((m) => m.id);
  add("budget-original", "budgets", { graph, budgets: [budget] });
  add("budget-duplicate", "budgets", { graph, budgets: [budget, budget] });
  const numeric = [
    -1,
    0,
    -0,
    1,
    1.5,
    Number.MAX_SAFE_INTEGER,
    Number.MAX_SAFE_INTEGER + 1,
    NaN,
    Infinity,
    -Infinity,
    null,
    true,
    false,
    "0",
    "-1",
    "junk",
  ];
  for (const value of numeric) {
    const b = structuredClone(budget);
    b.classifications[0].cost = value;
    add("budget-cost-" + cases.length, "budgets", { graph, budgets: [b] });
    add("risk-cost-" + cases.length, "risk", {
      graph,
      generation: {
        ...riskGeneration,
        semantic: { ...riskGeneration.semantic, riskBudgets: [b] },
      },
      spec,
      used,
    });
  }
  for (const field of [
    "maximumTotalCost",
    "maximumLossyMappings",
    "maximumInferredMappings",
  ])
    for (const value of numeric) {
      const b = { ...budget, [field]: value };
      add("budget-limit-" + cases.length, "budgets", { graph, budgets: [b] });
      add("risk-limit-" + cases.length, "risk", {
        graph,
        generation: {
          ...riskGeneration,
          semantic: { ...riskGeneration.semantic, riskBudgets: [b] },
        },
        spec,
        used,
      });
    }
  for (const change of [
    (b) => (b.classifications = []),
    (b) => b.classifications.push({ ...b.classifications[0] }),
    (b) => (b.classifications[0].select.ids = ["urn:missing"]),
    (b) => b.classifications.forEach((r) => (r.cost = Number.MAX_SAFE_INTEGER)),
    (b) => (b.consumer = "urn:other"),
    (b) => (b.metadata = { ignored: NaN }),
  ]) {
    const b = structuredClone(budget);
    change(b);
    add("risk-change-" + cases.length, "risk", {
      graph,
      generation: {
        ...riskGeneration,
        semantic: { ...riskGeneration.semantic, riskBudgets: [b] },
      },
      spec,
      used,
    });
  }
  for (const selected of [null, "urn:missing", budget.id])
    for (const selectedMappings of [
      [],
      used,
      [...used, ...used],
      [...used, "urn:missing"],
    ])
      add("risk-selection-" + cases.length, "risk", {
        graph,
        generation: riskGeneration,
        spec: { ...spec, budget: selected },
        used: selectedMappings,
      });
  add("risk-last-summary", "risk", {
    graph,
    generation: {
      ...riskGeneration,
      semantic: {
        ...riskGeneration.semantic,
        uncertainty: [
          ...summaries,
          ...summaries.map((s) => ({
            ...s,
            dimensions: dimensions.map(unknown),
          })),
        ],
      },
    },
    spec,
    used,
  });
  const corpus = {
    schemaVersion: "1.0.0",
    referenceEngine: reference.referenceEngine,
    scope:
      "Complete original uncertainty/risk helper operations and finite typed/numeric/identity refusals; full compiler/proof/projection, arbitrary accepted domains and required package/platform acceptance remain open.",
    cases,
  };
  writeFileSync(corpusPath, JSON.stringify(corpus, null, 2) + "\n", {
    flag: "wx",
  });
  receipt = {
    status: "frozen-from-original-only",
    cases: cases.length,
    operations: [...new Set(cases.map((c) => c.action.operation))],
  };
} else {
  const corpus = JSON.parse(readFileSync(corpusPath)),
    binary = join(root, "target/debug/patamaps"),
    sdk = await import(
      pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
    ),
    executions = [];
  sdk.configureLegacyValidation(binary, (call) => executions.push(call));
  const owner = sdk.createLegacyValidationApi(binary, (call) =>
    executions.push(call),
  );
  const apis = [owner, sdk].map((a) => ({
    empty: a.legacyEmptyUncertaintyInputs,
    validate: a.validateLegacyUncertaintyInputs,
    unknown: a.legacyUnknownDimension,
    combine: a.combineLegacyUncertainty,
    mapping: a.legacyMappingUncertainty,
    dependencies: a.legacyUncertaintyDependencies,
    graph: a.legacyGraphUncertainty,
    summary: a.legacyUncertaintySummaryIssues,
    requirements: a.legacyUncertaintyRequirementIssues,
    budgets: a.legacyConsumerBudgetIssues,
    risk: a.evaluateLegacyConsumerRisk,
  }));
  const differences = [];
  let matched = 0;
  for (const [index, api] of apis.entries())
    for (const entry of corpus.cases) {
      const observed = observe(entry.action, api);
      if (JSON.stringify(observed) === JSON.stringify(entry.expected))
        matched++;
      else
        differences.push({
          facade: index ? "configured" : "factory",
          name: entry.name,
          expected: entry.expected,
          observed,
        });
    }
  writeFileSync(
    join(output, "native-executions.ndjson"),
    executions.map((c) => JSON.stringify(c)).join("\n") + "\n",
  );
  receipt = {
    status: differences.length ? "different" : "matched",
    counts: {
      cases: corpus.cases.length,
      comparisons: corpus.cases.length * 2,
      matched,
      different: differences.length,
    },
    differences,
    candidate: {
      binaryDigest: sha(readFileSync(binary)),
      engine: JSON.parse(execFileSync(binary, ["engine"])),
      sdkSourceInventory: readdirSync(join(root, "sdk/typescript"))
        .filter((n) => /\.(mjs|ts)$/.test(n))
        .map((n) => ({
          path: "sdk/typescript/" + n,
          digest: sha(readFileSync(join(root, "sdk/typescript", n))),
        })),
    },
  };
}
verifyReference();
receipt = {
  ...receipt,
  supervision,
  corpus: {
    path: relative(root, corpusPath),
    digest: sha(readFileSync(corpusPath)),
  },
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
  join(root, ".tools/parity/current-uncertainty-risk.json"),
  JSON.stringify({ receipt: relative(root, join(output, "receipt.json")) }) +
    "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    receipt: relative(root, join(output, "receipt.json")),
    counts: receipt.counts,
    cases: receipt.cases,
  }),
);
if (receipt.status === "different") process.exitCode = 1;
