/** Independent original v2 semantic validators and dependency/view helpers. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
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
const corpusPath = join(
    root,
    "fixtures/parity/semantic-validation-controls.json",
  ),
  output = join(
    root,
    "docs/acceptance/parity",
    "semantic-validation-" + new Date().toISOString().replaceAll(":", "-"),
  );
mkdirSync(output, { recursive: true });
function decode(action) {
  if (action.kind) {
    switch (action.kind) {
      case "undefined":
        return undefined;
      case "nan":
        return NaN;
      case "infinity":
        return Infinity;
      case "bigint":
        return 1n;
      case "function":
        return () => 1;
      case "cycle": {
        const v = {};
        v.self = v;
        return v;
      }
      case "date":
        return new Date("2026-10-09T00:00:00Z");
      case "sparse":
        return new Array(2);
      case "symbol":
        return { [Symbol("extra")]: 1 };
      case "accessor":
        return Object.defineProperty({}, "value", {
          enumerable: true,
          get() {
            throw new Error("must not execute");
          },
        });
      case "undefined-member":
        return { value: undefined };
      case "unpaired":
        return String.fromCharCode(0xd800);
      case "null-prototype":
        return Object.assign(Object.create(null), { a: 1 });
    }
  }
  return JSON.parse(action.text);
}
function observe(action, api) {
  let value;
  try {
    value = decode(action);
    let result;
    if (action.operation === "dependencies")
      result = api.dependencies(
        value.graph,
        new Set(value.active),
        value.records,
      );
    else result = api[action.operation](value);
    return {
      status: "observed",
      value: JSON.parse(JSON.stringify(result)),
      host: {
        sameInput: result === value,
        keys: result && typeof result === "object" ? Object.keys(result) : null,
        issueKeys: result?.issues?.map((issue) => Object.keys(issue)) ?? null,
        ...(action.operation === "view"
          ? {
              retained: Object.keys(result)
                .filter((key) => key !== "schemaVersion")
                .map((key) => ({ key, same: result[key] === value[key] })),
              schemaVersion: result.schemaVersion,
              inputSchemaVersion: value.schemaVersion,
            }
          : {}),
      },
    };
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
  const original = await import(
      pathToFileURL(join(oracle, "dist/semantic.js"))
    ),
    canonical = await import(pathToFileURL(join(oracle, "dist/canonical.js")));
  const api = {
    "validate-policy": original.validateSemanticPolicy,
    "parse-policy": original.parseSemanticPolicy,
    "validate-generation": original.validateSemanticGeneration,
    "parse-generation": original.parseSemanticGeneration,
    digest: original.semanticGenerationDigest,
    view: original.legacyPolicyView,
    dependencies: original.admittedMappingDependencies,
  };
  const policy = JSON.parse(
      readFileSync(join(oracle, "examples/relations/generated/policy.json")),
    ),
    generation = JSON.parse(
      readFileSync(
        join(oracle, "examples/relations/generated/generation.json"),
      ),
    ),
    graph = JSON.parse(
      readFileSync(join(oracle, "examples/relations/generated/graph.json")),
    ),
    cases = [];
  const add = (name, operation, value, kind) => {
    const action = kind
      ? { operation, kind }
      : { operation, text: JSON.stringify(value) };
    cases.push({ name, action, expected: observe(action, api) });
  };
  const validate = (name, kind, value) => {
    for (const op of ["validate-", "parse-"])
      add(name + "-" + op + kind, op + kind, value);
  };
  for (const folder of ["relations", "uncertainty", "provenance"]) {
    validate(
      `baseline-${folder}`,
      "policy",
      JSON.parse(
        readFileSync(join(oracle, `examples/${folder}/generated/policy.json`)),
      ),
    );
    validate(
      `baseline-${folder}`,
      "generation",
      JSON.parse(
        readFileSync(
          join(oracle, `examples/${folder}/generated/generation.json`),
        ),
      ),
    );
  }
  for (const value of [null, false, true, 0, -0, 1.5, "text", [], {}])
    for (const kind of ["policy", "generation"])
      validate(`root-${JSON.stringify(value)}`, kind, value);
  for (const kind of [
    "undefined",
    "nan",
    "infinity",
    "bigint",
    "function",
    "cycle",
    "date",
    "sparse",
    "symbol",
    "accessor",
    "undefined-member",
    "unpaired",
    "null-prototype",
  ])
    for (const operation of [
      "validate-policy",
      "parse-policy",
      "validate-generation",
      "parse-generation",
      "digest",
    ])
      add(`host-${kind}-${operation}`, operation, undefined, kind);
  for (const [kind, base] of [
    ["policy", policy],
    ["generation", generation],
  ]) {
    for (const key of Object.keys(base)) {
      let changed = structuredClone(base);
      delete changed[key];
      validate(`remove-${kind}-${key}`, kind, changed);
      for (const replacement of [null, 42, "wrong", [], {}]) {
        changed = structuredClone(base);
        changed[key] = replacement;
        validate(
          `replace-${kind}-${key}-${JSON.stringify(replacement)}`,
          kind,
          changed,
        );
      }
    }
    const changed = structuredClone(base);
    changed.zExtra = true;
    changed.aExtra = false;
    validate(`extra-${kind}`, kind, changed);
  }
  for (const field of [
    "constraints",
    "evidence",
    "waivers",
    "derivations",
    "assessments",
    "uncertaintyRequirements",
    "riskBudgets",
  ]) {
    const changed = structuredClone(policy);
    changed[field] = [...(changed[field] ?? []), { id: policy.id }];
    validate(`duplicate-policy-${field}`, "policy", changed);
  }
  const readdress = (value) => {
    const digest = original.semanticGenerationDigest(value);
    value.digest = digest;
    value.id = "urn:metamap:generation:" + digest.slice(7);
    return value;
  };
  const mutations = {
    duplicateSummary: (g) =>
      g.semantic.uncertainty.push(structuredClone(g.semantic.uncertainty[0])),
    missingDimension: (g) => g.semantic.uncertainty[0].dimensions.pop(),
    knownUnbound: (g) =>
      (g.semantic.uncertainty[0].dimensions[0].status = "supported"),
    duplicateReference: (g) =>
      (g.semantic.uncertainty[0].dimensions[0].evidence = ["urn:e", "urn:e"]),
    missingSummary: (g) => (g.semantic.uncertainty = []),
    unboundAssessment: (g) =>
      (g.semantic.uncertainty[0].dimensions[0].assessments = ["urn:absent"]),
    unboundEvidence: (g) =>
      (g.semantic.uncertainty[0].dimensions[0].evidence = ["urn:absent"]),
    badRiskState: (g) =>
      (g.semantic.riskEvaluation = "available-for-projection"),
    proofDigest: (g) =>
      (g.semantic.derivations[0].digest = "sha256:" + "0".repeat(64)),
    proofDimension: (g) =>
      (g.semantic.derivations[0].uncertainty[1].dimension =
        g.semantic.derivations[0].uncertainty[0].dimension),
    packBinding: (g) =>
      (g.semantic.packs[0].binding.digest = "sha256:" + "0".repeat(64)),
    packValue: (g) => (g.semantic.packs[0].value.version = "changed"),
    duplicatePack: (g) =>
      g.semantic.packs.push({
        ...structuredClone(g.semantic.packs[0]),
        value: {
          ...structuredClone(g.semantic.packs[0].value),
          version: "changed",
        },
      }),
  };
  for (const [name, mutate] of Object.entries(mutations)) {
    const value = structuredClone(generation);
    mutate(value);
    readdress(value);
    validate(`semantic-generation-${name}`, "generation", value);
  }
  for (const value of [
    generation,
    { ...generation, id: "different", digest: "different" },
    { a: 1, id: "drop", digest: "drop" },
    null,
    {},
    42,
    "abc",
    [1, 2],
  ])
    add(`digest-${JSON.stringify(value).slice(0, 40)}`, "digest", value);
  for (const value of [
    policy,
    { ...policy, metadata: { x: [1, 2] }, $schema: "urn:test:schema" },
    {
      schemaVersion: "2.0.0",
      derivations: [],
      derivationLimits: { maxDepth: 3, maxDerivations: 9 },
      assessments: [],
      uncertaintyRequirements: [],
      riskBudgets: [],
      extra: { retained: true },
    },
    null,
    42,
  ])
    add(`view-${JSON.stringify(value).slice(0, 40)}`, "view", value);
  for (const active of [
    [],
    graph.mappings.map((m) => m.id),
    [graph.mappings[0].id],
    [graph.mappings.at(-1).id],
  ])
    for (const records of [generation.semantic.derivations, []])
      add(
        `dependencies-${active.join(",")}-${records.length}`,
        "dependencies",
        { graph, active, records },
      );
  const repeated = structuredClone(generation.semantic.derivations);
  repeated[0].premises.push(structuredClone(repeated[0].premises[0]));
  add("dependency-unique-premises", "dependencies", {
    graph,
    active: graph.mappings.map((m) => m.id),
    records: repeated,
  });
  verifyReference();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: reference.referenceEngine,
        cases,
        scope:
          "Complete original semantic validation/parsing and selected digest/policy-view/dependency value and host contracts, with preserved original generated examples and independently readdressed semantic mutations. Fullsemantic compilation/replay/proof execution and remaining accepted-domain/package/platform obligations remain required.",
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
  };
} else {
  const corpus = JSON.parse(readFileSync(corpusPath));
  assert.equal(corpus.referenceEngine, reference.referenceEngine);
  const configured = await import("../../sdk/typescript/legacy-validation.mjs"),
    binary = join(root, "target/debug/patamaps"),
    executions = [];
  const owner = configured.createLegacyValidationApi(binary, (call) =>
    executions.push(call),
  );
  configured.configureLegacyValidation(binary, (call) => executions.push(call));
  const apis = [owner, configured].map((api, index) => ({
      name: index ? "configured" : "factory",
      "validate-policy": api.validateLegacySemanticPolicy,
      "parse-policy": api.parseLegacySemanticPolicy,
      "validate-generation": api.validateLegacySemanticGeneration,
      "parse-generation": api.parseLegacySemanticGeneration,
      digest: api.legacySemanticGenerationDigest,
      view: api.legacyPolicyView,
      dependencies: api.admittedLegacyMappingDependencies,
    })),
    differences = [];
  for (const api of apis)
    for (const entry of corpus.cases) {
      const observed = observe(entry.action, api);
      if (JSON.stringify(observed) !== JSON.stringify(entry.expected))
        differences.push({
          name: entry.name,
          facade: api.name,
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
    status: differences.length ? "different" : "matched",
    counts: {
      cases: corpus.cases.length,
      comparisons: corpus.cases.length * apis.length,
      matched: corpus.cases.length * apis.length - differences.length,
      differences: differences.length,
    },
    differences,
    supervision,
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
  join(root, ".tools/parity/current-semantic-validation.json"),
  JSON.stringify({ receipt: relative(root, join(output, "receipt.json")) }) +
    "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    counts: receipt.counts ?? { cases: receipt.cases },
    receipt: relative(root, join(output, "receipt.json")),
  }),
);
assert.notEqual(receipt.status, "different");
