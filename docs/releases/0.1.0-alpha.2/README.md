# Patamaps 0.1.0-alpha.2

Release packages: patamaps-workspace and patamaps-cli, plus patamaps-inspect solely because its exact workspace dependency pin must advance. Other Patamaps dependencies stay at 0.1.0-alpha.1; the collator stays at 2.2.1-patamaps.1.

This release adds explicit lockless Cargo observations, bounded retained attempts, selected-command artifact checks, closed-tree output validation, captured executable-mode corrections, snapshot-backed Docker contexts and digest-bound ELF target inspection. Existing optional Next adapter corrections are included; further Next integration is outside this release.

[CI 40117789049](https://github.com/roryscot/patamaps/actions/runs/40117789049) passed workspace library tests, Cargo package verification, a fresh Cargo-home/target installation from a local registry containing the exact candidate archives, CLI validation/generation and a compiled generated Rust consumer. The install rehearsal used a debug build on Linux x86_64; it does not establish native macOS or ARM acceptance. The first attempt exposed the required inspect pin update. Intel's initial guarded run refused before Cargo because retention headroom was insufficient.

preflight.json records exact archive hashes. Workspace engine identities change with source and package inputs; old captures do not automatically gain current-engine verification. ELF inspection establishes bounded header/target checks, not general runtime compatibility.
