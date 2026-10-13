import { marshalLegacyNumericObservationJson } from "./canonical.mjs";
import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";

export const LEGACY_METAMAP_VIABILITY_POLICY_VERSION = "1.0.0";
export const LEGACY_METAMAP_GENERATION_VERSION = "1.0.0";

function deepFreeze(value) {
  if (typeof value !== "object" || value === null || Object.isFrozen(value))
    return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}
/** Host handles, undefined properties and freezing only; Rust compiles. */
export function createLegacyViabilityApi(invoke, Registry) {
  function call(operation, input) {
    const response = invoke("viability", "json", {
      operation,
      input: marshalLegacyNumericObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
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
  const api = {
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
      if (options.constraintRegistry !== undefined)
        throw new Error(
          "Original custom constraint registry transport is not implemented",
        );
      const context = options.context ?? {};
      const registry = options.relationRegistry ?? new Registry();
      const { relationRegistry, constraintRegistry, ...portable } = options;
      const result = call("compile", {
        document,
        policy,
        options: {
          ...portable,
          context,
          evaluatedAt: options.evaluatedAt ?? new Date().toISOString(),
        },
        registry: legacyRegistryGraphSnapshot(registry, ["impactDirection"]),
        executablePackCount: registry.executablePacks().length,
      });
      if (result.generation) {
        result.generation.context = context;
        deepFreeze(result.generation);
      }
      return result;
    },
  };
  return api;
}
