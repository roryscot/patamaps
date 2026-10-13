import type {
  LEGACY_METAMAP_CONFIG_VERSION,
  parseLegacyMetamapConfig,
  loadLegacyMetamapConfig,
} from "./legacy-config.js";
export * from "./legacy-config.js";
import type { JsonValue, NativeJsonExecution } from "./canonical.js";
import type { LegacyGraph } from "./legacy-graph.js";
import type { composeLegacyDocuments } from "./legacy-composition.js";
import type {
  diffLegacyDocuments,
  emptyLegacyGraphDiff,
  renderLegacyDriftReport,
  renderLegacyGraphDocumentation,
} from "./legacy-reporting.js";
export * from "./legacy-reporting.js";
import type { materializeLegacyCorrespondences } from "./legacy-correspondence.js";
import type {
  isLegacyReferenceIdentifier,
  isLegacyRelationIdentifier,
  makeLegacyUrn,
  makeLegacyRepositoryUri,
  hasLegacyAmbiguousPathLanguage,
  isLegacyPathPattern,
} from "./legacy-references.js";
export * from "./legacy-correspondence.js";
export * from "./legacy-references.js";
export * from "./legacy-composition.js";
export * from "./legacy-graph.js";

export type LegacyCyclePolicy = "allow" | "forbid";
export type LegacyImpactDirection =
  "source-to-target" | "target-to-source" | "both" | "none";
export type LegacyMappingCardinality =
  "one-to-one" | "one-to-many" | "many-to-one" | "many-to-many";
export interface LegacyRelationDefinition {
  id: string;
  cyclePolicy: LegacyCyclePolicy;
  description?: string;
  sourceKinds?: readonly string[];
  targetKinds?: readonly string[];
  cardinalities?: readonly LegacyMappingCardinality[];
  transitive?: boolean;
  symmetric?: boolean;
  inverse?: string;
  composesWith?: readonly string[];
  impactDirection?: LegacyImpactDirection;
}
export interface LegacyExecutableRelationDefinition extends LegacyRelationDefinition {
  disjointWith?: readonly string[];
}
export type LegacyContextExpression =
  | {
      key: string;
      operator: "equals" | "not-equals";
      value: null | boolean | number | string;
    }
  | {
      key: string;
      operator: "in" | "not-in";
      values: (null | boolean | number | string)[];
    }
  | { key: string; operator: "exists"; value?: boolean }
  | { all: LegacyContextExpression[] }
  | { any: LegacyContextExpression[] }
  | { not: LegacyContextExpression };
export interface LegacyLawConditions {
  context?: LegacyContextExpression;
  sourceKinds?: readonly string[];
  middleKinds?: readonly string[];
  targetKinds?: readonly string[];
}
export type LegacyRelationLaw = {
  id: string;
  resultRelation: string;
  conditions?: LegacyLawConditions;
  handling: {
    lossiness: "conservative";
    uncertainty: "conservative";
    authority: "none";
  };
} & (
  | {
      operation: "reverse";
      operands: readonly [string];
    }
  | {
      operation: "chain";
      operands: readonly [string, string];
    }
);
export interface LegacyPackBinding {
  id: string;
  version: string;
  digest: string;
}
export interface LegacyPortableRelationPack {
  $schema?: string;
  schemaVersion: "1.0.0";
  id: string;
  version: string;
  description?: string;
  relations: readonly LegacyRelationDefinition[];
}
export interface LegacyExecutableRelationPack {
  $schema?: string;
  schemaVersion: "2.0.0";
  id: string;
  version: string;
  description?: string;
  relations: readonly LegacyExecutableRelationDefinition[];
  imports?: readonly LegacyPackBinding[];
  laws: readonly LegacyRelationLaw[];
}
export type LegacyRelationPack =
  LegacyPortableRelationPack | LegacyExecutableRelationPack;
export interface NativeRelationPackView {
  $schema?: string;
  schemaVersion: "0.1.0";
  documentType: "relation-pack";
  id: string;
  version: string;
  description?: string;
  relations: LegacyExecutableRelationDefinition[];
  imports?: LegacyPackBinding[];
  laws?: LegacyRelationLaw[];
}
/** Read-only interpretation; the original value/digest remains separate. */
export interface LegacyPackSourceRecord {
  byteDigest: string;
  byteLength: number;
  utf8ReplacementOccurred: boolean;
  duplicatePropertyPolicy: "last-property-wins" | "reject-decoded-duplicates";
}
export interface LegacyPackImportReport {
  source?: LegacyPackSourceRecord;
  sourceSchemaVersion: "1.0.0" | "2.0.0";
  originalDocumentDigest: string;
  originalDigestConvention:
    "metamap-stable-json-lf-sha256" | "rfc8785-jcs-sha256";
  nativeViewDigest: string;
  nativeView: NativeRelationPackView;
  changes: {
    operation: "replace" | "add";
    path: string;
    before?: JsonValue;
    after: JsonValue;
    reason: string;
  }[];
  discardedPaths: string[];
  pendingChecks: { path: string; code: string; message: string }[];
  registryValidated: false;
  admitted: false;
}

