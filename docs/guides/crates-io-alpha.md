# crates.io alpha

Status: prepared and verified on Intel; public upload remains pending.
The Rust libraries and CLI are `0.1.0-alpha.1`. APIs and wire profiles remain draft.

## Exact release candidate

Publication source is frozen at
`3f54166f8ad4f2071c88de145e2b20ed38355502`.
The [candidate inventory](../acceptance/crates-io/2026-10-19/candidate-inventory.json)
records the SHA-256, size, members and command receipt for every archive.
All ten archives passed `cargo package --locked --offline` with Cargo's default
build verification. Their combined compressed size is 3,070,893 bytes; the
largest is 1,335,236 bytes. Each is below the 10,000,000-byte preparation limit.

Publish in this dependency order:

| Order | Crate | Version |
| --- | --- | --- |
| 1 | patamaps-icu-collator | 2.2.1-patamaps.1 |
| 2 | patamaps-contracts | 0.1.0-alpha.1 |
| 3 | patamaps-core | 0.1.0-alpha.1 |
| 4 | patamaps-projection | 0.1.0-alpha.1 |
| 5 | patamaps-governance | 0.1.0-alpha.1 |
| 6 | patamaps-workspace | 0.1.0-alpha.1 |
| 7 | patamaps-scientific | 0.1.0-alpha.1 |
| 8 | patamaps-inspect | 0.1.0-alpha.1 |
| 9 | patamaps-cli | 0.1.0-alpha.1 |
| 10 | patamaps-activator | 0.1.0-alpha.1 |

The CLI package installs the `patamaps` executable. The independently named
collation fork retains Unicode-3.0, upstream attribution and the upstream
inventory. It is a Patamaps-maintained fork. Other Patamaps crates use
Apache-2.0; notices accompany reference inputs.

## Verification

The [release readiness record](../acceptance/crates-io/2026-10-19/release-readiness.json)
binds the candidate to these checks:

- Intel source: formatting, locked/offline all-target compilation and Clippy,
  336 passing tests in the workspace run, and 16 passing tests in the separate
  doc-test rerun. The workspace run already includes its doc tests.
