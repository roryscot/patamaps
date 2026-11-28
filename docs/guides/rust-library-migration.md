# Move a Rust consumer from the published alpha to the library snapshot

This guide covers `patamaps-core` and `patamaps-contracts`, not the optional
CLI, generated bindings, or an automatic migration of persisted data. The
published `0.1.0-alpha.1` core/contracts and the current `0.1.0` Git snapshot
are different versions. The snapshot is not a crates.io release. Pinning a Git
revision provides reproducible source selection, not a stability guarantee.

## Choose a dependency source

For a consumer that needs the existing legacy APIs, keep the default features
when moving both crates to the same tested revision:

```toml
[dependencies]
patamaps-core = { git = "https://github.com/roryscot/patamaps.git", rev = "40a0ef969af41b7b17938c8083b20ee0a48f5421" }
patamaps-contracts = { git = "https://github.com/roryscot/patamaps.git", rev = "40a0ef969af41b7b17938c8083b20ee0a48f5421" }
```

If the consumer only uses the native in-memory graph, it can use just
`patamaps-core` with `default-features = false` as shown in the
[Rust library guide](rust-library.md). Its model types are available as
`patamaps_core::model`. Disabling defaults removes legacy compatibility APIs;
Cargo can enable that feature again through feature unification if another
dependency requests it.

Avoid passing graph records between a registry-sourced alpha dependency and a
Git-sourced snapshot as if they were the same Rust types. Cargo can resolve
both sources in one dependency graph, but types from distinct crate instances
are distinct. Align direct core and contracts dependencies on the same source
and revision, inspect `cargo tree -d`, and commit an application's resulting
`Cargo.lock`. Other dependencies may still bring their own alpha version.

## Adapt and verify your consumer

1. Keep the old lockfile and graph inputs available for comparison. Switch the
   direct dependencies together, then compile and run your project's existing
   tests. Use your host's resource supervisor for builds where configured.
2. Existing checked-graph operations include `CheckedGraph::check`, lookup and
   traversal. The snapshot also provides draft constructors, the
   `patamaps_core::model` re-export, `try_edit`, and indexed relation lookup.
   See the [complete consumer](../../examples/rust-library-consumer/src/main.rs).
3. Treat constructor results as **unchecked drafts**. Supply explicit relation
   definitions and provenance, call `CheckedGraph::check`, and handle its
   issues before using checked results. `try_edit` clones and rechecks; the
   original checked graph remains intact if validation fails.
4. Exercise real inputs, error handling, and any serialized documents your
   application depends on. Keep stable identities and provenance explicit;
   verify digest, wire, policy and downstream behavior against your own prior
   data before replacing it. This guide does not establish universal wire or
   semantic compatibility between the alpha and the snapshot.

The retained alpha source has the same model record declarations as the
snapshot inspected for this guide; the snapshot adds draft constructors.
That source comparison is narrower than a complete compatibility proof. The
snapshot's native-only consumer and a scoped Rust desktop integration have been
built and tested, but the UI and every existing consumer have not been tested.
The [library guide](rust-library.md) records the relevant test and footprint
limits. No crate publication or automatic data conversion is implied.

A [limited Norway comparison](../acceptance/library/alpha-wire-compat-20261127.json)
passed on three graph fixtures, one relation pack, and three strict rejection
cases using the retained alpha source and current native-only contracts. It
does not replace application-specific migration checks.
