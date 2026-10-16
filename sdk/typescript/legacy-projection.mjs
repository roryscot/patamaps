import { marshalLegacyNumericObservationJson } from "./canonical.mjs";
import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";

export const LEGACY_METAMAP_PROJECTION_SPEC_VERSION = "1.0.0";
export const LEGACY_METAMAP_PROJECTION_VERSION = "1.0.0";
function freeze(value) {
  if (typeof value !== "object" || value === null || Object.isFrozen(value))
    return value;
  for (const child of Object.values(value)) freeze(child);
  return Object.freeze(value);
}
/** Transport and host object identity only; Rust validates and compiles. */
export function createLegacyProjectionApi(invoke, Registry) {
  function call(operation, input) {
    const response = invoke("viability", "json", {
      operation,
      input: marshalLegacyNumericObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
    const value = response.value;
    for (const fact of response.numbers ?? []) {
      let parent = value;
      for (const key of fact.path.slice(0, -1)) {
        if (!Object.hasOwn(parent, key))
          throw new Error("Invalid native numeric path");
        parent = parent[key];
      }
      const key = fact.path.at(-1);
      if (!Object.hasOwn(parent, key))
        throw new Error("Invalid native numeric path");
      const numbers = {
        "negative-zero": -0,
        nan: NaN,
        "positive-infinity": Infinity,
        "negative-infinity": -Infinity,
      };
      if (!Object.hasOwn(numbers, fact.kind))
        throw new Error("Invalid native numeric kind");
      Object.defineProperty(parent, key, {
        value: numbers[fact.kind],
        writable: true,
        enumerable: true,
        configurable: true,
      });
    }
    if (value.issues)
      value.issues = value.issues.map((entry, i) =>
        Object.fromEntries(
          response.issueKeys[i].map((key) => [key, entry[key]]),
        ),
      );
    return value;
  }
  return {
    validateLegacyProjectionSpec: (value) =>
      call("projection-spec-validate", { value }),
    parseLegacyProjectionSpec(value) {
      call("projection-spec-parse", { value });
      return value;
    },
    validateLegacyProjection: (value) => call("projection-validate", { value }),
    parseLegacyProjection(value) {
      call("projection-parse", { value });
      return value;
    },
    compileLegacyProjection(document, generation, spec, options = {}) {
      const registry = options.relationRegistry ?? new Registry();
      const result = call("projection-compile", {
        document,
        generation,
        spec,
        registry: legacyRegistryGraphSnapshot(registry),
        executablePackCount: registry.executablePacks().length,
        semanticPolicyPresent: Boolean(options.semanticPolicy),
      });
      if (result.projection) freeze(result.projection);
      return result;
    },
  };
}
