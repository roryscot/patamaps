# Cross-stack development fixture

This independent application is the accepted first profile for the 2026-10-15 cross-stack build plan. [M0–M7 and all X01–X20 controls](../../docs/acceptance/cross-stack/release-profile-1/receipt.json) pass on the identified source and tools. The [support matrix](support.json) fixes the supported Next.js App Router, Rust/Cargo, HTTP-schema and Linux-image context. Application owners still declare operation meaning and deployment intent; adapters observe facts. Broader framework or feature/platform support requires its own controls.

The intended path is the catalog page, its POST /api/items handler, operation urn:example:operation:create-item, Rust create_item handler, catalog-service Cargo target, Linux builder artifact, final runtime image and observed service. Dynamic page items/[id] is a separate route-discovery control. Request parsing, a health endpoint and a deliberate backend failure are real service behavior.

Native fixture commands (use the Intel storage supervisor):

    cargo test --manifest-path examples/cross-stack/service/Cargo.toml --locked
    cargo build --manifest-path examples/cross-stack/service/Cargo.toml --locked
    npm --prefix examples/cross-stack/web run build
    npm --prefix examples/cross-stack/web run typecheck

Run the service with its configuration path and an optional test-only listener override. Ordinary discovery must not execute project code. Compiling this fixture is an explicitly separate tool stage. The service's normal router now calls service/src/generated.rs; the Next page and route import web/generated/operations.ts. Both are emitted by native checked projections. The explicit contracts/operations.json module map selects the handler's exact source bytes. Cargo checks the real function/types; independent HTTP checks cover Serde behavior. The supported JSON Schema subset is exact objects containing only required string fields with optional length constraints. Unknown required schema features refuse generation.

Docker builds use this directory as context and deploy/Dockerfile with runtime as the selected stage. No local VM is required. Missing Docker or Chromium blocks the required Linux image lane. The accepted CI run built the actual amd64 image, inspected its ELF, loader, config and license bytes, and exercised health, generated-client HTTP and browser form/navigation. Image IDs and tool observations belong to their exact run; upstream base tags do not promise deterministic rebuilds.

Candidates, logs and images are retained. Do not clean/prune dependencies, targets, containers, images or earlier test material without the owner's required exact-list approval. Production deployment and registry publication are outside this workflow.

Run the retained driver with --phase bindings from the repository through the supervisor for the 20-control M2 matrix. examples/cross-stack/build.py --compiler <native-cli> --candidate <fresh-directory> stages only a new consumer candidate and generates source; compiling/testing and selecting a ready set remain separate stages. Previously generated source and runtime application dependencies suffice to run the app without a graph compiler on request paths.

The [M2 receipt](../../docs/acceptance/cross-stack/m2-http-bindings/receipt.json) distinguishes Cargo/TypeScript refusals, successful compilation with rejected HTTP behavior, source integrity, and the previously retained candidate. Those historical M2 phase flags do not claim browser/image/publication acceptance; the aggregate release receipt adds the separately executed lanes. M0's historical empty-name response was invalid-name; generated schema validation now rejects it earlier as invalid-request, with independently frozen M2 expectations retained.

The native Docker observation matrix runs with --phase docker. The [M3 native receipt](../../docs/acceptance/cross-stack/m3-docker-observations/receipt.json) covers syntax, context and explicit unresolved findings. It records syntax/context scope only. The aggregate release separately includes the actual BuildKit stage/copy/ignore controls, compiled Linux artifact, inspected image bytes and observed runtime. Parser and upstream license notices are retained under docs/licenses in the repository.

The foreground preview/watch driver is verified on Intel and Linux. See
[its command and publication contract](../../docs/decisions/0030-retained-development-previews.md)
and the [M5 evidence](../../docs/acceptance/cross-stack/m5-development/receipt.json).
All 13 independent controls passed: real compiler failure, usable previous
selection, source races, watch reconciliation, concurrent readers and
cancellation. No-op means verification was not repeated. A selected preview is a
local verified generation; it does not activate production.

The [release evidence](../../docs/acceptance/cross-stack/release-profile-1/README.md)
separates native checks, source admission, Linux image/HTTP/browser observations,
MetaMap interoperability and installed-consumer execution. The required Linux CI
workflow runs source, development, image, compatibility and installed phases.
The image matrix includes 21 independent controls, with real failures for wrong
binary, missing config/loader, incompatible architecture, stale client and wrong
listener. Static EXPOSE alone never counts as a listener.

MetaMap compatibility uses the pinned original engine and an explicitly
registered observation-binding evaluator outside its unchanged reference tree.
It preserves original native bytes, records envelope changes and separate
MetaMap digests, and compares independently expected facts/decisions. Both
consumers share discovery facts, so agreement cannot independently validate the
provider. The moved-handler comparison also runs real Cargo after a physical
file move; its receipt distinguishes source facts from image observations.

Exact unpublished source/native packages passed separate installed-consumer
workspaces. The Linux installation reran the image/browser workflow, then both
native and Linux consumers ran after their test installation's compiler was
renamed to a retained unavailable path. Generated application request paths have
no Patamaps or MetaMap compiler dependency. All source bytes, candidates, logs,
images and archives remain retained. Registry publication, production
installation/trust and activation are separate work.
