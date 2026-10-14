/** Independently freeze original v1 nonfinite and sparse-array observations. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";

const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const oracle = join(
  root,
  JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")))
    .source,
);
const reference = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const sha = (bytes) =>
  "sha256:" + createHash("sha256").update(bytes).digest("hex");
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
const corpusPath = join(
  root,
  "fixtures/parity/viability-numeric-controls.json",
);
const output = join(
  root,
  "docs/acceptance/parity",
  "viability-numeric-" + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(output, { recursive: true });

// Oracle encoding is independent of the candidate SDK. Facts preserve the
// values JSON.stringify would otherwise erase; no decision is normalized.
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
      return Array.from({ length: value.length }, (_, index) => {
        if (!Object.hasOwn(value, index)) {
          numbers.push({ path: [...path, String(index)], kind: "hole" });
          return 0;
        }
        return visit(value[index], [...path, String(index)]);
      });
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .filter(([, value]) => value !== undefined)
          .map(([key, value]) => [key, visit(value, [...path, key])]),
      );
    return value;
  }
  return { value: visit(value), numbers };
}
function hydrate(envelope) {
  const value = structuredClone(envelope.value);
  for (const fact of envelope.numbers) {
    const parent = fact.path
        .slice(0, -1)
        .reduce((value, key) => value[key], value),
      key = fact.path.at(-1);
    if (fact.kind === "hole") delete parent[key];
    else {
      assert.ok(
        [
          "nan",
          "negative-zero",
          "positive-infinity",
          "negative-infinity",
        ].includes(fact.kind),
      );
      parent[key] = {
        nan: NaN,
        "negative-zero": -0,
        "positive-infinity": Infinity,
        "negative-infinity": -Infinity,
      }[fact.kind];
    }
  }
  return value;
}
function observe(action, api) {
  const input = hydrate(JSON.parse(action.input));
  try {
    if (action.operation === "compile") {
      const result = api.compile(input.document, input.policy, input.options);
      return {
        status: "observed",
        value: encode(result),
        host: {
          keys: Object.keys(result),
          issueKeys: result.issues.map((issue) => Object.keys(issue)),
          ...(result.generation
            ? {
                generationKeys: Object.keys(result.generation),
                graphKeys: Object.keys(result.generation.graph),
                sharedContext:
                  result.generation.context === input.options.context,
                frozen: Object.isFrozen(result.generation),
                contextFrozen: Object.isFrozen(input.options.context),
                activeFrozen: Object.isFrozen(result.generation.activeMappings),
                contextValues: Object.entries(input.options.context).map(
                  ([key, value]) => ({
                    key,
                    shared: Object.is(result.generation.context[key], value),
                    frozen:
                      typeof value === "object" && value !== null
                        ? Object.isFrozen(value)
                        : null,
                    ...(Array.isArray(value)
                      ? { length: value.length, keys: Object.keys(value) }
                      : {}),
                  }),
                ),
              }
            : {}),
        },
      };
    }
    const value = api[action.operation](input.value);
    return {
      status: "observed",
      value: encode(value),
      host: action.operation.startsWith("parse-")
        ? {
            shared: value === input.value,
            frozen: Object.isFrozen(value),
            keys: Object.keys(value),
          }
        : {
            keys: Object.keys(value),
            issueKeys: value.issues.map((issue) => Object.keys(issue)),
          },
    };
  } catch (error) {
    return {
      status: "threw",
      error: {
        name: error.name,
        message: error.message,
        keys: Object.keys(error),
        ownNames: Object.getOwnPropertyNames(error),
        constructor: error.constructor.name,
      },
    };
  }
}

let receipt;
if (process.argv.includes("--freeze")) {
  const original = await import(
    pathToFileURL(join(oracle, "dist/viability.js"))
  );
  const stable = await import(pathToFileURL(join(oracle, "dist/stable.js")));
  const api = {
    compile: original.compileMetamap,
    "validate-policy": original.validateViabilityPolicy,
    "parse-policy": original.parseViabilityPolicy,
    "validate-generation": original.validateViableGeneration,
    "parse-generation": original.parseViableGeneration,
  };
  const document = JSON.parse(
    readFileSync(join(oracle, "examples/example-authority-graph.json")),
  );
  const baseline = JSON.parse(
    readFileSync(join(oracle, "examples/example-viability-policy.json")),
  );
  function policyBase() {
    const policy = structuredClone(baseline);
    policy.constraints = [];
    policy.evidence = [];
    for (const declaration of policy.mappings) delete declaration.applicability;
    return policy;
  }
  function compileInput(policy, context) {
    return {
      document: structuredClone(document),
      policy,
      options: { context, evaluatedAt: "2026-09-02T00:00:00.000Z" },
    };
  }
  const cases = [];
  function add(name, operation, input) {
    const action = {
      operation,
      input: JSON.stringify(encode(input)),
      locale: new Intl.Collator().resolvedOptions().locale,
    };
    cases.push({ name, action, expected: observe(action, api) });
  }
  const contexts = [
    0,
    null,
    -0,
    1,
    NaN,
    Infinity,
    -Infinity,
    [NaN],
    [Infinity],
    [-Infinity],
    [0, NaN],
    [null, Infinity],
    [-0, NaN],
    [Infinity, -Infinity, NaN],
    Array(1),
    [, 0],
    [null, ,],
    [, NaN],
    Array(2),
    [Infinity, 0],
  ];
  for (const [literalIndex, literal] of [0, null, -0].entries()) {
    for (const operator of ["equals", "not-equals", "in", "not-in"]) {
      for (const [contextIndex, context] of contexts.entries()) {
        const policy = policyBase();
        policy.mappings[0].applicability = {
          when: {
            key: "numeric",
            operator,
            ...(operator.endsWith("in")
              ? { values: [literal] }
              : { value: literal }),
          },
        };
        add(
          `${operator}-literal-${literalIndex}-context-${contextIndex}`,
          "compile",
          compileInput(policy, { numeric: context }),
        );
      }
    }
  }
  for (const [name, expression] of Object.entries({
    all: {
      all: [
        { key: "numeric", operator: "exists" },
        { key: "numeric", operator: "not-equals", value: null },
      ],
    },
    any: {
      any: [
        { key: "numeric", operator: "equals", value: null },
        { key: "numeric", operator: "equals", value: 0 },
      ],
    },
    not: { not: { key: "numeric", operator: "equals", value: null } },
  })) {
    for (const [index, context] of contexts.entries()) {
      const policy = policyBase();
      policy.mappings[0].applicability = { when: expression };
      add(
        `${name}-context-${index}`,
        "compile",
        compileInput(policy, { numeric: context }),
      );
    }
  }
  for (const [literalIndex, literal] of [NaN, Infinity, -Infinity].entries()) {
    for (const operator of ["equals", "not-equals", "in", "not-in"]) {
      const policy = policyBase();
      policy.mappings[0].applicability = {
        when: {
          key: "numeric",
          operator,
          ...(operator.endsWith("in")
            ? { values: [literal] }
            : { value: literal }),
        },
      };
      for (const [index, context] of [0, NaN].entries())
        add(
          `policy-nonfinite-${literalIndex}-${operator}-context-${index}`,
          "compile",
          compileInput(policy, { numeric: context }),
        );
      for (const operation of ["validate-policy", "parse-policy"])
        add(`${operation}-nonfinite-${literalIndex}-${operator}`, operation, {
          value: policy,
        });
    }
  }
  const generation = api.compile(document, policyBase(), {
    context: {},
    evaluatedAt: "2026-09-02T00:00:00.000Z",
  }).generation;
  assert.ok(generation);
  for (const [index, context] of contexts.entries()) {
    const value = structuredClone(generation);
    value.context = { numeric: context };
    const { $schema, id, digest, ...content } = value;
    value.digest = stable.valueDigest(content);
    value.id = "urn:metamap:generation:" + value.digest.slice(7);
    for (const operation of ["validate-generation", "parse-generation"])
      add(`${operation}-context-${index}`, operation, { value });
  }
  for (const [index, value] of [NaN, Infinity, -Infinity, [, NaN]].entries()) {
    const policy = policyBase();
    policy.constraints = [
      {
        id: "urn:test:numeric:constraint",
        kind: "test:unknown",
        subjects: [document.id],
        parameters: { extra: value },
      },
    ];
    for (const operation of ["validate-policy", "parse-policy"])
      add(`${operation}-metadata-${index}`, operation, { value: policy });
    add(
      `compile-metadata-${index}`,
      "compile",
      compileInput(policy, { numeric: 0 }),
    );
  }
  assert.equal(cases.length, 400);
  verifyReference();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: reference.referenceEngine,
        scope:
          "Original v1 plain context nonfinite numbers and sparse arrays, finite/negative-zero controls, policy nonfinite literal validation, independently addressed generation validation/parsing, and unchecked constraint metadata. Full error own-key/name/class and complete result/digest/context identity/freezing observations; no scope/expectation substitution. Other arbitrary JavaScript, custom callbacks, v2 and required package/platform domains remain open.",
        locale: new Intl.Collator().resolvedOptions().locale,
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  receipt = {
    status: "frozen-original",
    cases: cases.length,
    operationCounts: Object.fromEntries(
      [
        "compile",
        "validate-policy",
        "parse-policy",
        "validate-generation",
        "parse-generation",
      ].map((op) => [
        op,
        cases.filter((c) => c.action.operation === op).length,
      ]),
    ),
    corpusDigest: sha(readFileSync(corpusPath)),
    referenceEngine: reference.referenceEngine,
    supervision,
  };
} else {
  const corpus = JSON.parse(readFileSync(corpusPath));
  assert.equal(corpus.referenceEngine, reference.referenceEngine);
  const { createLegacyValidationApi } =
    await import("../../sdk/typescript/legacy-validation.mjs");
  const binary = join(root, "target/debug/patamaps"),
    executions = [],
    owner = createLegacyValidationApi(binary, (call) => executions.push(call));
  const api = {
    compile: owner.compileLegacyMetamap,
    "validate-policy": owner.validateLegacyViabilityPolicy,
    "parse-policy": owner.parseLegacyViabilityPolicy,
    "validate-generation": owner.validateLegacyViableGeneration,
    "parse-generation": owner.parseLegacyViableGeneration,
  };
  const differences = [];
  for (const entry of corpus.cases) {
    const observed = observe(entry.action, api);
    if (JSON.stringify(observed) !== JSON.stringify(entry.expected))
      differences.push({
        name: entry.name,
        expected: entry.expected,
        observed,
      });
  }
  verifyReference();
  writeFileSync(
    join(output, "native-executions.ndjson"),
    executions.map((call) => JSON.stringify(call)).join("\n") + "\n",
    { flag: "wx" },
  );
  receipt = {
    schemaVersion: "1.0.0",
    status: differences.length ? "different" : "matched",
    supervision,
    referenceEngine: reference.referenceEngine,
    corpus: {
      path: relative(root, corpusPath),
      digest: sha(readFileSync(corpusPath)),
    },
    candidate: {
      binaryDigest: sha(readFileSync(binary)),
      engine: JSON.parse(execFileSync(binary, ["engine"])),
      sdkSourceInventory: readdirSync(join(root, "sdk/typescript"))
        .filter(
          (name) => /\.(mjs|d\.ts)$/.test(name) || name === "package.json",
        )
        .sort()
        .map((name) => ({
          path: "sdk/typescript/" + name,
          digest: sha(readFileSync(join(root, "sdk/typescript", name))),
        })),
    },
    counts: {
      cases: corpus.cases.length,
      matched: corpus.cases.length - differences.length,
      differences: differences.length,
    },
    differences,
    scope: corpus.scope,
  };
}
receipt.driverDigest = sha(readFileSync(fileURLToPath(import.meta.url)));
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
  { flag: "wx" },
);
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
  { flag: "wx" },
);
writeFileSync(
  join(root, ".tools/parity/current-viability-numeric.json"),
  JSON.stringify({ receipt: relative(root, join(output, "receipt.json")) }) +
    "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    receipt: relative(root, join(output, "receipt.json")),
    counts: receipt.counts ?? { cases: receipt.cases },
  }),
);
assert.notEqual(receipt.status, "different");
