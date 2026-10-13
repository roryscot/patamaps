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
  configureCanonical(executable, observeExecution);
  configureSssom(executable, observeExecution);
}
export {
  adaptLegacySourcesOfTruth,
  isLegacySourceOfTruthDocument,
} from "./adapters/source-of-truth.js";
