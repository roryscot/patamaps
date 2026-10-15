# 0032 — Explicit MetaMap cross-stack compatibility

The consumer bridge in adapters/discovery/metamap-cross-stack.mjs converts only
the declared fixture profile. Native graph 0.1 becomes MetaMap graph 2.0; the
legacy structural policy and relation packs become their original MetaMap 1.0
contracts. Native JSON validation and a canonical round-trip check precede host
unmarshalling. Unsupported values or schema fields refuse conversion.

Every original input byte stream is retained. Each converted stream records
its own digest and every changed JSON pointer. Graph revision, policy graph
binding, and relation-pack content bindings are created for the converted
documents. Native captures, generations, approvals and their digests are never
substituted for MetaMap records. Materialized capture values identify their
original baseline bytes and JSON pointers.

The pinned reference remains at commit
399747a4ad05a37cd8db1cedd53048fad2175be4. Tests copy its tracked source into a
separate retained runtime, install its exact lockfile and compile there. Reference
tracked-file hashes are checked before and after. The original MetaMap shard
adapter imports converted facts, and the real compiler executes its ordinary
routing/topology constraints plus a registered observation-binding evaluator.
The evaluator uses the same complete active-binding comparison, missing/null
distinction and fixed selector/work bounds as the native profile. An absent
evaluator and attempted waiver must refuse acceptance.

The corpus compares independently expected facts and decisions, never compiler
hashes or incidental exception text. It includes an actual moved handler with
fresh native generation/Cargo tests, missing artifact evidence, ambiguous
operation binding, numeric equivalence, missing versus null and selector bounds.
Malformed TOML produces a real unavailable source record; MetaMap must reject
that non-graph. This shared provider failure is not an independent TOML-parser
comparison, and common discovery bugs remain possible.

Source-only compatibility is named separately from compatibility including real
M6 image/browser observations. Installed-package and final release acceptance
remain required separate gates. Implementation of the corpus is not evidence
that its commands have passed.
