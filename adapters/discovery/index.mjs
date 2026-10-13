import {
  LegacyAdapterRegistry,
  configureLegacyValidation,
  setLegacyDefaultAdapterRegistryFactory,
} from "patamaps-native-sdk-draft/legacy-validation";
import { PrismaAdapter } from "./adapters/prisma.js";
import { TypeScriptZodAdapter } from "./adapters/typescript-zod.js";
import { NextjsAppRouterAdapter } from "./adapters/nextjs-app-router.js";
import { JsonCollectionsAdapter } from "./adapters/json-collections.js";
import { LegacySourcesAdapter } from "./adapters/legacy-sources.js";
import { SssomTsvAdapter } from "./adapters/sssom-tsv.js";
import { MetamapShardAdapter } from "./adapters/metamap-shard.js";
export function createDefaultLegacyAdapterRegistry(
  Registry = LegacyAdapterRegistry,
) {
  return new Registry()
    .register(new PrismaAdapter())
    .register(new TypeScriptZodAdapter())
    .register(new LegacySourcesAdapter())
    .register(new JsonCollectionsAdapter())
    .register(new MetamapShardAdapter())
    .register(new SssomTsvAdapter())
    .register(new NextjsAppRouterAdapter());
}
setLegacyDefaultAdapterRegistryFactory(createDefaultLegacyAdapterRegistry);
export {
  LegacyAdapterRegistry,
  discoverLegacyWorkspace,
  checkLegacyWorkspace,
  writeLegacyWorkspaceOutputs,
  assembleLegacyWorkspace,
  makeLegacyWorkspaceSnapshot,
  legacyWorkspaceHasErrors,
} from "patamaps-native-sdk-draft/legacy-validation";
export * from "./model.js";
export { PrismaAdapter } from "./adapters/prisma.js";
export { TypeScriptZodAdapter } from "./adapters/typescript-zod.js";
export {
  NextjsAppRouterAdapter,
  nextjsAppRouterAdapterVersion,
} from "./adapters/nextjs-app-router.js";
export { JsonCollectionsAdapter } from "./adapters/json-collections.js";
export { LegacySourcesAdapter } from "./adapters/legacy-sources.js";
export { SssomTsvAdapter } from "./adapters/sssom-tsv.js";
export { MetamapShardAdapter } from "./adapters/metamap-shard.js";
import { configureCanonical } from "patamaps-native-sdk-draft/canonical";
import { configureSssom } from "patamaps-native-sdk-draft/sssom";

/** Bind optional scientific facts to an explicitly selected native engine. */
export function configureDiscoveryNative(executable, observeExecution) {
  configureLegacyValidation(executable, observeExecution);
  configureCanonical(executable, observeExecution);
  configureSssom(executable, observeExecution);
}
export {
  adaptLegacySourcesOfTruth,
  isLegacySourceOfTruthDocument,
} from "./adapters/source-of-truth.js";
