# patamaps-workspace

Part of [Patamaps](https://github.com/roryscot/patamaps), a Rust correspondence
compiler for independently owned systems. This is version `0.1.0-alpha.1`, an
experimental alpha with draft APIs and wire profiles. Its package inputs are
self-contained; generated consumers run without the graph compiler at runtime.

Rust 1.99 or newer is required. The CLI package is `patamaps-cli` and installs
the `patamaps` executable. Library entry points are documented by each crate.
Protected activation is a separately qualified Linux-only profile; installing
a crate does not provision trust, grant permissions or activate a consumer.

See the repository's `docs/guides/crates-io-alpha.md` for package order,
verification evidence, supported scope and release limitations. Source identity
records declared inputs; it does not authenticate a binary or attest a parent
application's complete dependency graph. No performance advantage is claimed.

License: Apache-2.0. Third-party attribution is retained in `NOTICE` and, where
needed, the packaged reference licenses. The collation fork retains Unicode-3.0.
