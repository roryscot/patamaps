import {
  marshalLegacyNumericObservationJson,
  marshalLegacyObservationJson,
} from "./canonical.mjs";
import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";
const kind = (value) =>
  value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
/** JavaScript retains caller identity; Rust decides validity and expressions. */
export function createLegacyEvaluationApi(invoke, Registry) {
  const call = (operation, input, observation = false) =>
    invoke("evaluation", "json", {
      operation,
      input: observation
        ? marshalLegacyObservationJson(input)
        : marshalLegacyNumericObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
  return {
    parseLegacyEvaluationContext(value) {
      // Object.entries executes the same enumerable getters as the original.
      const entries = kind(value) === "object" ? Object.entries(value) : [];
      const response = call(
        "parse-context",
        {
          rootKind: kind(value),
          entries: entries.map(([key, value]) => {
            const entry = { key, kind: kind(value) };
            if (Array.isArray(value)) {
              entry.elementKinds = [];
              Array.prototype.forEach.call(value, (v) =>
                entry.elementKinds.push(kind(v)),
              );
            }
            return entry;
          }),
        },
        true,
      );
      const result = {};
      for (const index of response.indices) {
        const [key, value] = entries[index];
        result[key] = value;
      }
      return result;
    },
    evaluateLegacyContextExpression(expression, context) {
      return call("evaluate", { expression, context });
    },
    requiredLegacyContextKeys(expression) {
      return new Set(call("required", { expression }));
    },
    legacyInactiveReason(applicability, context) {
      return call("inactive", { applicability, context }) ?? undefined;
    },
    legacySelectorMatches(mapping, selector, entityKinds) {
      return call("selector", {
        mapping,
        selector,
        entityKinds: [...entityKinds],
      });
    },
    analyzeLegacyImpact(document, options) {
      const { registry, activeMappings, ...rest } = options;
      return call("impact", {
        document,
        options: {
          ...rest,
          ...(activeMappings === undefined
            ? {}
            : { activeMappings: [...activeMappings] }),
        },
        registry: legacyRegistryGraphSnapshot(registry ?? new Registry(), [
          "impactDirection",
        ]),
      });
    },
  };
}
