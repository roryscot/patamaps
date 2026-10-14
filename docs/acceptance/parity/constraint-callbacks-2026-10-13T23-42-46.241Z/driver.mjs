/** Independent original registry, evaluator and custom compiler observations. */
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
  process.argv.includes("--host")
    ? "fixtures/parity/constraint-callback-host-controls.json"
    : "fixtures/parity/constraint-callback-controls.json",
);
const output = join(
  root,
  "docs/acceptance/parity",
  (process.argv.includes("--host")
    ? "constraint-callback-host-"
    : "constraint-callbacks-") + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(output, { recursive: true });
const kinds = [
  "core:requires-evidence",
  "core:requires-mapping",
  "core:forbids-mapping",
  "core:unique-target",
  "core:requires-authority",
  "topology:relation-totality",
  "topology:reachable",
  "topology:context-satisfied",
];
// Transport-only observation encoder, independent of the candidate SDK.
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
function errorObservation(error) {
  return {
    name: error?.name,
    message: error?.message ?? String(error),
    constructor: error?.constructor?.name,
    keys: error && typeof error === "object" ? Object.keys(error) : [],
    ownNames:
      error && typeof error === "object"
        ? Object.getOwnPropertyNames(error)
        : [],
  };
}
function policyBase(baseline) {
  const value = structuredClone(baseline);
  value.constraints = [];
  value.evidence = [];
  for (const declaration of value.mappings) delete declaration.applicability;
  return value;
}
function observe(action, api, document, baseline) {
  const events = [],
    issues = [],
    contexts = [];
  let thrown;
  try {
    if (action.operation === "registry") {
      if (action.mode === "subclass") {
        const registrations = [];
        class Subclass extends api.Registry {
          register(kind, evaluator) {
            registrations.push({
              kind,
              name: evaluator.name,
              receiver: this instanceof Subclass,
            });
            return super.register(kind, evaluator);
          }
        }
        const registry = new Subclass();
        return {
          status: "observed",
          value: {
            registrations,
            keys: Object.keys(registry),
            prototype: registry instanceof Subclass,
          },
        };
      }
      if (action.mode === "cross-instance") {
        const first = new api.Registry(),
          second = new api.Registry();
        return {
          status: "observed",
          value: kinds.map((kind) => first.get(kind) === second.get(kind)),
        };
      }
      if (action.mode === "borrowed") {
        const target = { evaluators: new Map() },
          evaluator = () => [];
        const result = api.Registry.prototype.register.call(
          target,
          "test:borrowed",
          evaluator,
        );
        return {
          status: "observed",
          value: {
            registerUndefined: result === undefined,
            retained:
              api.Registry.prototype.get.call(target, "test:borrowed") ===
              evaluator,
            missing:
              api.Registry.prototype.get.call(target, "test:missing") ===
              undefined,
          },
        };
      }
      const registry = new api.Registry();
      const originals = kinds.map((kind) => registry.get(kind));
      const builtins = originals.map((fn, index) => ({
        kind: kinds[index],
        name: fn.name,
        length: fn.length,
        stable: registry.get(kinds[index]) === fn,
      }));
      let key = action.key;
      if (key === "@nan") key = NaN;
      if (key === "@negative-zero") key = -0;
      if (key === "@symbol") key = Symbol("key");
      if (key === "@object") key = {};
      if (action.mode === "construct")
        return {
          status: "observed",
          value: {
            builtins,
            keys: Object.keys(registry),
            missing: registry.get("test:absent") === undefined,
          },
        };
      const fn = function custom() {
        return [];
      };
      const supplied =
        action.mode === "undefined"
          ? undefined
          : action.mode === "null"
            ? null
            : action.mode === "false"
              ? false
              : fn;
      const registered = registry.register(key, supplied);
      if (action.mode === "duplicate") registry.register(key, fn);
      return {
        status: "observed",
        value: {
          builtins,
          registerUndefined: registered === undefined,
          retained: registry.get(key) === supplied,
          zeroAlias: key === 0 ? registry.get(0) === supplied : null,
          keys: Object.keys(registry),
        },
      };
    }
    const doc = structuredClone(document),
      policy = policyBase(baseline),
      options = {
        context: { environment: "production", maintenance: false },
        evaluatedAt: "2026-09-02T00:00:00.000Z",
      };
    const registry = new api.Registry();
    if (action.operation === "builtin") {
      const graph = new api.Graph(doc);
      if (action.graphMutation === "replace-authorities") doc.authorities = [];
      if (action.graphMutation === "mutate-authority")
        doc.authorities[0].owner = "urn:test:callback:mutated-owner";
      const constraint = {
        id: "urn:test:callback:builtin",
        kind: action.kind,
        subjects: [doc.entities[0].id],
        ...(action.parameters === undefined
          ? {}
          : { parameters: action.parameters }),
      };
      const activeMappings = new Set(doc.mappings.map((m) => m.id)),
        evidence = structuredClone(baseline.evidence);
      const result = registry.get(action.kind)(constraint, {
        document: doc,
        graph,
        activeMappings,
        evidence,
      });
      return {
        status: "observed",
        value: encode(result),
        host: {
          issueKeys: result.map((i) => Object.keys(i)),
          documentUnchanged: JSON.stringify(doc) === JSON.stringify(document),
          evidenceUnchanged:
            JSON.stringify(evidence) === JSON.stringify(baseline.evidence),
          active: [...activeMappings],
        },
      };
    }
    const names = action.callbacks ?? [action.mode];
    const constraints = names.map((mode, index) => ({
      id: `urn:test:callback:${index}`,
      kind: `test:callback-${index}`,
      subjects: [doc.mappings[0].id],
      parameters: { mode },
    }));
    policy.constraints = constraints;
    let firstGraph, firstSet, firstContext;
    const sharedIssue = {
      severity: "error",
      code: "REQUIRED_MAPPING_MISSING",
      message: "shared issue",
      subjectId: doc.mappings[0].id,
      path: undefined,
      extra: "retained",
    };
    const get = registry.get;
    registry.get = function (kind) {
      events.push({ lookup: kind, receiver: this === registry });
      return get.call(this, kind);
    };
    for (const [index, mode] of names.entries())
      registry.register(
        `test:callback-${index}`,
        function (constraint, context) {
          if (!firstGraph) {
            firstGraph = context.graph;
            firstSet = context.activeMappings;
            firstContext = context;
          }
          contexts.push(context);
          events.push({
            callback: index,
            receiverUndefined: this === undefined,
            sameConstraint: constraint === constraints[index],
            sameDocument: context.document === doc,
            graphDocument: context.graph.document === doc,
            sameGraph: context.graph === firstGraph,
            sameSet: context.activeMappings === firstSet,
            freshContext: index === 0 || context !== firstContext,
            sameEvidence: context.evidence === policy.evidence,
            contextKeys: Object.keys(context),
            active: [...context.activeMappings],
            entityIdentity:
              context.graph.getEntity(document.entities[0].id) ===
              doc.entities[0],
          });
          if (mode === "throw-error" || mode === "throw-typeerror") {
            thrown =
              mode === "throw-error"
                ? new Error("callback failure")
                : new TypeError("callback failure");
            throw thrown;
          }
          if (mode === "active-clear") context.activeMappings.clear();
          if (mode === "active-add")
            context.activeMappings.add("urn:test:callback:external");
          if (mode === "mutate-context") options.context.numeric = NaN;
          if (mode === "mutate-policy-id")
            policy.id = "urn:test:callback:mutated-policy";
          if (mode === "mutate-document-id")
            doc.id = "urn:test:callback:mutated-document";
          if (mode === "mutate-mappings") policy.mappings = [];
          if (mode === "replace-evidence") policy.evidence = [];
          if (mode === "append-constraint")
            policy.constraints.push({
              id: "urn:test:callback:late",
              kind: "test:absent",
              subjects: [doc.id],
            });
          if (mode === "delete-next") delete constraints[index + 1];
          if (mode === "shared-error") {
            issues.push(sharedIssue);
            return [sharedIssue];
          }
          if (
            [
              "warning",
              "error",
              "waived",
              "frozen-error",
              "frozen-warning",
              "frozen-bare-warning",
              "frozen-waived",
              "bare-warning",
            ].includes(mode)
          ) {
            const issue = {
              severity: mode.includes("warning") ? "warning" : "error",
              code: mode.includes("waived")
                ? "REQUIRED_MAPPING_MISSING"
                : "CUSTOM_CALLBACK",
              message: "custom issue",
              subjectId: doc.mappings[0].id,
              path: undefined,
              extra: { retained: true },
            };
            if (mode.includes("bare")) delete issue.subjectId;
            if (mode.startsWith("frozen-")) Object.freeze(issue);
            issues.push(issue);
            return [issue];
          }
          return [];
        },
      );
    if (action.waiver)
      policy.waivers = [
        {
          id: "urn:test:callback:waiver",
          codes: ["REQUIRED_MAPPING_MISSING"],
          subjects: [doc.mappings[0].id],
          reason: "fixture",
          assertedBy: "test:owner",
          expiresAt: "2026-09-03T00:00:00.000Z",
        },
      ];
    if (action.invalid === "document")
      doc.mappings[0].sources = ["urn:test:missing"];
    if (action.invalid === "policy") policy.mappings = [];
    const result = api.compile(doc, policy, {
      ...options,
      constraintRegistry: registry,
    });
    return {
      status: "observed",
      value: encode(result),
      host: {
        keys: Object.keys(result),
        issueKeys: result.issues.map((issue) => Object.keys(issue)),
        events,
        issueIdentity: issues.map((issue) => result.issues.includes(issue)),
        issueMutations: encode(issues),
        distinctContexts: new Set(contexts).size,
        ...(action.host
          ? {
              causalPathIdentity: result.issues
                .filter((issue) => issue.causalPath)
                .map((issue) =>
                  result.impact.paths.some(
                    (path) => path.path === issue.causalPath,
                  ),
                ),
            }
          : {}),
        ...(result.generation
          ? {
              sharedContext: result.generation.context === options.context,
              frozen: Object.isFrozen(result.generation),
              contextFrozen: Object.isFrozen(options.context),
              generationKeys: Object.keys(result.generation),
              graphKeys: Object.keys(result.generation.graph),
            }
          : {}),
      },
    };
  } catch (error) {
    return {
      status: "threw",
      error: errorObservation(error),
      host: { events, sameThrownObject: error === thrown },
    };
  }
}

let receipt;
if (process.argv.includes("--freeze")) {
  const original = await import(
      pathToFileURL(join(oracle, "dist/constraints.js"))
    ),
    viability = await import(pathToFileURL(join(oracle, "dist/viability.js"))),
    graph = await import(pathToFileURL(join(oracle, "dist/graph.js")));
  const api = {
    Registry: original.ConstraintRegistry,
    Graph: graph.MetamapGraph,
    compile: viability.compileMetamap,
  };
  const document = JSON.parse(
      readFileSync(join(oracle, "examples/example-authority-graph.json")),
    ),
    baseline = JSON.parse(
      readFileSync(join(oracle, "examples/example-viability-policy.json")),
    );
  const cases = [];
  function add(name, action) {
    cases.push({
      name,
      action,
      expected: observe(action, api, document, baseline),
    });
  }
  if (process.argv.includes("--host")) {
    for (const mode of ["cross-instance", "subclass", "borrowed"])
      add(`registry-host-${mode}`, { operation: "registry", mode });
    for (const graphMutation of ["replace-authorities", "mutate-authority"])
      add(`builtin-host-${graphMutation}`, {
        operation: "builtin",
        kind: "core:requires-authority",
        parameters: { fact: "type" },
        graphMutation,
      });
    for (const mode of [
      "warning",
      "error",
      "waived",
      "bare-warning",
      "frozen-warning",
      "frozen-error",
      "frozen-bare-warning",
      "frozen-waived",
    ])
      add(`compile-host-${mode}`, {
        operation: "compile",
        mode,
        waiver: mode.includes("waived"),
        host: true,
      });
    add("compile-host-shared-waiver", {
      operation: "compile",
      callbacks: ["shared-error", "shared-error"],
      waiver: true,
      host: true,
    });
  } else {
    add("registry-construct", { operation: "registry", mode: "construct" });
    for (const key of [
      "test:custom",
      "core:requires-evidence",
      "__proto__",
      "",
      "@nan",
      "@negative-zero",
      "@symbol",
      "@object",
    ])
      for (const mode of ["register", "duplicate"])
        add(`registry-${key}-${mode}`, { operation: "registry", key, mode });
    for (const mode of ["undefined", "null", "false"])
      add(`registry-value-${mode}`, {
        operation: "registry",
        key: "test:custom",
        mode,
      });
    for (const kind of kinds)
      for (const [index, parameters] of [
        undefined,
        {},
        { unexpected: true },
      ].entries())
        add(`builtin-${kind}-${index}`, {
          operation: "builtin",
          kind,
          parameters,
        });
    for (const mode of [
      "empty",
      "warning",
      "error",
      "waived",
      "throw-error",
      "throw-typeerror",
      "active-clear",
      "active-add",
      "mutate-context",
      "mutate-policy-id",
      "mutate-document-id",
      "mutate-mappings",
      "replace-evidence",
      "append-constraint",
    ])
      add(`compile-${mode}`, {
        operation: "compile",
        mode,
        waiver: mode === "waived",
      });
    for (const callbacks of [
      ["empty", "empty"],
      ["active-clear", "empty"],
      ["replace-evidence", "empty"],
      ["delete-next", "error"],
      ["shared-error", "shared-error"],
      ["warning", "error"],
      ["mutate-document-id", "empty"],
      ["mutate-context", "empty"],
    ])
      add(`compile-sequence-${callbacks.join("-")}`, {
        operation: "compile",
        callbacks,
        waiver: callbacks[0] === "shared-error",
      });
    for (const invalid of ["document", "policy"])
      add(`compile-invalid-${invalid}`, {
        operation: "compile",
        mode: "throw-error",
        invalid,
      });
    assert.equal(cases.length, 68);
  }
  verifyReference();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: reference.referenceEngine,
        document,
        baseline,
        cases,
        scope:
          "Original registry and built-in evaluator observations plus v1 custom compiler callback receiver/lookup/context/graph/Set/evidence/issue identities, side effects, exceptions, live input changes, array iteration and shared issue waiver mutation. Other arbitrary JavaScript, full v2 and required platform acceptance remain independently open.",
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
  const configured = await import("../../sdk/typescript/legacy-validation.mjs");
  const binary = join(root, "target/debug/patamaps"),
    executions = [],
    owner = configured.createLegacyValidationApi(binary, (call) =>
      executions.push(call),
    );
  configured.configureLegacyValidation(binary, (call) => executions.push(call));
  const apis = [
      {
        name: "factory",
        Registry: owner.LegacyConstraintRegistry,
        Graph: owner.LegacyGraph,
        compile: owner.compileLegacyMetamap,
      },
      {
        name: "configured",
        Registry: configured.LegacyConstraintRegistry,
        Graph: configured.LegacyGraph,
        compile: configured.compileLegacyMetamap,
      },
    ],
    differences = [];
  for (const api of apis)
    for (const entry of corpus.cases) {
      const observed = observe(
        entry.action,
        api,
        corpus.document,
        corpus.baseline,
      );
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
  join(
    root,
    process.argv.includes("--host")
      ? ".tools/parity/current-constraint-callback-host.json"
      : ".tools/parity/current-constraint-callbacks.json",
  ),
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
