import { marshalLegacyObservationJson } from "./canonical.mjs";
/** @internal Rust owns schema, semantic and filesystem decisions. */
export function createLegacyConfigApi(invoke, loadFile) {
  return {
    LEGACY_METAMAP_CONFIG_VERSION: "1.0.0",
    parseLegacyMetamapConfig(value) {
      invoke("config", "json", { input: marshalLegacyObservationJson(value) });
      return value;
    },
    async loadLegacyMetamapConfig(path) {
      return await loadFile("config-file", null, path);
    },
  };
}
