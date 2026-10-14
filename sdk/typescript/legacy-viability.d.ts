import type { LegacyGraph, LegacyGraphDocument } from "./legacy-graph.js";
import type { LegacyRelationRegistry } from "./legacy-validation.js";
import type {
  LegacyEvaluationContext,
  LegacyInactiveMappingReason,
  LegacyImpactReport,
  LegacyMetamapViabilityPolicy,
  LegacyEvidenceRecord,
  LegacyViabilityConstraint,
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
export interface LegacyConstraintEvaluationContext {
  document: LegacyGraphDocument;
  graph: LegacyGraph;
  activeMappings: ReadonlySet<string>;
  evidence: readonly LegacyEvidenceRecord[];
}
export type LegacyConstraintEvaluator = (
  constraint: LegacyViabilityConstraint,
  context: LegacyConstraintEvaluationContext,
) => LegacyViabilityIssue[];
export class LegacyConstraintRegistry {
  private readonly evaluators: Map<string, LegacyConstraintEvaluator>;
  constructor();
  register(kind: string, evaluator: LegacyConstraintEvaluator): void;
  get(kind: string): LegacyConstraintEvaluator | undefined;
}
export interface LegacyCompilationRuntimeOptions extends LegacyCompileOptions {
  relationRegistry?: LegacyRelationRegistry;
  constraintRegistry?: LegacyConstraintRegistry;
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
export type LegacyActivationResult =
  | {
      activated: true;
      current: LegacyViableGeneration;
      compilation: Extract<LegacyCompilationResult, { status: "viable" }>;
    }
  | {
      activated: false;
      current?: LegacyViableGeneration;
      compilation: Extract<LegacyCompilationResult, { status: "rejected" }>;
    };
/** Original memory interface. Signed governed overloads remain unfinished. */
export class LegacyMetamapActivator {
  private readonly relationRegistry: LegacyRelationRegistry;
  private readonly constraintRegistry: LegacyConstraintRegistry;
  private generation?: LegacyViableGeneration;
  constructor(
    relationRegistry?: LegacyRelationRegistry,
    constraintRegistry?: LegacyConstraintRegistry,
  );
  get current(): LegacyViableGeneration | undefined;
  get governedCurrent(): undefined;
  activate(
    document: LegacyGraphDocument,
    policy: LegacyMetamapViabilityPolicy,
    options?: LegacyCompileOptions,
  ): LegacyActivationResult;
}
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
