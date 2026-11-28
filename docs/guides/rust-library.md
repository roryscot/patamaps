# Use Patamaps in a Rust program

Use the existing graph model and checked kernel directly in your Rust program.
The example does not execute the CLI, read a graph file, generate code, or start
an application. Five native-only focused tests and the standalone path consumer
passed on Norway; earlier interrupted runs remain recorded in the
[Rust-first plan](../plans/rust-first-data-structure.md).

## Add the library to a project

The current `0.1.0` core and contracts crates are not published. To use the
verified native-only API without a local Patamaps checkout, pin the tested Git
revision in your project's `Cargo.toml`:

```toml
[dependencies]
patamaps-core = { git = "https://github.com/roryscot/patamaps.git", rev = "5d1b594153337966220ce14d929812614c687459", default-features = false }
```

Use Rust 1.99 or newer and commit your application's `Cargo.lock` to retain the
resolved dependencies. Cargo needs network access for the first fetch; checking
and querying an in-memory graph do not need network access. A fresh Intel macOS
CI build compiled this pinned dependency in a Rust desktop application and ran
two integration-module tests. The application UI was not exercised, and a
separate fetch on Norway was interrupted by its storage guard. A Git revision
is a source snapshot, not a published release or stability guarantee.

Alternatively, for a local checkout, add a path dependency to your project's `Cargo.toml`.
Adjust the path so it points to `crates/patamaps-core` in your Patamaps
checkout; Cargo resolves it relative to the manifest containing this entry:

```toml
[dependencies]
patamaps-core = { path = "../patamaps/crates/patamaps-core", default-features = false }
```

This checkout requires Rust 1.99 or newer. The path uses the checkout's source,
so its API follows that checkout; pin the checkout revision for repeatable
builds. The example disables legacy compatibility for this dependency. Cargo
feature unification can still enable it if another dependency requests it.

Start with the complete
[standalone consumer](../../examples/rust-library-consumer/src/main.rs): it
creates two entities and a mapping, declares the relation and provenance,
checks the graph, queries it, and makes a checked edit. Copy and adapt those
records to your project's explicit domain; draft records become a
`CheckedGraph` only after validation succeeds. No service or CLI is required.

Do not replace these dependencies with a registry version expecting the current
API until an appropriate version is published.
Linux CI at source `5612baf` built fresh archives of both crates and ran default
and native-only consumers against the extracted packages, with the extracted
contracts crate supplied through a Cargo patch. It also ran focused core and
contracts tests from those archives. This checks package contents; it does not
verify a registry release. The initial Norway test of the packaged candidate
was refused by the storage guard; later checkout tests passed on Norway.

## Run the checkout examples

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

## Queries, errors and limits

`entity`, `mapping`, and `relation` return borrowed records, or `None` when the
identity is not present. `incident(entity_id)` borrows mappings in document
order, with each mapping returned once even if that entity occurs on both sides;
an unknown identity yields an empty iterator. The returned references cannot
outlive the checked graph. `document()` and `packs()` also expose borrowed,
immutable data. Iterate the document's vectors when you need all records in
their stored order.

`trace` includes an existing starting entity at depth zero; an unknown start
returns an empty result. The depth limit is 64 and a higher value produces a
`CheckError`. An empty relation filter allows every relation. Validation
returns `CheckError`, whose issues have codes and optional subject identities;
inspect those fields instead of relying on the displayed error sentence.

The current checked-graph profile allows up to 200,000 entities, 100,000
mappings, 1,024 authorities, 1,000,000 total source and target endpoint
occurrences, 64 relation packs, and 4,096 relations across packs. An authority
may list at most 128 facts. Metadata has separate structural limits, and other
validation rules may reject a graph below these counts. If diagnostics exceed
1,000, the list is truncated and includes a `DIAGNOSTIC_LIMIT` error; the
graph remains rejected. These are current profile bounds, not performance
promises or a guarantee that a graph near the bounds fits available memory.

## Optional legacy compatibility

The core crate enables its legacy-compat feature by default to preserve existing
consumers. A consumer that needs only the native graph API can set
`default-features = false` on patamaps-core, as the standalone consumer does.
Legacy APIs and legacy registry import methods are unavailable in that mode;
ordinary native registry and checked graph operations remain intended to work.
Cargo can unify features if another dependency enables legacy compatibility.
The feature split passed focused Linux CI at source e4ccd68 and is not yet a
published release. The five native-only focused tests and standalone consumer passed on Norway;
that local result does not verify a published package.
