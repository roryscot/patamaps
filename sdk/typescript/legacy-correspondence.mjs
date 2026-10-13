import { marshalLegacyObservationJson } from "./canonical.mjs";
/** @internal Rust owns all structure/field/enum/coverage decisions and IDs.
 * Native bindings restore caller array identities and own undefined fields. */
export function createLegacyCorrespondenceApi(invoke) {
  return {
    materializeLegacyCorrespondences(
      namespace,
      documentId,
      discovered,
      configurations,
      configRevision,
    ) {
      const response = invoke("correspondence", "json", {
        input: marshalLegacyObservationJson({
          namespace,
          documentId,
          discovered,
          configurations,
          configRevision,
        }),
      });
      const result = {
        issues: response.issues,
        configuredStructureIds: new Set(response.configuredStructureIds),
        document: response.document,
      };
      const at = (root, path) => path.reduce((value, key) => value[key], root);
      for (const entry of response.undefinedProperties) {
        const path = entry.path;
        const key = path.at(-1);
        const parent = at(result, path.slice(0, -2));
        const slot = path.at(-2);
        const properties = Object.entries(parent[slot]);
        properties.splice(entry.position, 0, [key, undefined]);
        parent[slot] = Object.fromEntries(properties);
      }
      for (const binding of response.bindings) {
        const target = at(result, binding.target.slice(0, -1));
        target[binding.target.at(-1)] = at({ configurations }, binding.source);
      }
      for (const field of ["entities", "mappings", "authorities"])
        for (const record of result.document[field])
          record.provenance = response.provenance;
      return result;
    },
  };
}
