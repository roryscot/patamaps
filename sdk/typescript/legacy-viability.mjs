import { marshalLegacyNumericObservationJson } from "./canonical.mjs";
import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";
import { legacyConstraintGraphSnapshot } from "./legacy-graph.mjs";

export const LEGACY_METAMAP_VIABILITY_POLICY_VERSION = "1.0.0";
export const LEGACY_METAMAP_GENERATION_VERSION = "1.0.0";
const constraintInitializers = new WeakMap();
/** @internal Seed configured and factory registries through their own register. */
export const initializeLegacyConstraintRegistry = (registry, Registry) =>
  constraintInitializers.get(Registry)(registry);

function deepFreeze(value) {
  if (typeof value !== "object" || value === null || Object.isFrozen(value))
    return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}
/** Host handles, undefined properties and freezing only; Rust compiles. */
export function createLegacyViabilityApi(invoke, Registry, Graph) {
  function wire(operation, input) {
    const response = invoke("viability", "json", {
      operation,
      input: marshalLegacyNumericObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
    return response;
  }
  function restore(response) {
    const value = response.value;
    if (value.issues)
      value.issues = value.issues.map((issue, index) =>
        Object.fromEntries(
          response.issueKeys[index].map((key) => [key, issue[key]]),
        ),
      );
    if (value.generation)
      value.generation.graph = Object.fromEntries(
        response.graphKeys.map((key) => [key, value.generation.graph[key]]),
      );
    return value;
  }
  const call = (operation, input) => restore(wire(operation, input));
  const keySnapshot = (evaluators, key) => {
    const keys = new Map([...evaluators.keys()].map((kind, i) => [kind, i]));
    if (!keys.has(key)) keys.set(key, keys.size);
    return {
      keys: [...evaluators.keys()].map((kind) => keys.get(kind)),
      key: keys.get(key),
    };
  };
  let builtins;
  class LegacyConstraintRegistry {
    constructor() {
      initializeLegacyConstraintRegistry(this, LegacyConstraintRegistry);
    }
    register(kind, evaluator) {
      const duplicate = wire(
        "constraint-register",
        keySnapshot(this.evaluators, kind),
      ).value;
      if (duplicate)
        throw new Error(`Constraint evaluator ${kind} is already registered`);
      this.evaluators.set(kind, evaluator);
    }
    get(kind) {
      const ordinal = wire(
        "constraint-get",
        keySnapshot(this.evaluators, kind),
      ).value;
      return ordinal === null
        ? undefined
        : [...this.evaluators.values()][ordinal];
    }
  }
  constraintInitializers.set(LegacyConstraintRegistry, (registry) => {
    registry.evaluators = new Map();
    builtins ??= wire("constraint-kinds", {}).value.map(({ kind, name }) => {
      const evaluator = (constraint, context) => {
        const graph =
          kind === "core:requires-authority"
            ? legacyConstraintGraphSnapshot(context.graph)
            : undefined;
        const result = wire("constraint-evaluate", {
          kind,
          constraint,
          context: {
            document: context.document,
            activeMappings: [...context.activeMappings],
            evidence: context.evidence,
            ...(graph
              ? {
                  graph,
                  registry: legacyRegistryGraphSnapshot(context.graph.registry),
                }
              : {}),
          },
        });
        return result.value.map((issue, index) =>
          Object.fromEntries(
            result.issueKeys[index].map((key) => [key, issue[key]]),
          ),
        );
      };
      Object.defineProperty(evaluator, "name", { value: name });
      return { kind, evaluator };
    });
    for (const { kind, evaluator } of builtins)
      registry.register(kind, evaluator);
  });
  function request(document, policy, options, registry, context) {
    const { relationRegistry, constraintRegistry, ...portable } = options;
    return {
      document,
      policy,
      options: {
        ...portable,
        context,
        evaluatedAt: options.evaluatedAt ?? new Date().toISOString(),
      },
      registry: legacyRegistryGraphSnapshot(registry, ["impactDirection"]),
      executablePackCount: registry.executablePacks().length,
    };
  }
  function finish(result, context) {
    if (result.generation) {
      result.generation.context = context;
      deepFreeze(result.generation);
    }
    return result;
  }
  const api = {
    LegacyConstraintRegistry,
    validateLegacyViabilityPolicy(value) {
      return call("validate-policy", { value });
    },
    validateLegacyViableGeneration(value) {
      return call("validate-generation", { value });
    },
    parseLegacyViabilityPolicy(value) {
      call("parse-policy", { value });
      return value;
    },
    parseLegacyViableGeneration(value) {
      call("parse-generation", { value });
      return value;
    },
    compileLegacyMetamap(document, policy, options = {}) {
      const context = options.context ?? {};
      const registry = options.relationRegistry ?? new Registry();
      if (options.constraintRegistry == null)
        return finish(
          call(
            "compile",
            request(document, policy, options, registry, context),
          ),
          context,
        );
      const prepared = call("compile-start", {
        ...request(document, policy, options, registry, context),
        callbackPhase: true,
      });
      if (prepared.status !== "constraints") return finish(prepared, context);
      const frame = prepared.frame;
      const graph = new Graph(document, { registry });
      const activeMappings = new Set(frame.activeMappings);
      const constraints = policy.constraints,
        length = constraints.length,
        callbackIssues = [],
        retained = [],
        issueHandles = new Map();
      for (let index = 0; index < length; index++) {
        if (!(index in constraints)) continue;
        const constraint = constraints[index];
        const selected = call("constraint-select", { constraint });
        let output;
        if (selected.status === "missing") output = selected.issues;
        else {
          const evaluator = options.constraintRegistry.get(selected.kind);
          if (!evaluator)
            output = call("constraint-missing", { constraint }).issues;
          else
            output = evaluator(constraint, {
              document,
              graph,
              activeMappings,
              evidence: policy.evidence,
            });
        }
        // Array.flatMap retains returned issue handles and flattens one level.
        for (const issue of Array.isArray(output) ? output.flat(0) : [output]) {
          if (!issueHandles.has(issue)) {
            issueHandles.set(issue, retained.length);
            retained.push(issue);
          }
          callbackIssues.push(issue);
        }
      }
      const response = wire("compile-finish", {
        ...request(
          document,
          policy,
          { ...options, evaluatedAt: frame.evaluatedAt },
          registry,
          context,
        ),
        frame,
        activeMappings: [...activeMappings],
        callbackIssues: callbackIssues.map((issue) => ({
          value: issue,
          keys: Object.keys(issue),
          handle: issueHandles.get(issue),
        })),
      });
      const result = restore(response);
      for (const write of response.issueWrites ?? []) {
        retained[write.handle][write.key] =
          write.pathIndex === undefined
            ? write.value
            : result.impact.paths[write.pathIndex].path;
      }
      result.issues = result.issues.map((value, index) => {
        const handle = response.issueHandles?.[index];
        if (handle === null || handle === undefined) return value;
        return retained[handle];
      });
      return finish(result, context);
    },
  };
  return api;
}
