import { marshalLegacyObservationJson } from "./canonical.mjs";

/** @internal Rust owns comparisons, ordering, counts and rendered text. The
 * facade sends snapshots without mutating input objects or validating graphs. */
export function createLegacyReportingApi(invoke) {
  const call = (action) =>
    invoke("reporting", "json", {
      action,
      locale: new Intl.Collator().resolvedOptions().locale,
    });
  return {
    diffLegacyDocuments(before, after) {
      return call({
        operation: "diff",
        before: marshalLegacyObservationJson(before),
        after: marshalLegacyObservationJson(after),
      });
    },
    emptyLegacyGraphDiff() {
      return call({ operation: "empty-diff" });
    },
    renderLegacyDriftReport(input) {
      return call({
        operation: "drift-report",
        input: marshalLegacyObservationJson(input),
      });
    },
    renderLegacyGraphDocumentation(graph, correspondences) {
      return call({
        operation: "graph-documentation",
        graph: marshalLegacyObservationJson(graph),
        correspondences: marshalLegacyObservationJson(correspondences),
      });
    },
  };
}