- [Linux source CI](https://github.com/roryscot/patamaps/actions/runs/39341691837):
  all four jobs passed at `6d6f31d1bb5a1e64380491b7053a3e2d84f57fe0`,
  covering x86_64, aarch64, source bindings and Linux image/browser checks.
- Cargo built and verified every candidate archive; normalized dependencies,
  ordinary archive members, names, versions, licenses, sizes and hashes passed.
- A fresh Cargo home and target installed the CLI from the exact archives through
  an isolated offline candidate registry. A calibrated macOS sandbox denied
  reads from development checkouts and denied outbound networking.
- Installed engine identities matched independent calculations from unpacked
  archives. A new Rust consumer used all seven libraries and the named fork from
  registry sources, completed capture/replay and rejected a forged capture.
- Generated Rust programs returned `Hello, Ada!` before and after an actual
  module-file rename. The semantic ID stayed stable and the generated binding
  digest changed. Runtime controls denied reads of the selected Rust and graph
  compiler executables.
- A separate registry copy and fresh negative-control Cargo home refused a
  corrupted `patamaps-contracts` archive with an explicit checksum error.

The [initial clean record](../acceptance/crates-io/2026-10-19/clean-initial.json)
retains the successful fresh CLI install and generated-runtime checks, followed
by a refusal caused by the test consumer's incorrect `serde_json=1.0.151` pin.
The [accepted follow-up](../acceptance/crates-io/2026-10-19/clean-accepted.json)
uses the frozen lockfile's `1.0.152`, verifies and reuses that exact installed
binary, and repeats identity/runtime checks in new consumer directories before
the successful library and archive-corruption controls. Its Cargo home was
reused from the initial fresh installation; it does not claim a second fresh
installation. Both records and all raw outputs remain on Intel.

This rehearses unpublished names with explicit source replacement. It establishes
the recorded local installation result. Public crates.io upload, download,
publisher authorization and registry acceptance remain unverified.

## Self-contained inputs and identity

Crate-owned `package-inputs.tsv` inventories each bundled fixture/schema/configuration
copy and its repository origin. Run `python3 scripts/sync_crate_inputs.py` after
changing an authoritative input; `--check` refuses drift. Source-workspace build
scripts refuse missing or stale copies. Registry packages compile from their
bundled input bytes. Original inputs remain.

Contracts and core export source fragments from their actual owning dependencies.
Each crate binds its bundled input bytes into its source identity. The fork
exports a digest of its active manifest, build script and production source.
Cargo normalizes registry manifests, so the packaged executors have distinct
identities; historical captures and approvals keep their original scope.

Source identity is separate from binary authentication, reproducible native
compilation and a parent application's complete dependency graph. The bundled
workspace lockfile is a declared reference input, not the importing application's
lockfile. Metadata snapshots use `workspace-manifest.toml` and `workspace.lock`:
[Cargo excludes nested directories containing a file named Cargo.toml](https://doc.rust-lang.org/cargo/reference/manifest.html#the-exclude-and-include-fields).

## Retained Intel state and reproduction

The release branch is `release/crates-io-alpha`. Its working checkout is
`/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/crates-io/alpha-20261019/checkout`.
The frozen publishing checkout is its sibling `publishing-source-0001`.
Candidate archives are in
`/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/crates-io/alpha-20261019/candidate-0001/candidate-registry`.
The verified Intel executable is
`/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/crates-io/alpha-20261019/candidate-0001/installation/bin/patamaps`.

Use the current branch's `scripts/crates_alpha_package.py` as the driver and pass
the frozen checkout with `--source` and its exact commit with `--expected-source`.
The operational driver was corrected after freezing the package payload.
Run `seed`, `package` and `clean` stages with a new `--state` and unique
`--record` names through the existing Intel supervisor. The default clean stage
creates a fresh home, target and consumer for that record. The optional
`--reuse-install-record` requires the original successful installation, matching
source/state/driver and binary digests, and records the reused home explicitly.

Native toolchain and full source/bootstrap records remain under the existing
Intel development environment. Keep the frozen checkout and candidate archives.
Preparation preserved prior failures, logs and outputs and performed no direct
file deletion. The approved storage limits remain 4 GB growth per run, a 500 MB
reserve and a 100 GB retention cap.

## Public installation after upload

Rust 1.99 or newer is required. These commands become usable after publication:

```sh
cargo install patamaps-cli --version 0.1.0-alpha.1 --locked
cargo add 'patamaps-core@=0.1.0-alpha.1'
```

Before the separately authorized upload, confirm the intended crates.io owner,
verified email and private publishing credentials on Intel. Recheck name
availability: the retained public lookup returned HTTP 404 for all ten names and
does not reserve them. Use ordinary crates.io configuration for publishing;
the rehearsal Cargo homes contain local source-replacement settings.

Use the frozen source, publish the fork with
`--manifest-path vendor/icu_collator/Cargo.toml`, then the listed workspace crates
with `-p NAME`. Use `--locked` and wait for each dependency's public index entry.
Compare regenerated archive hashes with the inventory before uploading. Recheck
the published checksums and perform a new installation from public crates.io.
[Cargo's publishing guide](https://doc.rust-lang.org/cargo/reference/publishing.html)
describes the account and permanent-version boundary.

## Scope limits

The exact archive installation was verified on macOS x86_64. The Linux matrix
above verifies identified source builds; it is not a Linux registry-install
claim. Windows and performance claims require separate evidence. Existing-project
qualification remains partial.

Optional Node discovery providers and the Python watch controller remain separate
source tooling. This alpha does not publish an npm adapter or bundle that
ecosystem. Protected activation remains a separately qualified Linux profile;
package preparation and installation do not provision trust or activate consumers.
