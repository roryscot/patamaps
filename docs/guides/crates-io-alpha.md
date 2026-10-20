# crates.io alpha

Status: all ten candidate archives are built and Cargo-verified; clean installation is pending. No package has been uploaded. The experimental
Patamaps version is `0.1.0-alpha.1`; APIs and wire profiles remain draft.

## Packages and publication order

The dependency order is `patamaps-icu-collator` `2.2.1-patamaps.1`, then
`patamaps-contracts`, `patamaps-core`, `patamaps-projection`,
`patamaps-governance`, `patamaps-workspace`, `patamaps-scientific`,
`patamaps-inspect`, `patamaps-cli` and `patamaps-activator`, all at
`0.1.0-alpha.1`. The CLI package installs the `patamaps` executable.

The collation fork is independently named and retains Unicode-3.0 and upstream
attribution. It is not an official ICU4X release. Other Patamaps crates use
Apache-2.0; reference licenses and notices travel with their inputs.

## Self-contained inputs and identity

Crate-owned `package-inputs.tsv` records each bundled fixture/schema/configuration
copy and its repository origin. Run `python3 scripts/sync_crate_inputs.py` after
changing an authoritative input; `--check` refuses drift. Source-workspace build
scripts also refuse missing or stale copies. Those scripts work without the
repository when compiling unpacked registry packages. Original files remain.

The contracts and core libraries export exact source fragments for the compiler's
identity. The compiler hashes the actual dependency fragments rather than stale
copies of another crate's production code. Each dependency also supplies a
digest of the actual bundled input bytes, so changing its schema or fixture
changes its recorded identity even when a separate copy exists elsewhere. The fork exports a production-source
digest including its active manifest and build script. Cargo normalizes registry
manifests, so a packaged executor can differ from a source-workspace executor;
captures and approvals from another executor are not upgraded or reused.

Source identity is not binary authentication, reproducible native compilation,
or an attestation of a parent application's complete dependency graph. The frozen
workspace lockfile is a declared reference input, not the importing application's
lockfile.

## Installation after publication

Rust 1.99 or newer is required. These commands are prospective until upload:

```sh
cargo install patamaps-cli --version 0.1.0-alpha.1 --locked
cargo add 'patamaps-core@=0.1.0-alpha.1'
```

The [candidate inventory](../acceptance/crates-io/2026-10-19/candidate-inventory.json) records all ten archive/member hashes and dependency order from frozen source commit 3f54166f8ad4f2071c88de145e2b20ed38355502. The native Intel source checks and all four hosted Linux jobs passed; fresh installation is pending.
Before upload, a disclosed offline candidate-registry rehearsal must install the
exact `.crate` archives with a fresh Cargo home and consumer. That rehearsal does
not claim a public crates.io download, name ownership, verified publisher email,
or authenticated upload.

## Scope

The portable Rust compiler consumes explicit inputs and generates static
consumers without MetaMap or a graph compiler on their request paths. Optional
Node discovery providers and the Python watch controller remain separate source
tooling; this release does not publish an npm adapter or bundle that ecosystem.
Current existing-project qualification remains partial. Protected activation is
a separately qualified Linux-only profile; crate installation does not configure
trust or activate a consumer. Windows and performance claims require separate
evidence. The alpha's exact tested platform and limitations belong in its receipt.

Workspace metadata snapshots use workspace-manifest.toml and workspace.lock.
Cargo excludes any nested directory containing a file named Cargo.toml, even
when include patterns select it; these names keep the bundled inputs eligible.
See https://doc.rust-lang.org/cargo/reference/manifest.html#the-exclude-and-include-fields.

Before freezing publication inputs, prepare the standalone fork dependency closure with cargo fetch --manifest-path vendor/icu_collator/Cargo.toml through the existing Intel supervisor. Optional upstream dependencies may require a public registry download; root native checks remain locked and offline.
