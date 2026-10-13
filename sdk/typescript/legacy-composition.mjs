import { marshalLegacyGraphDocument } from "./legacy-graph.mjs";

export class LegacyCompositionError extends Error {
  constructor(message, identifier) {
    super(message);
    this.identifier = identifier;
    this.name = "MetamapCompositionError";
  }
}

/** @internal Rust owns merge/conflict/equivalence decisions. Host handles retain
 * first source objects and original arrays; composition supplies no admission. */
export function createLegacyComposer(invoke) {
  return function composeLegacyDocuments(documents, options) {
    const selectedOptions = Object.fromEntries(
      ["id", "namespace", "label", "revision"]
        .filter((field) => options[field] !== undefined)
        .map((field) => [field, options[field]]),
    );
    const report = invoke("compose", "json", {
      documents: documents.map((document) =>
        marshalLegacyGraphDocument(document),
      ),
      options: selectedOptions,
      locale: new Intl.Collator().resolvedOptions().locale,
    });
    const retained = (field) =>
      report[field].map(
        (handle) => documents[handle.document][field][handle.item],
      );
    const header = report.header;
    return {
      $schema: header.$schema,
      schemaVersion: header.schemaVersion,
      id: header.id,
      namespace: header.namespace,
      label: header.label,
      revision: header.revision,
      relationPacks: retained("relationPacks"),
      entities: retained("entities"),
      mappings: retained("mappings"),
      authorities: retained("authorities"),
      metadata: header.metadata,
    };
  };
}
