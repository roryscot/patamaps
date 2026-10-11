# Static scientific lookup consumer

This independent Rust workspace has no Patamaps dependency at runtime. It
compiles the verified crate's generated Rust bindings, graph and projection into
one lookup executable. `scripts/test_scientific.py` creates those generated files
in a disposable installed consumer and compares every result with the unchanged
pinned MetaMap `lookup.mjs`, through an explicit adapter for the new target table.

The seven licensed MGI assertions retain their IDs, provenance, complementary
metadata, duplicate-pair distinctions and five relation types. Lookup success
does not establish biological identity: the producer description explicitly
ignores the species restriction, confidence remains metadata, and the consumer
authors its exploratory policy and ordinal budget separately.

Generated `src/bindings.rs`, `src/graph.json` and `src/projection.json` are supplied
by the checked scientific package during installation. They are deliberately
absent from this source template. No approval or production activation occurs.
