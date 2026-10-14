import {
  marshalJson,
  marshalLegacyNumericObservationJson,
  CanonicalJsonError,
} from "./canonical.mjs";

export const legacyEmptyUncertaintyInputs = Object.freeze({
  assessments: Object.freeze([]),
  evidence: Object.freeze([]),
});

/** JavaScript carries values and references; all uncertainty/accounting decisions are native. */
export function createLegacyUncertaintyRiskApi(invoke) {
  const wire = (operation, input) => {
    const response = invoke("viability", "json", {
      operation,
      input: marshalLegacyNumericObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
    for (const fact of response.numberFacts ?? []) {
      const parent = fact.path
        .slice(0, -1)
        .reduce((value, key) => value[key], response);
      parent[fact.path.at(-1)] = {
        nan: NaN,
        "negative-zero": -0,
        "positive-infinity": Infinity,
        "negative-infinity": -Infinity,
      }[fact.kind];
    }
    return response;
  };
  const call = (operation, input) => wire(operation, input).value;
  function strict(value) {
    return JSON.parse(marshalJson(value));
  }
  function validate(graph, inputs, prospective, proofIds = []) {
    let snapshot;
    try {
      snapshot = strict(inputs);
    } catch (error) {
      if (!(error instanceof CanonicalJsonError)) throw error;
      return call("uncertainty-shape", { canonicalError: error.message });
    }
    const shape = call("uncertainty-shape", { inputs: snapshot });
    if (shape.length) return shape;
    return call("uncertainty-validate", {
      graph,
      inputs: snapshot,
      prospective,
      proofIds,
    });
  }
  function dependencies(summary, inputs) {
    const records = [...inputs.assessments, ...inputs.evidence];
    const plan = call("uncertainty-dependency-plan", {
      summary,
      recordIds: records.map((record) => record.id),
    });
    const selected = plan.map(({ id, ordinal }) => ({
      id,
      value: strict(ordinal === null ? undefined : records[ordinal]),
    }));
    return call("uncertainty-bindings", { records: selected });
  }
  function graphSummaries(graph, proofs, inputs) {
    const response = wire("uncertainty-graph", { graph, proofs, inputs });
    return response.value.map((entry, i) =>
      response.proofOrdinals[i] === null
        ? entry
        : {
            ...entry,
            dimensions: proofs[response.proofOrdinals[i]].uncertainty,
          },
    );
  }
  function evaluateRisk(graph, generation, spec, used) {
    // Fields not read by the original accounting operation remain caller handles;
    // only the chosen successful budget undergoes the original strict digest gate.
    const budgets = generation.semantic.riskBudgets;
    const budgetSnapshots = budgets.map((b) => ({
      id: b.id,
      consumer: b.consumer,
      classifications: b.classifications,
      maximumTotalCost: b.maximumTotalCost,
      maximumLossyMappings: b.maximumLossyMappings,
      maximumInferredMappings: b.maximumInferredMappings,
    }));
    const response = wire("risk-evaluate", {
      graph,
      generation: {
        semantic: {
          riskBudgets: budgetSnapshots,
          uncertainty: generation.semantic.uncertainty,
        },
      },
      spec: { consumer: spec.consumer, budget: spec.budget },
      used,
    });
    const result = response.value;
    result.risk.uncertainty = response.summaryOrdinals.map(
      (i) => generation.semantic.uncertainty[i],
    );
    if (response.budgetOrdinal !== null) {
      const budget = budgets[response.budgetOrdinal];
      result.risk.budget = call("uncertainty-bindings", {
        records: [{ id: budget.id, value: strict(budget) }],
      })[0];
    }
    return result;
  }
  return {
    legacyEmptyUncertaintyInputs,
    validateLegacyUncertaintyInputs: validate,
    legacyUnknownDimension: (dimension) =>
      call("uncertainty-unknown", { dimension }),
    combineLegacyUncertainty: (dimension, values) =>
      call("uncertainty-combine", { dimension, values }),
    legacyMappingUncertainty: (graph, mapping, inputs, premises = []) =>
      call("uncertainty-mapping", { graph, mapping, inputs, premises }),
    legacyUncertaintyDependencies: dependencies,
    legacyGraphUncertainty: graphSummaries,
    legacyUncertaintySummaryIssues: (summaries) =>
      call("uncertainty-summary", { summaries }),
    legacyUncertaintyRequirementIssues: (
      graph,
      active,
      summaries,
      requirements,
      inputs,
    ) =>
      call("uncertainty-requirements", {
        graph,
        active: [...active],
        summaries,
        requirements,
        inputs,
      }),
    legacyConsumerBudgetIssues: (graph, budgets) =>
      call("risk-budgets", { graph, budgets }),
    evaluateLegacyConsumerRisk: evaluateRisk,
  };
}
