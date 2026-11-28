# Patamaps legacy UTF-16 compatibility patch

This is ICU4X `icu_collator` 2.2.1 under its original Unicode-3.0 license.
`PATAMAPS-UPSTREAM.json` records the unchanged package's 29 file hashes and
registry archive checksum. The semantic patch changes `src/comparison.rs` and
`src/elements.rs`; the independent packaging changes are described below. Original notices and source test data are preserved.

ICU4X's documented `compare_utf16` replaces unpaired surrogates. MetaMap's pinned
Node 22 / ICU4C runtime retains their implicit code-point collation weights.
See the [upstream comparison API](https://docs.rs/icu_collator/2.2.1/icu_collator/struct.CollatorBorrowed.html#method.compare_utf16)
and [ICU4X design notes](https://github.com/unicode-org/icu4x/blob/5f61883417c361ecdfb24fb539465ed02b728639/components/collator/src/docs.rs).

The added `compare_legacy_utf16` method decodes input into scalar or unpaired-unit
tokens. An unpaired unit carries a separate tag through the existing element
iterator and normalization buffers, then uses the existing ICU4C-derived
implicit-weight formula with the original code point. Its internal starter
placeholder is a valid scalar; the tag distinguishes an actual U+F0000 input
from any unpaired unit. No invalid Rust `char` or new unsafe code is introduced.
Existing scalar APIs preserve their original replacement behavior. Patamaps
uses this extension only with the default tertiary comparison options and
compiled locale data; identical-strength/custom-provider behavior is outside
the extension's verified scope.

Frozen original observations cover 40 unchecked digests and 65 additional
UTF-16 contexts, including every unpaired unit, real placeholder scalars,
combining marks, ignorable characters, repeated units and pair boundaries.
These finite checks do not establish exhaustive collation-data/version or
locale equivalence. Full upstream tests and required Linux host acceptance
remain separate checks.

The original complete-workspace profile used `patamaps-contracts/build.rs` to
hash every vendored file and embed that digest in the compiler identity. The independent Python verifier reconstructs the digest
from actual source bytes. Those native release binaries include the patched code. The independent
registry profile below replaces the original same-name path dependency; it does
not reuse the upstream package identity or old executor approvals.

## Independently publishable fork

The registry name is `patamaps-icu-collator`, version `2.2.1-patamaps.1`.
This is a Patamaps-maintained fork, not an official ICU4X release. The original
Unicode-3.0 license, attribution, upstream inventory, manifest and test data remain.
In addition to the two comparison changes above, packaging changes the manifest,
adds `build.rs`, and exports its computed production-source digest from `lib.rs`.
The digest binds the actual active manifest, build script and every ordinary file
under `src/` and `data/`. It excludes registry cache metadata and is not binary
authentication. Cargo-normalized manifests give registry builds a distinct source
identity; old captures and approvals are not relabelled or reused.
