# patamaps-contracts

Portable draft records and strict JSON/canonicalization helpers used by
Patamaps. These records describe data; constructing or deserializing one does
not make it a checked graph or confer admission or authority.

Rust graph consumers can access the matching model types through
`patamaps_core::model` and validate with `CheckedGraph::check`. The default
`legacy-compat` feature supports legacy compatibility; it can be disabled when
only native contracts are needed. See the [Rust library guide](https://github.com/roryscot/patamaps/blob/feat/retained-owner-preparation/docs/guides/rust-library.md)
for usage and current verification limits.
