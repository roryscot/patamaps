export const SSSOM_MAX_BYTES: number;
export const SSSOM_FORMAT_VERSION: "1.0.0";
export const SSSOM_ENTITY_PROFILE: "sssom-1.0-entity-tsv";
export const SSSOM_BUILTIN_PREFIXES: Readonly<Record<string, string>>;
export const SSSOM_PROPAGATABLE_SLOTS: readonly string[];
import type { JsonValue } from "./canonical.js";
export interface SssomSourceConfig {
  id: string;
  adapter: "sssom-tsv";
  path: string;
  formatVersion: "1.0.0";
  sourceRevision: string;
  metadataPath?: string;
  recordIdColumn?: string;
  provenance?: Record<string, JsonValue>;
}
export interface SssomDocument {
  schemaVersion: typeof SSSOM_FORMAT_VERSION;
  profile: typeof SSSOM_ENTITY_PROFILE;
  metadata: { [key: string]: JsonValue };
  columns: string[];
  rows: string[][];
}
export interface SssomRecord {
  raw: Record<string, string>;
  fields: Record<string, JsonValue>;
  origins: Record<string, "record" | "set">;
  expanded: Record<string, string | string[]>;
}
export interface SssomInterpretation {
  metadata: Record<string, JsonValue>;
  prefixes: Record<string, string>;
  extensions: Array<{ name: string; property: string; type: string }>;
  propagation: Array<{
    slot: string;
    status: "propagated" | "blocked-by-record-value";
    value: JsonValue;
  }>;
  records: SssomRecord[];
}
export interface SssomExportResult {
  text: string;
  loss: {
    profile: typeof SSSOM_ENTITY_PROFILE;
    semanticFieldsPreserved: true;
    byteIdentityPreserved: false;
    droppedFields: [];
    condensedSlots: string[];
    normalization: string[];
  };
}
export class SssomError extends Error {
  readonly code: string;
  constructor(code: string, message: string);
}
export interface SssomApi {
  parseSssomTsv(
    input: string | Uint8Array,
    externalMetadata?: string | Uint8Array,
  ): SssomDocument;
  parseSssomDocument(value: unknown): SssomDocument;
  parseSssomSourceConfig(value: unknown): SssomSourceConfig;
  interpretSssomDocument(value: unknown): SssomInterpretation;
  exportSssomTsv(
    value: unknown,
    options?: { condense?: boolean },
  ): SssomExportResult;
  expandSssomCurie(
    value: string,
    prefixes: Readonly<Record<string, string>>,
  ): string;
}
export interface SssomExecution {
  command: string[];
  input: string;
  exitCode: number | null;
  signal: string | null;
  stdout: string;
  stderr: string;
  processError: string | null;
}
export function createSssomApi(
  executable: string,
  observeExecution?: (execution: SssomExecution) => void,
): SssomApi;
export function configureSssom(
  executable: string,
  observeExecution?: (execution: SssomExecution) => void,
): void;
export const parseSssomTsv: SssomApi["parseSssomTsv"];
export const parseSssomDocument: SssomApi["parseSssomDocument"];
export const parseSssomSourceConfig: SssomApi["parseSssomSourceConfig"];
export const interpretSssomDocument: SssomApi["interpretSssomDocument"];
export const exportSssomTsv: SssomApi["exportSssomTsv"];
export const expandSssomCurie: SssomApi["expandSssomCurie"];
