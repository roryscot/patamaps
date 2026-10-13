export type JsonValue =
  null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export interface NativeJsonExecution {
  command: string[];
  input: string;
  exitCode: number | null;
  signal: string | null;
  stdout: string;
  stderr: string;
  processError: string | null;
}
export declare class CanonicalJsonError extends Error {
  readonly code: string;
  readonly nativeMessage?: string;
  constructor(code: string, message: string);
}
export interface CanonicalApi {
  canonicalJson(value: unknown): string;
  canonicalDigest(value: unknown): string;
  parseStrictJson(text: string): JsonValue;
  legacyReferenceValue(value: unknown): JsonValue;
}
export declare function createCanonicalApi(
  executable: string,
  observeExecution?: (execution: NativeJsonExecution) => void,
): CanonicalApi;
export declare function configureCanonical(
  executable: string,
  observeExecution?: (execution: NativeJsonExecution) => void,
): void;
export declare function canonicalJson(value: unknown): string;
export declare function canonicalDigest(value: unknown): string;
export declare function parseStrictJson(text: string): JsonValue;
export declare function legacyReferenceValue(value: unknown): JsonValue;
