import type { JsonValue } from "./canonical.js";
type JsonObject = { [key: string]: JsonValue };
import type { LegacyCorrespondenceConfig } from "./legacy-correspondence.js";
export declare const LEGACY_METAMAP_CONFIG_VERSION: "1.0.0";
export interface LegacyMetamapSourceConfig {
  id: string;
  adapter: string;
  readonly [key: string]: unknown;
}
export interface LegacyPrismaSourceConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "prisma";
  path: string;
}
export interface LegacyTypeScriptZodSourceConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "typescript-zod";
  roots: string[];
  exclude?: string[];
}
export interface LegacySourcesConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "legacy-sources";
  path: string;
}
export interface LegacySssomSourceConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "sssom-tsv";
  path: string;
  metadataPath?: string;
  formatVersion: "1.0.0";
  sourceRevision: string;
  recordIdColumn?: string;
  provenance?: JsonObject;
}
export interface LegacyJsonReferenceConfig {
  property: string;
  targetKind: string;
  relation?: string;
}
export interface LegacyJsonCollectionConfig {
  pointer: string;
  idProperty: string;
  labelProperty?: string;
  entityKind: string;
  references?: LegacyJsonReferenceConfig[];
}
export interface LegacyJsonCollectionsSourceConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "json-collections";
  path: string;
  collections: LegacyJsonCollectionConfig[];
}
export interface LegacyMetamapShardSourceConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "metamap-shard";
  path: string;
}
export interface LegacyNextjsTopologyExclusion {
  path: string;
  reason: string;
  assertedBy: string;
  relations?: string[];
}
export interface LegacyNextjsAppRouterSourceConfig extends LegacyMetamapSourceConfig {
  id: string;
  adapter: "nextjs-app-router";
  root: string;
  extensions?: string[];
  exclusions?: LegacyNextjsTopologyExclusion[];
}
export type LegacyBuiltInSourceConfig =
  | LegacyPrismaSourceConfig
  | LegacyTypeScriptZodSourceConfig
  | LegacySourcesConfig
  | LegacyJsonCollectionsSourceConfig
  | LegacyMetamapShardSourceConfig
  | LegacyNextjsAppRouterSourceConfig;
export interface LegacyMetamapOutputConfig {
  graph: string;
  snapshot: string;
  report: string;
  documentation: string;
  cache?: string;
}
export interface LegacyMetamapPolicyConfig {
  baselineChanges?: "error" | "warning" | "ignore";
  unconfiguredStructures?: "error" | "warning" | "ignore";
}
export interface LegacyMetamapConfig {
  $schema?: string;
  schemaVersion: typeof LEGACY_METAMAP_CONFIG_VERSION;
  id: string;
  label?: string;
  namespace: string;
  repository: string;
  repositoryRoot: string;
  relationPacks?: string[];
  sources: LegacyMetamapSourceConfig[];
  correspondences: LegacyCorrespondenceConfig[];
  outputs: LegacyMetamapOutputConfig;
  policy?: LegacyMetamapPolicyConfig;
}
export interface LegacyLoadedMetamapConfig {
  config: LegacyMetamapConfig;
  configPath: string;
  configDirectory: string;
  repositoryRoot: string;
}
export declare function parseLegacyMetamapConfig(
  value: unknown,
): LegacyMetamapConfig;
export declare function loadLegacyMetamapConfig(
  path: string,
): Promise<LegacyLoadedMetamapConfig>;
