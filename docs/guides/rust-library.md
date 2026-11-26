# Use Patamaps in a Rust program

This is the first library-first example. The focused tests, in-memory example and standalone path-dependent consumer passed Linux CI at source 760378b. Two earlier Norway runs stopped under the shared-disk guard. A later native-only focused run passed four tests on Norway on 2026-11-25; the earlier failures remain recorded. It uses the
existing graph model and checked kernel directly; it does not execute the CLI,
read a graph file, generate code, or start an application.

From this checkout, run the example and its focused tests:

```sh
cargo run --locked -p patamaps-core --example in_memory_graph
cargo test --locked -p patamaps-core --test in_memory_library
```

On a shared development host, run these through that host's configured
resource supervisor. The example is part of the checkout; do not assume it is
already present in a published crate version.

For indexed relation lookup, `graph.mappings_for_relation(id)` borrows matching
mappings in the document's order; unknown or unused relations yield no items.

The example creates a draft GraphDocument, entities, an explicit relation
definition and a mapping with explicit cardinality, lossiness and provenance.
It calls CheckedGraph::check before using indexed lookup and trace. Draft
constructors do not validate identifiers, infer authority, or confer admission.
CheckedGraph is an immutable checked view. Its try_edit method clones the
draft, applies a caller-provided change and checks it with the same relation
packs, leaving the original graph unchanged if the edit is invalid. This is a
full clone and recheck, not an incremental update. Admission and policy
evaluation are separate.

Rust consumers can depend on patamaps-core and access draft records through
patamaps_core::model. Projection, code generation, CLI commands, application
builds and framework integrations are separate workflows, not required to run
this in-memory example. The library still has its own Rust dependencies; their
compile footprint has not yet been measured.

The [Rust-first plan](../plans/rust-first-data-structure.md) tracks the remaining
API, packaging and external-consumer work. See the example source for the
complete code and the core tests for invalid-input behavior.

A separate Cargo workspace is available at
[examples/rust-library-consumer](../../examples/rust-library-consumer/README.md).
It uses a path dependency on this checkout and demonstrates checked editing
without the CLI. Its native-only Linux CI check passed at source e4ccd68. It also passed on
Norway on 2026-11-25. These path-dependency checks do not verify a published
package.

## Optional legacy compatibility

The core crate enables its legacy-compat feature by default to preserve existing
consumers. A consumer that needs only the native graph API can set
`default-features = false` on patamaps-core, as the standalone consumer does.
Legacy APIs and legacy registry import methods are unavailable in that mode;
ordinary native registry and checked graph operations remain intended to work.
Cargo can unify features if another dependency enables legacy compatibility.
The feature split passed focused Linux CI at source e4ccd68 and is not yet a
published release. The four native-only focused tests also passed on Norway;
that local result does not verify a published package.
