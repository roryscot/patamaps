import type {
  LegacyMetamapProjectionSpec,
  LegacyProjectionDirection,
  LegacyProjectionCardinality,
} from "./legacy-uncertainty-risk.js";
import type { LegacyEntity, LegacyGraphDocument } from "./legacy-graph.js";
import type { LegacyRelationRegistry } from "./legacy-validation.js";
import type { LegacyViableGeneration } from "./legacy-viability.js";
export const LEGACY_METAMAP_PROJECTION_SPEC_VERSION: "1.0.0";
export const LEGACY_METAMAP_PROJECTION_VERSION: "1.0.0";
export type LegacyProjectionSpec = LegacyMetamapProjectionSpec;
export type LegacyProjectedEntity = Omit<LegacyEntity, "provenance">;
export interface LegacyProjectedSlot {
  name: string;
  relation: string;
  direction: LegacyProjectionDirection;
  cardinality: LegacyProjectionCardinality;
  mappings: string[];
  targets: LegacyProjectedEntity[];
}
export interface LegacyProjection {
  $schema?: string;
  schemaVersion: "1.0.0";
  id: string;
  digest: string;
  generation: { id: string; digest: string };
  graph: { id: string; digest: string };
  spec: { id: string; digest: string };
  entries: { subject: LegacyProjectedEntity; slots: LegacyProjectedSlot[] }[];
}
export interface LegacyProjectionIssue {
  severity: "error";
  code: string;
  message: string;
  subjectId?: string;
  slot?: string;
  path?: string;
}
export interface LegacyProjectionValidation {
  valid: boolean;
  issues: LegacyProjectionIssue[];
}
export type LegacyProjectionCompilation =
  | {
      status: "projected";
      projection: LegacyProjection;
      issues: LegacyProjectionIssue[];
    }
  | { status: "rejected"; issues: LegacyProjectionIssue[] };
export function validateLegacyProjectionSpec(
  value: unknown,
): LegacyProjectionValidation;
export function parseLegacyProjectionSpec(value: unknown): LegacyProjectionSpec;
export function validateLegacyProjection(
  value: unknown,
): LegacyProjectionValidation;
export function parseLegacyProjection(value: unknown): LegacyProjection;
export function compileLegacyProjection(
  document: LegacyGraphDocument,
  generation: LegacyViableGeneration,
  spec: LegacyProjectionSpec,
  options?: { relationRegistry?: LegacyRelationRegistry },
): LegacyProjectionCompilation;

/** Static legacy data rendering; this never admits a generation. */
export function emitLegacyTypeScriptProjection(
  projection: LegacyProjection,
  options?: { exportName?: string },
): string;
