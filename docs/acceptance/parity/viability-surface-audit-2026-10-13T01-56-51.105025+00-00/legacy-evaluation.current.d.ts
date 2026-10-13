import type {
  LegacyContextExpression,
  LegacyRelationRegistry,
} from "./legacy-validation.js";
import type { JsonValue } from "./index.js";
import type {
  LegacyStructuralMapping,
  LegacyGraphDocument,
  LegacyLocator,
} from "./legacy-graph.js";
export type LegacyContextValue =
  null | boolean | number | string | (null | boolean | number | string)[];
export type LegacyEvaluationContext = Record<string, LegacyContextValue>;
export interface LegacyMappingApplicability {
  when?: LegacyContextExpression;
  unless?: LegacyContextExpression;
}
export type LegacyInactiveMappingReason = "when-not-satisfied" | "inhibited";
export type LegacyMappingCoverage = "total" | "partial";
export type LegacyMappingDeterminism = "deterministic" | "nondeterministic";
export type LegacyMappingReversibility = "reversible" | "irreversible";
export type LegacyEvidenceResult = "supports" | "contradicts" | "inconclusive";
export interface LegacyMappingViabilitySelector {
  ids?: string[];
  relations?: string[];
  sourceKinds?: string[];
  targetKinds?: string[];
  provenanceStatuses?: ("declared" | "observed" | "generated" | "inferred")[];
}
export type LegacySelectorMapping = LegacyStructuralMapping;
export type LegacyImpactDocument = LegacyGraphDocument;
export interface LegacyEvidenceRecord {
  id: string;
  subjects: string[];
  kind: string;
  result: LegacyEvidenceResult;
  producer: string;
  observedAt?: string;
  confidence?: number;
  locator?: LegacyLocator;
  digest?: string;
  attributes?: Record<string, JsonValue>;
}
export interface LegacyViabilityConstraint {
  id: string;
  kind: string;
  subjects: string[];
  parameters?: Record<string, JsonValue>;
}
export interface LegacyViabilityWaiver {
  id: string;
  codes: string[];
  subjects: string[];
  reason: string;
  expiresAt: string;
  assertedBy: string;
}
export interface LegacyGraphBinding {
  id: string;
  revision?: string;
  digest?: string;
}
export type LegacyMappingViabilityDeclaration = {
  coverage: LegacyMappingCoverage;
  determinism: LegacyMappingDeterminism;
  reversibility: LegacyMappingReversibility;
  applicability?: LegacyMappingApplicability;
} & (
  | { mapping: string; select?: never }
  | { select: LegacyMappingViabilitySelector; mapping?: never }
);
export interface LegacyMetamapViabilityPolicy {
  $schema?: string;
  schemaVersion: "1.0.0";
  id: string;
  graph: LegacyGraphBinding;
  mappings: LegacyMappingViabilityDeclaration[];
  constraints: LegacyViabilityConstraint[];
  evidence: LegacyEvidenceRecord[];
  waivers?: LegacyViabilityWaiver[];
  metadata?: Record<string, JsonValue>;
}
export interface LegacyContentBinding {
  id: string;
  digest: string;
}
export interface LegacyPackContentBinding extends LegacyContentBinding {
  version: string;
}
export interface LegacyDerivationPremise {
  mapping: string;
  digest: string;
  derivation?: LegacyContentBinding;
}
export type LegacyUncertaintyDimension =
  | "identity"
  | "context"
  | "provenance"
  | "completeness"
  | "causal-relevance"
  | "conflicting-authority";
export type LegacyUncertaintyStatus =
  "supported" | "contradicted" | "unknown" | "not-applicable";
export interface LegacyDerivationUncertainty {
  dimension: LegacyUncertaintyDimension;
  status: LegacyUncertaintyStatus;
  evidence: string[];
  assessments: string[];
  measurementModels: string[];
  sourceRevisions: string[];
}
export interface LegacyCorrespondenceDerivation {
  $schema?: string;
  schemaVersion: "1.0.0";
  id: string;
  digest: string;
  interpretation: "declared-law-application";
  rule: {
    id: string;
    pack: LegacyPackContentBinding;
    imports: LegacyPackContentBinding[];
  };
  premises: LegacyDerivationPremise[];
  result: LegacyStructuralMapping;
  context: LegacyEvaluationContext;
  contextDigest: string;
  dependencies: LegacyContentBinding[];
  depth: number;
  derivationCount: number;
  uncertainty: LegacyDerivationUncertainty[];
}
export interface LegacyImpactOptions {
  changedSubjects: readonly string[];
  activeMappings?: ReadonlySet<string>;
  registry?: LegacyRelationRegistry;
  policy?: LegacyMetamapViabilityPolicy;
  derivations?: readonly LegacyCorrespondenceDerivation[];
}
export interface LegacyImpactPath {
  subjectId: string;
  path: string[];
}
export interface LegacyImpactReport {
  changedSubjects: string[];
  affectedSubjects: string[];
  paths: LegacyImpactPath[];
}
export function parseLegacyEvaluationContext(
  value: unknown,
): LegacyEvaluationContext;
export function evaluateLegacyContextExpression(
  expression: LegacyContextExpression,
  context: Readonly<LegacyEvaluationContext>,
): boolean;
export function requiredLegacyContextKeys(
  expression: LegacyContextExpression,
): Set<string>;
export function legacyInactiveReason(
  applicability: LegacyMappingApplicability | undefined,
  context: Readonly<LegacyEvaluationContext>,
): LegacyInactiveMappingReason | undefined;
export function legacySelectorMatches(
  mapping: LegacySelectorMapping,
  selector: LegacyMappingViabilitySelector,
  entityKinds: ReadonlyMap<string, string>,
): boolean;
export function analyzeLegacyImpact(
  document: LegacyImpactDocument,
  options: LegacyImpactOptions,
): LegacyImpactReport;
