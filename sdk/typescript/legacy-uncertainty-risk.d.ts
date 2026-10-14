import type { JsonValue } from "./index.js";
import type {
  LegacyGraphDocument,
  LegacyStructuralMapping,
} from "./legacy-graph.js";
import type {
  LegacyContentBinding,
  LegacyCorrespondenceDerivation,
  LegacyDerivationUncertainty,
  LegacyUncertaintyDimension,
  LegacyEvidenceRecord,
} from "./legacy-evaluation.js";
import type {
  LegacyUncertaintyAssessment,
  LegacyUncertaintyRequirement,
  LegacyConsumerRiskBudget,
  LegacySemanticGeneration,
} from "./legacy-semantic.js";

export interface LegacyDerivationIssue {
  code: string;
  message: string;
  subjectId?: string;
  path?: string;
}
export interface LegacyUncertaintyInputs {
  assessments: readonly LegacyUncertaintyAssessment[];
  evidence: readonly LegacyEvidenceRecord[];
}
export const legacyEmptyUncertaintyInputs: LegacyUncertaintyInputs;
export type LegacyProjectionDirection = "outgoing" | "incoming";
export type LegacyProjectionCardinality =
  "exactly-one" | "zero-or-one" | "one-or-more" | "many";
export interface LegacyProjectionSelection {
  ids?: string[];
  kinds?: string[];
}
export interface LegacyProjectionSlotSpec {
  name: string;
  relation: string;
  direction: LegacyProjectionDirection;
  cardinality: LegacyProjectionCardinality;
  targetKinds?: string[];
  allowLossy?: boolean;
}
export type LegacyPathTreeDelimiter = "/" | "--" | ".";
export interface LegacyPathTreeSpec {
  attribute?: string;
  delimiter?: LegacyPathTreeDelimiter;
}
export interface LegacyMetamapProjectionSpec {
  $schema?: string;
  schemaVersion: "1.0.0";
  id: string;
  select: LegacyProjectionSelection;
  slots: LegacyProjectionSlotSpec[];
  pathTree?: LegacyPathTreeSpec;
  metadata?: Record<string, JsonValue>;
}
export interface LegacySemanticProjectionSpec extends Omit<
  LegacyMetamapProjectionSpec,
  "schemaVersion"
> {
  schemaVersion: "2.0.0";
  consumer: string;
  budget: string | null;
}
export type LegacyMappingUncertaintySummary = {
  mapping: string;
  dimensions: LegacyDerivationUncertainty[];
};
export interface LegacyProjectionRiskSummary {
  status: "not-evaluated" | "evaluated";
  budget: LegacyContentBinding | null;
  classifications: { mapping: string; classification: string; cost: number }[];
  totalCost: number | null;
  lossyMappings: string[];
  inferredMappings: string[];
  uncertainty: LegacyMappingUncertaintySummary[];
}
export function validateLegacyUncertaintyInputs(
  graph: LegacyGraphDocument,
  inputs: LegacyUncertaintyInputs,
  prospectiveSubject?: string,
  proofIds?: readonly string[],
): LegacyDerivationIssue[];
export function legacyUnknownDimension(
  dimension: LegacyUncertaintyDimension,
): LegacyDerivationUncertainty;
export function combineLegacyUncertainty(
  dimension: LegacyUncertaintyDimension,
  values: readonly LegacyDerivationUncertainty[],
): LegacyDerivationUncertainty;
export function legacyMappingUncertainty(
  graph: LegacyGraphDocument,
  mapping: LegacyStructuralMapping,
  inputs: LegacyUncertaintyInputs,
  premises?: readonly (readonly LegacyDerivationUncertainty[])[],
): LegacyDerivationUncertainty[];
export function legacyUncertaintyDependencies(
  summary: readonly LegacyDerivationUncertainty[],
  inputs: LegacyUncertaintyInputs,
): LegacyContentBinding[];
export function legacyGraphUncertainty(
  graph: LegacyGraphDocument,
  proofs: readonly LegacyCorrespondenceDerivation[],
  inputs: LegacyUncertaintyInputs,
): LegacyMappingUncertaintySummary[];
export function legacyUncertaintySummaryIssues(
  summaries: LegacyMappingUncertaintySummary[],
): LegacyDerivationIssue[];
export function legacyUncertaintyRequirementIssues(
  graph: LegacyGraphDocument,
  active: ReadonlySet<string>,
  summaries: LegacyMappingUncertaintySummary[],
  requirements: readonly LegacyUncertaintyRequirement[],
  inputs: LegacyUncertaintyInputs,
): LegacyDerivationIssue[];
export function legacyConsumerBudgetIssues(
  graph: LegacyGraphDocument,
  budgets: readonly LegacyConsumerRiskBudget[],
): LegacyDerivationIssue[];
export function evaluateLegacyConsumerRisk(
  graph: LegacyGraphDocument,
  generation: LegacySemanticGeneration,
  spec: LegacySemanticProjectionSpec,
  usedMappings: readonly string[],
): { risk: LegacyProjectionRiskSummary; issues: LegacyDerivationIssue[] };
