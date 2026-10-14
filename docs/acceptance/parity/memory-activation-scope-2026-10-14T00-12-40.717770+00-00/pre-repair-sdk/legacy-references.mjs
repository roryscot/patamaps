import { marshalLegacyObservationJson } from "./canonical.mjs";
/** @internal Identifier, path and percent-encoding decisions belong to Rust. */
export function createLegacyReferenceApi(invoke) {
  const call = (operation, input) =>
    invoke("references", "json", {
      operation,
      input: marshalLegacyObservationJson(input),
    });
  return {
    isLegacyReferenceIdentifier(value) {
      return call("reference-identifier", {
        value: typeof value === "string" ? value : null,
      });
    },
    isLegacyRelationIdentifier(value) {
      return call("relation-identifier", {
        value: typeof value === "string" ? value : null,
      });
    },
    makeLegacyUrn(namespace, kind, value) {
      return call("urn", { namespace, kind, value });
    },
    makeLegacyRepositoryUri(path, repository = "workspace") {
      return call("repository-uri", { path, repository });
    },
    hasLegacyAmbiguousPathLanguage(path) {
      return call("ambiguous-path", { path });
    },
    isLegacyPathPattern(path) {
      return call("path-pattern", { path });
    },
  };
}
