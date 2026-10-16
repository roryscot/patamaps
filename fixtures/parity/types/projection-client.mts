import {
  createLegacyValidationApi,
  compileLegacyProjection,
  parseLegacyProjectionSpec,
  type LegacyProjectionSpec,
  type LegacyGraphDocument,
  type LegacyViableGeneration,
  type LegacyProjection,
} from "../../../sdk/typescript/index.js";
declare const graph: LegacyGraphDocument;
declare const generation: LegacyViableGeneration;
const spec: LegacyProjectionSpec = {
  schemaVersion: "1.0.0",
  id: "urn:test:typed-projection",
  select: { kinds: ["test:item"] },
  slots: [],
};
const parsed: LegacyProjectionSpec = parseLegacyProjectionSpec(spec);
const api = createLegacyValidationApi("/native/patamaps");
api.validateLegacyProjectionSpec(parsed);
api.parseLegacyProjectionSpec(parsed);
const result = api.compileLegacyProjection(graph, generation, parsed);
if (result.status === "projected") {
  const record: LegacyProjection = result.projection;
  const digest: string = record.generation.digest;
  api.validateLegacyProjection(record);
  api.parseLegacyProjection(record);
}
compileLegacyProjection(graph, generation, parsed);
const invalid: LegacyProjectionSpec = {
  schemaVersion: "1.0.0",
  id: "urn:test:bad",
  select: { kinds: ["test:item"] },
  slots: [
    {
      name: "x",
      relation: "core:contains",
      direction: "outgoing",
      // @ts-expect-error v1 slot cardinalities are explicit
      cardinality: "all",
    },
  ],
};
