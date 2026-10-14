import type { LegacyGraphDocument } from "./legacy-graph.js";
export interface LegacyCompositionOptions {
  id: string;
  namespace: string;
  label?: string;
  revision?: string;
}
export declare class LegacyCompositionError extends Error {
  readonly identifier?: string;
  constructor(message: string, identifier?: string);
}
/** Retains first source objects. This is not a checked/admitted generation. */
export declare function composeLegacyDocuments(
  documents: readonly LegacyGraphDocument[],
  options: LegacyCompositionOptions,
): LegacyGraphDocument;