export interface LegacyValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  path?: string;
  subjectId?: string;
}
export interface LegacyValidationResult {
  valid: boolean;
  issues: LegacyValidationIssue[];
}
export type LegacyValidationOptions =
  | {
      /** Modern Patamaps draft relation packs. An explicit [] selects no packs.
       * Omission selects the original MetaMap 1.0 core identity and definitions.
       * Supply either these or portable legacyPacks. */
      nativePacks?: readonly unknown[];
      legacyPacks?: never;
    }
  | {
      /** Portable legacy 1.0/2.0 data. Dependency bindings use original addresses.
       * This is an immutable JSON snapshot, not the original mutable JS registry. */
      legacyPacks: readonly LegacyRelationPack[];
      nativePacks?: never;
    };
export interface LegacyValidationApi {
  readonly LEGACY_METAMAP_CONFIG_VERSION: typeof LEGACY_METAMAP_CONFIG_VERSION;
  parseLegacyMetamapConfig: typeof parseLegacyMetamapConfig;
  loadLegacyMetamapConfig: typeof loadLegacyMetamapConfig;
  materializeLegacyCorrespondences: typeof materializeLegacyCorrespondences;
  isLegacyReferenceIdentifier: typeof isLegacyReferenceIdentifier;
  isLegacyRelationIdentifier: typeof isLegacyRelationIdentifier;
  makeLegacyUrn: typeof makeLegacyUrn;
  makeLegacyRepositoryUri: typeof makeLegacyRepositoryUri;
  hasLegacyAmbiguousPathLanguage: typeof hasLegacyAmbiguousPathLanguage;
  isLegacyPathPattern: typeof isLegacyPathPattern;
  LegacyGraph: typeof LegacyGraph;
  composeLegacyDocuments: typeof composeLegacyDocuments;
  diffLegacyDocuments: typeof diffLegacyDocuments;
  emptyLegacyGraphDiff: typeof emptyLegacyGraphDiff;
  renderLegacyDriftReport: typeof renderLegacyDriftReport;
  renderLegacyGraphDocumentation: typeof renderLegacyGraphDocumentation;
  LegacyRelationRegistry: new (
    packs?: readonly LegacyRelationPack[],
  ) => LegacyRelationRegistry;
  readonly legacyCoreRelationPack: LegacyPortableRelationPack;
  validateLegacyDocument(
    document: unknown,
    options?: LegacyValidationOptions,
  ): LegacyValidationResult;
  validateLegacyDocumentShape(document: unknown): LegacyValidationIssue[];
  parseLegacyRelationPack(value: unknown): LegacyRelationPack;
  importLegacyRelationPack(value: unknown): LegacyPackImportReport;
  /** Version-dispatched JSON digest without shape validation. Arbitrary unchecked
   * JS object serialization remains outside this provisional transport. */
  digestLegacyRelationPack(value: unknown): string;
  loadLegacyRelationPack(path: string): Promise<LegacyRelationPack>;
}
export declare function createLegacyValidationApi(
  executable: string,
  observeExecution?: (execution: NativeJsonExecution) => void,
): LegacyValidationApi;
export declare function configureLegacyValidation(
  executable: string,
  observeExecution?: (execution: NativeJsonExecution) => void,
): void;
export declare function validateLegacyDocument(
  document: unknown,
  options?: LegacyValidationOptions,
): LegacyValidationResult;
export declare function validateLegacyDocumentShape(
  document: unknown,
): LegacyValidationIssue[];
export declare function parseLegacyRelationPack(
  value: unknown,
): LegacyRelationPack;
export declare function importLegacyRelationPack(
  value: unknown,
): LegacyPackImportReport;
export declare function digestLegacyRelationPack(value: unknown): string;
export declare function loadLegacyRelationPack(
  path: string,
): Promise<LegacyRelationPack>;

/** Legacy object identity transport. This is not an admitted native registry.
 * Portable pack data is supported; arbitrary JS prototypes/accessors and
 * unchecked non-JSON values remain outside this provisional implementation. */
export declare class LegacyRelationRegistry {
  constructor(packs?: readonly LegacyRelationPack[]);
  registerPack(pack: LegacyRelationPack): void;
  getPack(id: string): LegacyRelationPack | undefined;
  getLaw(
    id: string,
  ): { pack: LegacyExecutableRelationPack; law: LegacyRelationLaw } | undefined;
  executablePacks(): LegacyExecutableRelationPack[];
  get(id: string): LegacyRelationDefinition | undefined;
  hasPack(id: string, version?: string): boolean;
  all(): LegacyRelationDefinition[];
  allPacks(): LegacyRelationPack[];
}
export declare function legacyCoreRelationPack(): LegacyPortableRelationPack;
