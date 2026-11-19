# Standalone Rust library consumer

This separate Cargo workspace depends only on the local patamaps-core crate.
It constructs, checks, queries and safely edits a graph in memory.

From the repository root:

```sh
cargo run --locked --manifest-path examples/rust-library-consumer/Cargo.toml
```

This example uses the checkout through a path dependency, not a published
crate version. No Patamaps CLI, generated source, Node or app is involved.
