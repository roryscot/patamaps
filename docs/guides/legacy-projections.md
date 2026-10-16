# Original v1 projection compatibility

The TypeScript SDK exposes the original v1 projection parser, validator and compiler through the native Patamaps executable. This fills an API gap for existing generators that already consume v1 projection entries.

Use an explicitly configured factory:

```javascript
import { createLegacyValidationApi } from "patamaps-native-sdk-draft";
const api = createLegacyValidationApi("/absolute/path/to/patamaps");
const registry = new api.LegacyRelationRegistry();
registry.registerPack(routingPack);
const spec = api.parseLegacyProjectionSpec(specification);
const compilation = api.compileLegacyMetamap(document, policy, {
  relationRegistry: registry,
  evaluatedAt: "2026-09-02T00:00:00.000Z",
});
if (compilation.status !== "viable") throw new Error("Generation rejected");
const result = api.compileLegacyProjection(document, compilation.generation, spec, {
  relationRegistry: registry,
});
if (result.status !== "projected") throw new Error("Projection rejected");
consumeProjection(result.projection);
```

The module also exports `validateLegacyProjectionSpec`, `parseLegacyProjectionSpec`, `validateLegacyProjection`, `parseLegacyProjection`, `compileLegacyProjection`, `LEGACY_METAMAP_PROJECTION_SPEC_VERSION`, and `LEGACY_METAMAP_PROJECTION_VERSION`. The configured factory and lazy configured top-level API expose the same calls. The existing `LegacyMetamapProjectionSpec` type is reused; `LegacyProjectionSpec` is its alias. Shared slot, selection and cardinality types retain their existing declarations.

Rust checks graph and generation validity, graph identity and digest binding, active mappings, relation registration, subject selection, kind filters, lossiness and slot cardinality. It determines entry, slot, mapping and target ordering and computes the original v1 addresses. The SDK transports values, preserves parser object identity, restores numeric facts including signed zero, and freezes the returned projection. It does not compute projection semantics.

Generation and specification profiles must both be v1. A v2/executable projection is unsupported by this API; version mismatches, semantic policy inputs, executable packs and proof claims refuse. This compatibility record is a legacy observation: it does not create a native admitted generation or authorize activation. The existing native admitted-generation projection API remains separate.

Projection expansion has native resource guards. Conservative accounting before cloning bounds generated body size and values using the compatibility limits (16 MiB and 2,000,000 values). Incidence work is bounded, emitted numeric-fact metadata shares the final body budget, and output depth is bounded at 512. Resource refusals use the native diagnostic `LEGACY_PROJECTION_RESOURCE_LIMIT`; the SDK retains ordinary legacy Error behavior. These are native resource limits, not a claim that the original JavaScript compiler has equivalent guards.

The [frozen original corpus](../../fixtures/parity/projection-controls.json) and [differential runner](../../scripts/parity/projection_contracts.mjs) exercise records, diagnostics, addresses, ordering, immutable results, Unicode and signed zero. Rust regressions replay the frozen original observations and separately test excessive subject/slot expansion, repeated large target metadata and output depth. The [typed consumer](../../fixtures/parity/types/projection-client.mts) checks both factory and top-level exports.

This API checkpoint does not establish replacement of an application's existing generated contract. That requires running its real generator and consumers, binding the emitted replacement into the native build workflow, then qualifying runtime, installed use and deployment.
