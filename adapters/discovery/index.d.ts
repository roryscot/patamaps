export * from "./model.js";
export type * from "./config.js";
export type * from "./adapters/types.js";
export * from "./adapters/prisma.js";
export * from "./adapters/typescript-zod.js";
export * from "./adapters/nextjs-app-router.js";
export * from "./adapters/json-collections.js";
export * from "./adapters/legacy-sources.js";
export * from "./adapters/sssom-tsv.js";
export * from "./adapters/metamap-shard.js";
import type { SssomExecution } from "patamaps-native-sdk-draft/sssom";
export function configureDiscoveryNative(
  executable: string,
  observeExecution?: (execution: SssomExecution) => void,
): void;
export * from "./adapters/source-of-truth.js";

export {
  LegacyAdapterRegistry,
  createDefaultLegacyAdapterRegistry,
  discoverLegacyWorkspace,
  checkLegacyWorkspace,
  writeLegacyWorkspaceOutputs,
  assembleLegacyWorkspace,
  makeLegacyWorkspaceSnapshot,
  legacyWorkspaceHasErrors,
} from "patamaps-native-sdk-draft/legacy-validation";
export type {
  LegacyWorkspaceDiscovery,
  LegacyWorkspaceCheck,
  LegacyWorkspaceOptions,
  LegacyMetamapSnapshot,
} from "patamaps-native-sdk-draft/legacy-validation";
