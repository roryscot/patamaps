/** Independent original memory activation and refusal observations. */
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
  "fixtures/parity/memory-activation-controls.json",
);
const output = join(
  root,
  "docs/acceptance/parity",
  "memory-activation-" + new Date().toISOString().replaceAll(":", "-"),
);
mkdirSync(output, { recursive: true });
// Observe host numbers/holes without using the candidate's marshaller.
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
      return Array.from({ length: value.length }, (_, i) => {
        if (!Object.hasOwn(value, i)) {
          numbers.push({ path: [...path, String(i)], kind: "hole" });
          return 0;
        }
        return visit(value[i], [...path, String(i)]);
      });
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, visit(v, [...path, k])]),
      );
    return value;
  }
  return value === undefined ? { numbers } : { value: visit(value), numbers };
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
function observe(action, api, document, baseline) {
  const events = [],
    results = [],
    retained = [],
    contexts = [];
  let actor,
    callbackError,
    mode,
    inside = false;
  try {
    let relations =
      action.registry === "null"
        ? null
        : action.registry === "empty"
          ? new api.Relations([])
          : action.registry === "provided"
            ? new api.Relations()
            : undefined;
    let constraints =
      action.constraints === "null"
        ? null
        : action.constraints === "provided" || action.callbacks
          ? new api.Constraints()
          : undefined;
    let host = action.host;
    if (host === "governed")
      host = {
        mode: "governed",
        configuration: () => {
          throw new Error("unselected governed host");
        },
      };
    if (host === "memory") host = { mode: "memory" };
    if (host === "empty") host = {};
    if (action.callbacks)
      constraints.register(
        "test:memory-activation",
        function (constraint, context) {
          events.push({
            callback: mode,
            receiverUndefined: this === undefined,
            constraintId: constraint.id,
            sameDocument: context.document === context.graph.document,
            active: [...context.activeMappings],
            current: actor.current?.id ?? null,
          });
          if (mode === "callback-throw") {
            callbackError = new TypeError("memory callback failure");
            throw callbackError;
          }
          if (
            (mode === "reentrant-reject" || mode === "reentrant-good") &&
            !inside
          ) {
            inside = true;
            const innerDoc = structuredClone(document),
              innerPolicy = structuredClone(baseline);
            innerPolicy.constraints = [];
            const innerContext = {
              environment: "production",
              maintenance: true,
            };
            const inner = actor.activate(innerDoc, innerPolicy, {
              context: innerContext,
              evaluatedAt: "2026-09-02T01:00:00.000Z",
            });
            events.push({
              nestedActivated: inner.activated,
              nestedCurrentSame: inner.current === actor.current,
              innerContextFrozen: Object.isFrozen(innerContext),
            });
            retained.push(inner.current);
            inside = false;
          }
          if (mode === "callback-error" || mode === "reentrant-reject")
            return [
              {
                severity: "error",
                code: "CUSTOM_ACTIVATION",
                message: "custom rejection",
                subjectId: context.document.mappings[0].id,
              },
            ];
          if (mode === "callback-warning")
            return [
              {
                severity: "warning",
                code: "CUSTOM_ACTIVATION",
                message: "custom warning",
                subjectId: context.document.mappings[0].id,
              },
            ];
          return [];
        },
      );
    actor = new api.Actor(relations, constraints, host);
    const initial = {
      ownKeys: Object.keys(actor),
      name: actor.constructor.name,
      constructorLength: api.Actor.length,
      activateLength: actor.activate.length,
      currentUndefined: actor.current === undefined,
      governedUndefined: actor.governedCurrent === undefined,
      providedRelationIdentity:
        relations === undefined ? null : actor.relationRegistry === relations,
      providedConstraintIdentity:
        constraints === undefined
          ? null
          : actor.constraintRegistry === constraints,
      descriptors: Object.fromEntries(
        Object.entries(Object.getOwnPropertyDescriptors(actor)).map(
          ([key, d]) => [
            key,
            {
              enumerable: d.enumerable,
              configurable: d.configurable,
              writable: d.writable,
            },
          ],
        ),
      ),
    };
    if (action.freezeActor) Object.freeze(actor);
    for (const step of action.steps ?? []) {
      mode = step;
      const doc = structuredClone(document),
        policy = structuredClone(baseline),
        context = { environment: "production", maintenance: false },
        options = { context, evaluatedAt: "2026-09-02T00:00:00.000Z" };
      contexts.push(context);
      const before = actor.current;
      if (action.callbacks)
        policy.constraints = [
          {
            id: "urn:test:memory:constraint",
            kind: "test:memory-activation",
            subjects: [doc.mappings[0].id],
          },
        ];
      if (step === "bad-bindings") policy.mappings = [];
      if (step === "bad-graph") doc.mappings[0].sources = ["urn:test:missing"];
      if (step === "bad-context") delete context.environment;
      if (step === "bad-time") options.evaluatedAt = "not-a-date";
      if (step === "maintenance") context.maintenance = true;
      if (step === "numeric-context") context.numbers = [NaN, -0, Infinity];
      if (step === "version2") policy.schemaVersion = "2.0.0";
      if (step === "version0") policy.schemaVersion = "0.0.0";
      if (step === "version-missing") delete policy.schemaVersion;
      if (step === "unknown-constraint")
        policy.constraints.push({
          id: "urn:test:unknown",
          kind: "test:missing",
          subjects: [doc.id],
        });
      if (step === "changed-subjects")
        options.changedSubjects = [doc.entities[0].id];
      if (step === "mutate-current")
        actor.generation = { marker: "retained caller field" };
      let result;
      try {
        result =
          step === "request-only"
            ? actor.activate({ schemaVersion: "1.0.0", mode: "governed" })
            : step === "null-policy"
              ? actor.activate(doc, null, options)
              : actor.activate(doc, policy, options);
        results.push({
          status: "observed",
          value: encode(result),
          host: {
            keys: Object.keys(result),
            currentPresent: Object.hasOwn(result, "current"),
            currentSame: result.current === actor.current,
            currentUnchanged: actor.current === before,
            currentCompilationIdentity: result.compilation?.generation
              ? result.current === result.compilation.generation
              : null,
            compilationKeys: result.compilation
              ? Object.keys(result.compilation)
              : null,
            issueKeys:
              result.compilation?.issues?.map((issue) => Object.keys(issue)) ??
              result.issues?.map((issue) => Object.keys(issue)),
            quarantineAlias: result.compilation?.quarantinedSubjects
              ? result.compilation.quarantinedSubjects ===
                result.compilation.impact.affectedSubjects
              : null,
            causalAliases:
              result.compilation?.issues
                .filter((issue) => issue.causalPath)
                .map((issue) =>
                  result.compilation.impact.paths.some(
                    (path) => path.path === issue.causalPath,
                  ),
                ) ?? null,
            contextIdentity: result.compilation?.generation
              ? result.compilation.generation.context === context
              : null,
            contextFrozen: Object.isFrozen(context),
            currentFrozen:
              actor.current === undefined
                ? null
                : Object.isFrozen(actor.current),
            currentValue: encode(actor.current),
            governedUndefined: actor.governedCurrent === undefined,
          },
        });
        retained.push(result.current);
      } catch (error) {
        results.push({
          status: "threw",
          error: errorObservation(error),
          host: {
            currentUnchanged: actor.current === before,
            sameCallbackError: error === callbackError,
            contextFrozen: Object.isFrozen(context),
            governedUndefined: actor.governedCurrent === undefined,
            currentValue: encode(actor.current),
          },
        });
      }
    }
    return {
      status: "observed",
      initial,
      results,
      events,
      final: {
        current: encode(actor.current),
        currentRetained: retained.indexOf(actor.current),
        governedUndefined: actor.governedCurrent === undefined,
        contextFrozen: contexts.map(Object.isFrozen),
        ownKeys: Object.keys(actor),
      },
    };
  } catch (error) {
    return { status: "threw", error: errorObservation(error), events };
  }
}
let receipt;
if (process.argv.includes("--freeze")) {
  const viability = await import(
      pathToFileURL(join(oracle, "dist/viability.js"))
    ),
    relations = await import(pathToFileURL(join(oracle, "dist/relations.js"))),
    constraints = await import(
      pathToFileURL(join(oracle, "dist/constraints.js"))
    );
  const api = {
      Actor: viability.MetamapActivator,
      Relations: relations.RelationRegistry,
      Constraints: constraints.ConstraintRegistry,
    },
    document = JSON.parse(
      readFileSync(join(oracle, "examples/example-authority-graph.json")),
    ),
    baseline = JSON.parse(
      readFileSync(join(oracle, "examples/example-viability-policy.json")),
    ),
    cases = [];
  const add = (name, action) =>
    cases.push({
      name,
      action,
      expected: observe(action, api, document, baseline),
    });
  add("constructor-default", {});
  for (const registry of ["provided", "empty", "null"])
    add(`constructor-registry-${registry}`, { registry });
  for (const constraints of ["provided", "null"])
    add(`constructor-constraints-${constraints}`, { constraints });
  for (const step of [
    "good",
    "bad-bindings",
    "bad-graph",
    "bad-context",
    "bad-time",
    "maintenance",
    "numeric-context",
    "version2",
    "version0",
    "version-missing",
    "unknown-constraint",
    "changed-subjects",
    "request-only",
    "null-policy",
    "mutate-current",
  ])
    add(`activation-${step}`, { steps: [step] });
  for (const steps of [
    ["good", "bad-bindings"],
    ["bad-bindings", "good"],
    ["good", "good"],
    ["good", "maintenance"],
    ["good", "version2"],
    ["good", "request-only"],
    ["good", "null-policy"],
    ["good", "bad-graph", "bad-context", "good"],
    ["good", "unknown-constraint", "good"],
    ["mutate-current", "bad-bindings"],
  ])
    add(`sequence-${steps.join("-")}`, { steps });
  for (const host of [null, false, 0, "empty", "memory", "governed"])
    for (const step of [
      "good",
      "version2",
      ...(host === "governed" ? [] : ["request-only"]),
    ])
      add(`host-${host}-${step}`, { host, steps: [step] });
  for (const registry of ["empty", "null", "provided"])
    add(`registry-${registry}-sequence`, {
      registry,
      steps: ["good", "bad-bindings", "version2"],
    });
  for (const constraints of ["provided", "null"])
    add(`constraints-${constraints}-sequence`, {
      constraints,
      steps: ["good", "bad-bindings"],
    });
  for (const step of [
    "callback-good",
    "callback-error",
    "callback-warning",
    "callback-throw",
    "reentrant-good",
    "reentrant-reject",
  ])
    add(`callback-${step}`, { callbacks: true, steps: [step] });
  add("callback-retention-sequence", {
    callbacks: true,
    steps: [
      "callback-good",
      "callback-error",
      "callback-throw",
      "callback-good",
    ],
  });
  add("frozen-actor", {
    freezeActor: true,
    steps: ["good", "bad-bindings", "version2"],
  });
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
          "Original memory activator, current identity/state and selected callback/reentrant/error/freeze contracts plus no-host/protected v2/governed-mode refusals. Signed governed evaluator/state, complete arbitrary JavaScript and required platform acceptance remain open.",
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
  const sdkDirectory = process.argv.includes("--baseline")
    ? join(
        root,
        JSON.parse(
          readFileSync(
            join(root, ".tools/parity/current-memory-activation-scope.json"),
          ),
        ).output,
        "pre-repair-sdk",
      )
    : join(root, "sdk/typescript");
  const configured = await import(
      pathToFileURL(join(sdkDirectory, "legacy-validation.mjs"))
    ),
    binary = join(root, "target/debug/patamaps"),
    executions = [];
  const owner = configured.createLegacyValidationApi(binary, (call) =>
    executions.push(call),
  );
  configured.configureLegacyValidation(binary, (call) => executions.push(call));
  const apis = [
      {
        name: "factory",
        Actor: owner.LegacyMetamapActivator,
        Relations: owner.LegacyRelationRegistry,
        Constraints: owner.LegacyConstraintRegistry,
      },
      {
        name: "configured",
        Actor: configured.LegacyMetamapActivator,
        Relations: configured.LegacyRelationRegistry,
        Constraints: configured.LegacyConstraintRegistry,
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
      sdkSourceInventory: readdirSync(sdkDirectory)
        .filter(
          (name) => /\.(mjs|d\.ts)$/.test(name) || name === "package.json",
        )
        .sort()
        .map((name) => ({
          path: relative(root, join(sdkDirectory, name)),
          digest: sha(readFileSync(join(sdkDirectory, name))),
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
  join(root, ".tools/parity/current-memory-activation.json"),
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
