/** Independent original observations of signed-zero applicability and identity. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
import { marshalLegacyNumericObservationJson } from "../../sdk/typescript/canonical.mjs";

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
  "fixtures/parity/viability-signed-zero-controls.json",
);
const output = join(
  root,
  "docs/acceptance/parity",
  "viability-signed-zero-" + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(output, { recursive: true });
function hydrate(envelope) {
  const input = structuredClone(envelope.value);
  for (const fact of envelope.numbers) {
    assert.equal(fact.kind, "negative-zero");
    const parent = fact.path
      .slice(0, -1)
      .reduce((value, key) => value[key], input);
    parent[fact.path.at(-1)] = -0;
  }
  return input;
}
function observe(action, compile) {
  const input = hydrate(JSON.parse(action.input));
  try {
    const result = compile(input.document, input.policy, input.options);
    return {
      status: "observed",
      value: JSON.parse(marshalLegacyNumericObservationJson(result)),
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
            }
          : {}),
      },
    };
  } catch (error) {
    return {
      status: "threw",
      error: { name: error.name, message: error.message },
    };
  }
}
let receipt;
if (process.argv.includes("--freeze")) {
  const original = await import(
    pathToFileURL(join(oracle, "dist/viability.js"))
  );
  const document = JSON.parse(
    readFileSync(join(oracle, "examples/example-authority-graph.json")),
  );
  const baseline = JSON.parse(
    readFileSync(join(oracle, "examples/example-viability-policy.json")),
  );
  const cases = [];
  function add(name, expression, contextValue) {
    const policy = structuredClone(baseline);
    policy.constraints = [];
    policy.evidence = [];
    for (const declaration of policy.mappings) delete declaration.applicability;
    policy.mappings[0].applicability = { when: expression };
    const input = {
      document: structuredClone(document),
      policy,
      options: {
        context: { signed: contextValue },
        evaluatedAt: "2026-09-02T00:00:00.000Z",
      },
    };
    const action = {
      operation: "compile",
      input: marshalLegacyNumericObservationJson(input),
    };
    cases.push({
      name,
      action,
      expected: observe(action, original.compileMetamap),
    });
  }
  const contexts = [0, -0, [0], [-0], [0, -0], [-0, 0]];
  for (const [valueIndex, expected] of [0, -0].entries()) {
    for (const operator of ["equals", "not-equals", "in", "not-in"]) {
      const expression = {
        key: "signed",
        operator,
        ...(operator.endsWith("in")
          ? { values: [expected] }
          : { value: expected }),
      };
      for (const [contextIndex, actual] of contexts.entries())
        add(
          `${operator}-expected-${valueIndex}-context-${contextIndex}`,
          expression,
          actual,
        );
    }
  }
  for (const [name, expression] of Object.entries({
    all: {
      all: [
        { key: "signed", operator: "equals", value: -0 },
        { key: "signed", operator: "not-equals", value: 0 },
      ],
    },
    any: {
      any: [
        { key: "signed", operator: "equals", value: -0 },
        { key: "signed", operator: "equals", value: 1 },
      ],
    },
    not: { not: { key: "signed", operator: "equals", value: 0 } },
  }))
    for (const [index, actual] of [0, -0].entries())
      add(`${name}-context-${index}`, expression, actual);
  assert.equal(cases.length, 54);
  assert.ok(cases.every((entry) => entry.expected.status === "observed"));
  verifyReference();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: reference.referenceEngine,
        locale: new Intl.Collator().resolvedOptions().locale,
        cases,
        scope:
          "Signed-zero values in finite JSON policy expressions and context; full values, digests, native decisions and SDK identity/freezing. Nonfinite values, sparse arrays, custom callbacks, v2 and package/platform domains remain open.",
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
    referenceEngine: reference.referenceEngine,
    supervision,
    driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
  };
} else {
  const corpus = JSON.parse(readFileSync(corpusPath));
  assert.equal(corpus.referenceEngine, reference.referenceEngine);
  const { createLegacyValidationApi } =
    await import("../../sdk/typescript/legacy-validation.mjs");
  const binary = join(root, "target/debug/patamaps");
  const executions = [];
  const owner = createLegacyValidationApi(binary, (call) =>
    executions.push(call),
  );
  const differences = [];
  for (const entry of corpus.cases) {
    const observed = observe(entry.action, owner.compileLegacyMetamap);
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
    driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
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
  join(root, ".tools/parity/current-viability-signed-zero.json"),
  JSON.stringify({ receipt: relative(root, join(output, "receipt.json")) }) +
    "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    receipt: relative(root, join(output, "receipt.json")),
    counts: receipt.counts ?? { cases: receipt.cases },
    differences: receipt.differences?.map((entry) => entry.name),
  }),
);
assert.notEqual(receipt.status, "different");
