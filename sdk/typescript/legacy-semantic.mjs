import { marshalJson, CanonicalJsonError } from "./canonical.mjs";

/** Object-rest reads and retained handles are host transport; Rust validates/hashes. */
export function createLegacySemanticApi(invoke) {
  const call = (operation, input) =>
    invoke("viability", "json", {
      operation: "semantic-" + operation,
      input: marshalJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    }).value;
  function described(value) {
    try {
      return { value: JSON.parse(marshalJson(value)) };
    } catch (error) {
      if (!(error instanceof CanonicalJsonError)) throw error;
      return { canonicalError: error.message };
    }
  }
  const validate = (kind, value) => call("validate-" + kind, described(value));
  const parse = (kind, value) => {
    call("parse-" + kind, described(value));
    return value;
  };
  return {
    validateLegacySemanticPolicy: (value) => validate("policy", value),
    parseLegacySemanticPolicy: (value) => parse("policy", value),
    validateLegacySemanticGeneration: (value) => validate("generation", value),
    parseLegacySemanticGeneration: (value) => parse("generation", value),
    legacySemanticGenerationDigest(value) {
      const { id: _id, digest: _digest, ...content } = value;
      return call("digest", { value: JSON.parse(marshalJson(content)) });
    },
    legacyPolicyView(policy) {
      // Execute original host reads while retaining values rather than
      // serializing caller object/function identities.
      const {
        derivations: _proofs,
        derivationLimits: _limits,
        assessments: _assessments,
        uncertaintyRequirements: _requirements,
        riskBudgets: _budgets,
        ...common
      } = policy;
      const entries = Reflect.ownKeys(common).map((key) => [key, common[key]]);
      const plan = call("view", {
        fields: entries.map(([key]) => (typeof key === "symbol" ? null : key)),
      });
      const result = Object.fromEntries(
        plan.keep.map((index) => entries[index]),
      );
      result.schemaVersion = plan.schemaVersion;
      return result;
    },
    admittedLegacyMappingDependencies(graph, active, records) {
      return call("dependencies", { graph, active: [...active], records });
    },
  };
}
