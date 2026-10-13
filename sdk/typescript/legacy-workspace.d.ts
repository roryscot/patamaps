import type { LegacyGraphDocument } from "./legacy-graph.js";
import type {
  LegacyValidationResult,
  LegacyRelationRegistry,
} from "./legacy-validation.js";
import type {
  LegacyMetamapSourceConfig,
  LegacyMetamapConfig,
  LegacyLoadedMetamapConfig,
} from "./legacy-config.js";
import type { LegacyDriftIssue } from "./legacy-correspondence.js";
import type { LegacyGraphDiff } from "./legacy-reporting.js";
import type { LegacyRelationPack } from "./legacy-validation.js";
export interface LegacyAdapterInput {
  path: string;
  digest: string;
}
export interface LegacyAdapterDiagnostic {
  severity: "warning" | "error";
  code: string;
  message: string;
  path?: string;
  subjectId?: string;
}
export interface LegacyAdapterContext {
  namespace: string;
  repository: string;
  repositoryRoot: string;
}
export interface LegacyAdapterResult {
  sourceId: string;
  adapter: string;
  adapterVersion: string;
  inputs: LegacyAdapterInput[];
  document: LegacyGraphDocument;
  diagnostics: LegacyAdapterDiagnostic[];
}
export interface LegacyMetamapAdapter<
  TConfig extends LegacyMetamapSourceConfig = LegacyMetamapSourceConfig,
> {
  readonly id: TConfig["adapter"];
  readonly version: string;
  fingerprint(
    config: TConfig,
    context: LegacyAdapterContext,
  ): Promise<LegacyAdapterInput[]>;
  discover(
    config: TConfig,
    context: LegacyAdapterContext,
  ): Promise<LegacyAdapterResult>;
}
export declare class LegacyAdapterRegistry {
  register<TConfig extends LegacyMetamapSourceConfig>(
    adapter: LegacyMetamapAdapter<TConfig>,
  ): this;
  get(id: string): LegacyMetamapAdapter<LegacyMetamapSourceConfig> | undefined;
  require(id: string): LegacyMetamapAdapter<LegacyMetamapSourceConfig>;
  ids(): string[];
}
export declare function createDefaultLegacyAdapterRegistry(): LegacyAdapterRegistry;
export declare function setLegacyDefaultAdapterRegistryFactory(
  factory: () => LegacyAdapterRegistry,
): void;
export interface LegacyMetamapSnapshot {
  schemaVersion: "1.0.0";
  graphId: string;
  graphRevision: string;
  graphDigest: string;
  configDigest: string;
  sources: Array<{
    id: string;
    adapter: string;
    adapterVersion: string;
    inputs: LegacyAdapterResult["inputs"];
  }>;
  counts: { entities: number; mappings: number; authorities: number };
}
export interface LegacyWorkspaceDiscovery {
  graph: LegacyGraphDocument;
  adapters: LegacyAdapterResult[];
  driftIssues: LegacyDriftIssue[];
  validation: LegacyValidationResult;
  snapshot: LegacyMetamapSnapshot;
  cacheHits: string[];
}
export interface LegacyWorkspaceCheck extends LegacyWorkspaceDiscovery {
  baseline?: LegacyGraphDocument;
  diff: LegacyGraphDiff;
  baselineSeverity: "error" | "warning" | "ignore";
}
export interface LegacyWorkspaceOptions {
  useCache?: boolean;
  writeCache?: boolean;
  portablePackUris?: boolean;
  adapterRegistry?: LegacyAdapterRegistry;
  relationRegistry?: LegacyRelationRegistry;
}
export interface LegacyConfiguredRelationPack {
  configuredPath: string;
  pack: LegacyRelationPack;
}
export declare function makeLegacyWorkspaceSnapshot(
  graph: LegacyGraphDocument,
  adapters: readonly LegacyAdapterResult[],
  configDigest: string,
): LegacyMetamapSnapshot;
export declare function assembleLegacyWorkspace(
  config: LegacyMetamapConfig,
  adapters: readonly LegacyAdapterResult[],
  configuredRelationPacks: readonly LegacyConfiguredRelationPack[],
  relationRegistry: LegacyRelationRegistry,
  options?: Pick<LegacyWorkspaceOptions, "portablePackUris">,
): LegacyWorkspaceDiscovery;
export declare function discoverLegacyWorkspace(
  loaded: LegacyLoadedMetamapConfig,
  options?: LegacyWorkspaceOptions,
): Promise<LegacyWorkspaceDiscovery>;
export declare function checkLegacyWorkspace(
  loaded: LegacyLoadedMetamapConfig,
  options?: LegacyWorkspaceOptions,
): Promise<LegacyWorkspaceCheck>;
export declare function writeLegacyWorkspaceOutputs(
  loaded: LegacyLoadedMetamapConfig,
  discovery: LegacyWorkspaceDiscovery,
): Promise<void>;
export declare function legacyWorkspaceHasErrors(
  discovery: LegacyWorkspaceDiscovery,
): boolean;
