# Cross-stack development fixture

This independent application is the first fixture for the 2026-10-15 cross-stack build plan. M0's native application, M1's bounded Cargo/TOML observations and M2's generated HTTP boundary are verified for their declared scopes. Full cross-stack support remains under development. See support.json for pinned versions, scope and milestone state, and acceptance/expected.json for expectations frozen independently of discovery.

The intended path is the catalog page, its POST /api/items handler, operation urn:example:operation:create-item, Rust create_item handler, catalog-service Cargo target, Linux builder artifact, final runtime image and observed service. Dynamic page items/[id] is a separate route-discovery control. Request parsing, a health endpoint and a deliberate backend failure are real service behavior.

Native fixture commands (use the Intel storage supervisor):

    cargo test --manifest-path examples/cross-stack/service/Cargo.toml --locked
    cargo build --manifest-path examples/cross-stack/service/Cargo.toml --locked
    npm --prefix examples/cross-stack/web run build
    npm --prefix examples/cross-stack/web run typecheck

Run the service with its configuration path and an optional test-only listener override. Ordinary discovery must not execute project code. Compiling this fixture is an explicitly separate tool stage. The service's normal router now calls service/src/generated.rs; the Next page and route import web/generated/operations.ts. Both are emitted by native checked projections. The explicit contracts/operations.json module map selects the handler's exact source bytes. Cargo checks the real function/types; independent HTTP checks cover Serde behavior. The supported JSON Schema subset is exact objects containing only required string fields with optional length constraints. Unknown required schema features refuse generation.

Docker builds use this directory as context and deploy/Dockerfile with runtime as the selected stage. No local VM is required. Missing Docker blocks the image acceptance lane, whose build/inspection/runtime evidence will run on Linux CI. Runtime libraries, platform and resolved image digests must be checked there.

Candidates, logs and images are retained. Do not clean/prune dependencies, targets, containers, images or earlier test material without the owner's required exact-list approval. Production deployment and registry publication are outside this workflow.

Run the retained driver with --phase bindings from the repository through the supervisor for the 20-control M2 matrix. examples/cross-stack/build.py --compiler <native-cli> --candidate <fresh-directory> stages only a new consumer candidate and generates source; compiling/testing and selecting a ready set remain separate stages. Previously generated source and runtime application dependencies suffice to run the app without a graph compiler on request paths.

The [M2 receipt](../../docs/acceptance/cross-stack/m2-http-bindings/receipt.json) distinguishes Cargo/TypeScript refusals, successful compilation with rejected HTTP behavior, source integrity, and the previously retained candidate. Its browser, image, whole-chain and atomic publication lanes remain unaccepted. M0's historical empty-name response was invalid-name; generated schema validation now rejects it earlier as invalid-request, with independently frozen M2 expectations retained.

The native Docker observation matrix runs with --phase docker. The [M3 native receipt](../../docs/acceptance/cross-stack/m3-docker-observations/receipt.json) covers syntax, context and explicit unresolved findings. It is not full M3/BuildKit, artifact or image acceptance; those required Linux lanes remain pending. Parser and upstream license notices are retained under docs/licenses in the repository.

The foreground preview/watch driver is now implemented. See
[its usage and publication contract](../../docs/decisions/0030-retained-development-previews.md)
and the [M5 receipt](../../docs/acceptance/cross-stack/m5-development/receipt.json).
All 13 independent development controls passed on Linux at the receipt's exact
commit, including real compiler failure, usable previous selection, source races,
watch reconciliation, concurrent readers and cancellation. Native Intel checks
are still queued behind the existing shared build lease. The required Linux
image/browser lane is implemented and under verification; full release and
MetaMap/installed-consumer acceptance remain pending.
