import type {
  LegacyCorrespondenceDerivation,
  LegacyPackContentBinding,
  LegacyDerivationUncertainty,
  LegacyUncertaintyDimension,
  LegacyUncertaintyStatus,
  LegacyMappingViabilitySelector,
  LegacyMappingViabilityDeclaration,
  LegacyMetamapViabilityPolicy,
} from "./legacy-evaluation.js";
import type {
  LegacyCompilationResult,
  LegacyViableGeneration,
  LegacyViabilityValidationResult,
} from "./legacy-viability.js";
import type { LegacyGraphDocument } from "./legacy-graph.js";
import type { LegacyRelationPack } from "./legacy-validation.js";
export interface LegacyDerivationBounds {
  maxDepth: number;
  maxDerivations: number;
}
export interface LegacyUncertaintyAssessment {
  id: string;
  subject: string;
  dimension: LegacyUncertaintyDimension;
  status: LegacyUncertaintyStatus;
  evidence: string[];
  assessor: string;
  sourceRevision: string;
  measurementModel?: string;
  notApplicableReason?: string;
}
export interface LegacyUncertaintyRequirement {
  id: string;
  select: LegacyMappingViabilitySelector;
  dimension: LegacyUncertaintyDimension;
  allowedStates: LegacyUncertaintyStatus[];
  requireEvidence: boolean;
}
export interface LegacyMappingRiskClassification {
  id: string;
  select: LegacyMappingViabilitySelector;
  classification: string;
  cost: number;
}
export interface LegacyConsumerRiskBudget {
  id: string;
  consumer: string;
  classifications: LegacyMappingRiskClassification[];
  maximumTotalCost: number;
  maximumLossyMappings?: number;
  maximumInferredMappings?: number;
  requireCompleteClassification: true;
  requireCompleteDependencies: true;
}
export interface LegacyMetamapSemanticPolicy extends Omit<
  LegacyMetamapViabilityPolicy,
  "schemaVersion"
> {
  schemaVersion: "2.0.0";
  derivations: LegacyCorrespondenceDerivation[];
  derivationLimits: LegacyDerivationBounds;
  assessments: LegacyUncertaintyAssessment[];
  uncertaintyRequirements: LegacyUncertaintyRequirement[];
  riskBudgets: LegacyConsumerRiskBudget[];
}
export interface LegacyMappingDependency {
  mapping: string;
  premises: string[];
  derivation?: { id: string; digest: string };
}
export interface LegacySemanticGeneration extends Omit<
  LegacyViableGeneration,
  "schemaVersion"
> {
  schemaVersion: "2.0.0";
  semantic: {
    interpretation: "declared-law-application";
    packs: Array<{
      binding: LegacyPackContentBinding;
      value: LegacyRelationPack;
    }>;
    derivations: LegacyCorrespondenceDerivation[];
    derivationLimits: LegacyDerivationBounds;
    declarations: Array<{
      mapping: string;
      declaration: LegacyMappingViabilityDeclaration;
    }>;
    dependencies: LegacyMappingDependency[];
    assessments: LegacyUncertaintyAssessment[];
    uncertaintyRequirements: LegacyUncertaintyRequirement[];
    uncertainty: Array<{
      mapping: string;
      dimensions: LegacyDerivationUncertainty[];
    }>;
    riskBudgets: LegacyConsumerRiskBudget[];
    riskEvaluation: "not-evaluated" | "available-for-projection";
  };
}
export type LegacySemanticCompilationResult =
  | (Omit<
      Extract<LegacyCompilationResult, { status: "viable" }>,
      "generation"
    > & { generation: LegacySemanticGeneration })
  | Extract<LegacyCompilationResult, { status: "rejected" }>;
export function validateLegacySemanticPolicy(
  value: unknown,
): LegacyViabilityValidationResult;
export function parseLegacySemanticPolicy(
  value: unknown,
): LegacyMetamapSemanticPolicy;
export function validateLegacySemanticGeneration(
  value: unknown,
): LegacyViabilityValidationResult;
export function parseLegacySemanticGeneration(
  value: unknown,
): LegacySemanticGeneration;
export function legacySemanticGenerationDigest(
  value: LegacySemanticGeneration,
): string;
export function legacyPolicyView(
  policy: LegacyMetamapSemanticPolicy,
): LegacyMetamapViabilityPolicy;
export function admittedLegacyMappingDependencies(
  graph: LegacyGraphDocument,
  active: ReadonlySet<string>,
  records: readonly LegacyCorrespondenceDerivation[],
): LegacyMappingDependency[];
