import type { JsonValue } from "./canonical.js";
import type {
  LegacyRelationRegistry,
  LegacyValidationIssue,
  LegacyMappingCardinality,
} from "./legacy-validation.js";

export type LegacyProvenanceStatus =
  "declared" | "observed" | "generated" | "inferred";
export interface LegacyProvenance {
  status: LegacyProvenanceStatus;
  assertedBy: string;
  observedAt?: string;
  sourceRevision?: string;
  confidence?: number;
}
export interface LegacyLocator {
  uri: string;
  mediaType?: string;
  revision?: string;
  digest?: string;
}
export interface LegacyEntity {
  id: string;
  kind: string;
  label?: string;
  schema?: string;
  locators?: LegacyLocator[];
  attributes?: { [key: string]: JsonValue };
  provenance?: LegacyProvenance;
}
export type LegacyMappingLossiness = "lossless" | "lossy" | "unknown";
export interface LegacyTransformReference {
  adapter: string;
  version: string;
  entrypoint?: string;
  deterministic?: boolean;
  reversible?: boolean;
  configuration?: { [key: string]: JsonValue };
}
export interface LegacyStructuralMapping {
  id: string;
  relation: string;
  sources: string[];
  targets: string[];
  cardinality: LegacyMappingCardinality;
  lossiness: LegacyMappingLossiness;
  transform?: LegacyTransformReference;
  invariants?: string[];
  attributes?: { [key: string]: JsonValue };
  provenance: LegacyProvenance;
}
export type LegacyAuthorityMode = "canonical" | "delegated" | "candidate";
interface LegacyAuthorityBase {
  id: string;
  concept: string;
  source: string;
  facts: string[];
  provenance: LegacyProvenance;
}
export type LegacyAuthorityDeclaration = LegacyAuthorityBase &
  (
    | { mode: "canonical" | "candidate"; delegatedFrom?: never }
    | { mode: "delegated"; delegatedFrom: string }
  );
export interface LegacyRelationPackReference {
  id: string;
  version: string;
  uri?: string;
  digest?: string;
}
export interface LegacyGraphDocument {
  $schema?: string;
  schemaVersion: "2.0.0";
  id: string;
  namespace: string;
  label?: string;
  revision?: string;
  relationPacks?: LegacyRelationPackReference[];
  entities: LegacyEntity[];
  mappings: LegacyStructuralMapping[];
  authorities: LegacyAuthorityDeclaration[];
  metadata?: { [key: string]: JsonValue };
  extensions?: { [key: string]: JsonValue };
}
export type LegacyTraversalDirection = "outgoing" | "incoming" | "both";
export interface LegacyTraversalOptions {
  direction?: LegacyTraversalDirection;
  relations?: readonly string[];
  maxDepth?: number;
}
export interface LegacyTraversalVisit {
  entity: LegacyEntity;
  depth: number;
  viaMapping?: LegacyStructuralMapping;
  predecessor?: string;
}
export interface LegacyAuthorityResolution {
  status: "resolved" | "ambiguous" | "unresolved";
  canonical?: LegacyAuthorityDeclaration;
  effective?: LegacyAuthorityDeclaration;
  delegationChain?: LegacyAuthorityDeclaration[];
  candidates: LegacyAuthorityDeclaration[];
}
export interface LegacyGraphOptions {
  registry?: LegacyRelationRegistry;
  validate?: boolean;
}
export declare class LegacyGraphValidationError extends Error {
  readonly issues: LegacyValidationIssue[];
  constructor(issues: LegacyValidationIssue[]);
}
/** Legacy query observations. This view supplies no checked/admitted capability.
 * Complete non-JSON JavaScript and accepted-domain parity remains provisional. */
export declare class LegacyGraph {
  readonly document: LegacyGraphDocument;
  readonly registry: LegacyRelationRegistry;
  readonly validationIssues: LegacyValidationIssue[];
  constructor(document: LegacyGraphDocument, options?: LegacyGraphOptions);
  static from(value: unknown, options?: LegacyGraphOptions): LegacyGraph;
  getEntity(id: string): LegacyEntity | undefined;
  getMapping(id: string): LegacyStructuralMapping | undefined;
  mappingsFor(
    id: string,
    options?: Pick<LegacyTraversalOptions, "direction" | "relations">,
  ): LegacyStructuralMapping[];
  neighbors(
    id: string,
    options?: Pick<LegacyTraversalOptions, "direction" | "relations">,
  ): { entity: LegacyEntity; mapping: LegacyStructuralMapping }[];
  trace(id: string, options?: LegacyTraversalOptions): LegacyTraversalVisit[];
  resolveAuthority(conceptId: string, fact: string): LegacyAuthorityResolution;
}
