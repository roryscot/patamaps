# crates.io alpha publication

Status: eight of ten crates publicly verified on native Intel (`norway.local`).

The user authorized public crates.io publication of the prepared alpha. The
[release guide](../guides/crates-io-alpha.md) controls names, versions, dependency
order, immutable source and preparation evidence. The publishing checkout remains
clean at `3f54166f8ad4f2071c88de145e2b20ed38355502`.

Scope is all ten prepared archives: nine Patamaps crates at `0.1.0-alpha.1` and
`patamaps-icu-collator` at `2.2.1-patamaps.1`. The intended publisher is `roryscot`.
Cargo credentials are entered privately on Intel. Tokens never belong in source,
receipts, command arguments or chat. The existing Intel supervisor retains the
approved 4 GB growth limit, 500 MB reserve and 100 GB retention cap.

Acceptance requires each regenerated archive to match its prepared SHA-256 before
upload, followed by matching public index/API checksums, actual publisher, owner
and downloaded archive bytes. Versions already present may only be reused when
those checks agree. A failed upload requires inspection of public state before
retrying, because the registry may have accepted the upload.

Once the CLI and its dependencies are published, create an empty Cargo home, fresh target and installation
root with ordinary crates.io resolution. Install the CLI using the release
profile and locked dependencies while development-source reads are denied.
Independently recompute executor identities from the downloaded public archives.
Reuse the accepted generated-Rust module-move checks and typed library
capture/replay plus forged-capture refusal. Confirm all seven libraries and the
fork resolve to public registry sources without path overrides or source
replacement. Runtime checks continue to deny outbound networking and selected
compiler reads; registry download steps allow network access.

The publication and public-install drivers retain command arguments, exit codes,
stdout/stderr, source and driver digests, downloaded archives and receipts under
`.tools/crates-io/alpha-20261019/publication-20261021/`. Summarized evidence and
reproduction drivers belong on `release/crates-io-alpha`, with normal Rory commits
and pushes. Preparation evidence stays intact. This task performs no file
deletion or consumer activation.

Public installation acceptance is separate from the existing offline candidate
rehearsal. It does not extend Linux source CI into a Linux registry-install claim
or establish Windows, performance, optional Node/Python integration or general
project-adoption claims.

The [publication checkpoint](../acceptance/crates-io/2026-10-21/publication-progress.json)
preserves eight verified public archives, the initial rate-limit refusal, measured
headroom and accepted smaller-budget admission. The final two uploads
continue under the quota. CLI verification can overlap the independent final
activator upload; all ten public versions and the installation receipt remain
required. Source, replay, tamper and module-move criteria are unchanged.
