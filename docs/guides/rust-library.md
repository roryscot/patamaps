# Use Patamaps in a Rust program

This is the first library-first example, under development and not yet compiled or tested: the first guarded run was refused before compilation for insufficient retained-storage headroom. It uses the
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
