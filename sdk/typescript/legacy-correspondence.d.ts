import type { LegacyGraphDocument } from "./legacy-graph.js";
import type { LegacyReportDriftIssue } from "./legacy-reporting.js";
export type LegacyComparedFact =
  "type" | "presence" | "nullability" | "cardinality";
export interface LegacyStructureReferenceConfig {
  sourceId: string;
  kind: string;
  name: string;
}
export interface LegacyFieldPairConfig {
  source: string;
  target: string;
  compare?: LegacyComparedFact[];
  allowDifferences?: LegacyComparedFact[];
  transform?: string;
  note?: string;
}
export interface LegacyFieldCorrespondenceConfig {
  pairs: LegacyFieldPairConfig[];
  ignoreSource?: string[];
  ignoreTarget?: string[];
  requireSourceCoverage?: boolean;
  requireTargetCoverage?: boolean;
}
export interface LegacyEnumCorrespondenceConfig {
  allowSourceOnly?: string[];
  allowTargetOnly?: string[];
}
export interface LegacyCorrespondenceAuthorityConfig {
  side: "source" | "target";
  facts: string[];
}
export interface LegacyCorrespondenceConfig {
  id: string;
  source: LegacyStructureReferenceConfig;
  target: LegacyStructureReferenceConfig;
  relation?: string;
  fields?: LegacyFieldCorrespondenceConfig;
  enumValues?: LegacyEnumCorrespondenceConfig;
  authority?: LegacyCorrespondenceAuthorityConfig;
}
export type LegacyDriftIssue = LegacyReportDriftIssue;
export interface LegacyCorrespondenceResult {
  document: LegacyGraphDocument;
  issues: LegacyDriftIssue[];
  configuredStructureIds: Set<string>;
}
/** Read-only declaration/drift results; no admission or authority evaluation. */
export declare function materializeLegacyCorrespondences(
  namespace: string,
  documentId: string,
  discovered: LegacyGraphDocument,
  configurations: readonly LegacyCorrespondenceConfig[],
  configRevision: string,
): LegacyCorrespondenceResult;
