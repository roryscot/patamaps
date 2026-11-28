# patamaps-core

An in-process Rust library for explicit semantic identities and their typed
correspondences. Create draft records, provide relation definitions and
provenance, then use `CheckedGraph::check` before querying the graph. Checked
state is distinct from policy admission or authorization.

The default `legacy-compat` feature retains existing compatibility APIs. Set
`default-features = false` for the native graph API without that layer; Cargo
may unify features requested by other dependencies. The included
`examples/in_memory_graph.rs` demonstrates construction, validation, lookup,
and traversal without a CLI or service.

See the [Rust library guide](https://github.com/roryscot/patamaps/blob/feat/retained-owner-preparation/docs/guides/rust-library.md)
for source dependencies, usage, and verification limits. The API in a released
version may differ from the repository branch.
