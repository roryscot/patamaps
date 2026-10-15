# Cross-stack development fixture

This independent application is the first fixture for the 2026-10-15 cross-stack build plan. It is implementation scaffolding, not accepted cross-stack support. See support.json for pinned versions, scope and milestone state, and acceptance/expected.json for expectations frozen independently of discovery.

The intended path is the catalog page, its POST /api/items handler, operation urn:example:operation:create-item, Rust create_item handler, catalog-service Cargo target, Linux builder artifact, final runtime image and observed service. Dynamic page items/[id] is a separate route-discovery control. Request parsing, a health endpoint and a deliberate backend failure are real service behavior.

Native fixture commands (use the Intel storage supervisor):

    cargo test --manifest-path examples/cross-stack/service/Cargo.toml --locked
    cargo build --manifest-path examples/cross-stack/service/Cargo.toml --locked
    npm --prefix examples/cross-stack/web run build
    npm --prefix examples/cross-stack/web run typecheck

Run the service with its configuration path and an optional test-only listener override. Ordinary discovery must not execute project code. Compiling this fixture is an explicitly separate tool stage. The initial handwritten web/service connection will be replaced by checked generated registrations and clients in M2; it does not yet enforce the mapping contract.

Docker builds use this directory as context and deploy/Dockerfile with runtime as the selected stage. No local VM is required. Missing Docker blocks the image acceptance lane, whose build/inspection/runtime evidence will run on Linux CI. Runtime libraries, platform and resolved image digests must be checked there.

Candidates, logs and images are retained. Do not clean/prune dependencies, targets, containers, images or earlier test material without the owner's required exact-list approval. Production deployment and registry publication are outside this workflow.
