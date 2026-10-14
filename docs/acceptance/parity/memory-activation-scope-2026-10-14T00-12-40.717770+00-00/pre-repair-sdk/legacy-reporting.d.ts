import type { LegacyGraphDocument } from "./legacy-graph.js";
import type {
  LegacyValidationIssue,
  LegacyValidationResult,
} from "./legacy-validation.js";

export type LegacyGraphRecordKind = "entity" | "mapping" | "authority";
export type LegacyGraphChangeKind = "added" | "removed" | "changed";
export interface LegacyGraphChange {
  change: LegacyGraphChangeKind;
  kind: LegacyGraphRecordKind;
  id: string;
  changedProperties?: string[];
}
export interface LegacyGraphDiff {
  changes: LegacyGraphChange[];
  counts: Record<LegacyGraphChangeKind, number>;
}
export interface LegacyReportAdapterResult {
  sourceId: string;
  adapter: string;
  adapterVersion: string;
  inputs: { path: string; digest: string }[];
  document: LegacyGraphDocument;
  diagnostics: LegacyValidationIssue[];
}
export interface LegacyReportDriftIssue {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  correspondenceId?: string;
  sourceId?: string;
  targetId?: string;
  fact?:
    | "type"
    | "presence"
    | "nullability"
    | "cardinality"
    | "enum-values"
    | "coverage";
}
export interface LegacyReportInput {
  graph: LegacyGraphDocument;
  adapters: readonly LegacyReportAdapterResult[];
  driftIssues: readonly LegacyReportDriftIssue[];
  validation: LegacyValidationResult;
  diff: LegacyGraphDiff;
  cacheHits?: readonly string[];
}
/** JSON snapshots only; these operations perform no graph admission. */
export declare function diffLegacyDocuments(
  before: LegacyGraphDocument,
  after: LegacyGraphDocument,
): LegacyGraphDiff;
export declare function emptyLegacyGraphDiff(): LegacyGraphDiff;
export declare function renderLegacyDriftReport(
  input: LegacyReportInput,
): string;
export declare function renderLegacyGraphDocumentation(
  graph: LegacyGraphDocument,
  correspondences: readonly { id: string }[],
): string;
