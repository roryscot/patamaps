import type { LegacyGraphDocument } from "./legacy-graph.js";
export interface LegacySourceOfTruthEntry {
  id: string;
  label: string;
  paths: string[];
  outputs: string[];
  updateSteps?: string;
  specDoc?: string;
  note?: string;
}
export interface LegacySourceOfTruthDocument {
  description?: string;
  sourcesOfTruth: LegacySourceOfTruthEntry[];
}
export interface LegacySourcesOfTruthWarning {
  code:
    "LEGACY_MULTIPLE_SOURCES" | "LEGACY_AMBIGUOUS_PATH" | "LEGACY_PATH_PATTERN";
  message: string;
  entryId: string;
  value?: string;
}
export interface LegacySourcesOfTruthOptions {
  namespace?: string;
  repository?: string;
  documentId?: string;
  label?: string;
}
export interface LegacySourcesOfTruthResult {
  document: LegacyGraphDocument;
  warnings: LegacySourcesOfTruthWarning[];
}
export interface LegacyCliResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}
export declare function runLegacyCli(
  args: readonly string[],
): Promise<LegacyCliResult>;
export declare function isLegacySourceOfTruthDocument(
  value: unknown,
): value is LegacySourceOfTruthDocument;
export declare function adaptLegacySourcesOfTruth(
  legacy: LegacySourceOfTruthDocument,
  options?: LegacySourcesOfTruthOptions,
): LegacySourcesOfTruthResult;
