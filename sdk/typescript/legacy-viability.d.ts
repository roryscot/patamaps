import type { LegacyGraphDocument } from "./legacy-graph.js";
import type { LegacyRelationRegistry } from "./legacy-validation.js";
import type {
  LegacyEvaluationContext,
  LegacyInactiveMappingReason,
  LegacyImpactReport,
  LegacyMetamapViabilityPolicy,
} from "./legacy-evaluation.js";

export const LEGACY_METAMAP_VIABILITY_POLICY_VERSION: "1.0.0";
export const LEGACY_METAMAP_GENERATION_VERSION: "1.0.0";

export type LegacyViabilitySeverity = "error" | "warning";
export interface LegacyViabilityIssue {
  severity: LegacyViabilitySeverity;
  code: string;
  message: string;
  path?: string;
  subjectId?: string;
  causalPath?: string[];
  waivedBy?: string;
}
export interface LegacyViabilityValidationResult {
  valid: boolean;
  issues: LegacyViabilityIssue[];
}
export interface LegacyInactiveMapping {
  id: string;
  reason: LegacyInactiveMappingReason;
}
export interface LegacyViableGeneration {
  $schema?: string;
  schemaVersion: "1.0.0";
  id: string;
  digest: string;
  evaluatedAt: string;
  graph: { id: string; revision?: string; digest: string };
  policy: { id: string; digest: string };
  context: LegacyEvaluationContext;
  activeMappings: string[];
  inactiveMappings: LegacyInactiveMapping[];
  evidence: string[];
  waiversApplied: string[];
}
export interface LegacyCompileOptions {
  context?: LegacyEvaluationContext;
  evaluatedAt?: string;
  changedSubjects?: readonly string[];
}
/** The original custom constraint callback transport remains unfinished. */
export interface LegacyCompilationRuntimeOptions extends LegacyCompileOptions {
  relationRegistry?: LegacyRelationRegistry;
}
export type LegacyCompilationResult =
  | {
      status: "viable";
      generation: LegacyViableGeneration;
      issues: LegacyViabilityIssue[];
      impact: LegacyImpactReport;
    }
  | {
      status: "rejected";
      issues: LegacyViabilityIssue[];
      impact: LegacyImpactReport;
      quarantinedSubjects: string[];
    };
export function validateLegacyViabilityPolicy(
  value: unknown,
): LegacyViabilityValidationResult;
export function validateLegacyViableGeneration(
  value: unknown,
): LegacyViabilityValidationResult;
export function parseLegacyViabilityPolicy(
  value: unknown,
): LegacyMetamapViabilityPolicy;
export function parseLegacyViableGeneration(
  value: unknown,
): LegacyViableGeneration;
export function compileLegacyMetamap(
  document: LegacyGraphDocument,
  policy: LegacyMetamapViabilityPolicy,
  options?: LegacyCompilationRuntimeOptions,
): LegacyCompilationResult;
