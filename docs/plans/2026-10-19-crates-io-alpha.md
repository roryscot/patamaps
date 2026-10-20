# crates.io alpha preparation

Status: complete for preparation and the recorded installation acceptance.
Public crates.io upload remains pending and requires separate authorization.

## State and decisions

The branch is `release/crates-io-alpha`, based on
`60b898e2d433b49555c3928c35b3f4eb271e1f2f`.
Package payloads are frozen at `3f54166f8ad4f2071c88de145e2b20ed38355502`;
later commits contain operational verifier corrections and acceptance records.
The [release guide](../guides/crates-io-alpha.md) controls package order, versions,
retained Intel paths, reproduction and publication prerequisites.

Scope was the existing nine Rust crates at `0.1.0-alpha.1`, plus the independently
named `patamaps-icu-collator` `2.2.1-patamaps.1` fork. Original source records,
notices, tests and inputs remain preserved. This work excluded npm publication,
production installation, trust/bootstrap and consumer activation. Heavy local
work ran natively on Intel under the existing 4 GB growth, 500 MB reserve and
100 GB retention controls. Unrelated development checkout changes were preserved.

## Completed work

Crates carry explicit input inventories, build-time drift checks, local notices
and license files. All 256 literal Rust includes resolve within their owning
crate, all 94 declared data copies are present in Cargo file lists, and the
source audit binds all 79 production engine source files. Contracts and core
export actual dependency-owned source fragments. Per-crate input digests and
the named fork's production digest cover actual package bytes. The previously
missing legacy projection source binding is repaired.

The exact ten candidates total 3,070,893 compressed bytes. Cargo built and
verified each archive with locked offline dependencies. Name/version, license,
safe ordinary members, normalized dependencies, size and SHA-256 checks passed.
[The inventory](../acceptance/crates-io/2026-10-19/candidate-inventory.json)
retains archive and member hashes from the clean frozen checkout.

## Acceptance

| Requirement | Observed result |
| --- | --- |
| Crate-local sources, test includes and required data | 256 contained literal includes; 94 synchronized copies and no missing production source bindings |
| Dependency-owned identity | All four native and packaged executor identities independently matched their respective actual source inputs |
| Native source checks | Formatting, locked/offline check and Clippy passed; workspace run passed 336 tests; separate doc rerun passed 16 already-covered doc tests |
| Linux source checks | All four jobs passed at source 6d6f31d1bb5a1e64380491b7053a3e2d84f57fe0 |
| Cargo archives | Ten verified archives; largest 1,335,236 bytes; complete licenses and normalized dependency records |
| Fresh installation and controls | Fresh CLI install with source/network denied; exact-binary follow-up passed registry-only libraries, capture/replay, tamper refusal, module move and archive-checksum refusal |
| Release guide | Exact versions, order, hashes, retained state, prospective install commands, limits and pending public upload documented |

The [release readiness record](../acceptance/crates-io/2026-10-19/release-readiness.json)
indexes exact receipts and their digests. Raw stdout/stderr, state and artifacts
remain on Intel. The [Linux run](https://github.com/roryscot/patamaps/actions/runs/39341691837)
is successful source acceptance at its identified commit.

## Retained failures and repairs

The first preparation rejected a nested fork workspace. An explicit standalone
fork workspace fixed it. The first hosted run rejected source formatting; native
formatting fixed it before the successful second run. Cargo excluded a copied
nested Cargo.toml; byte-preserving renames to workspace-manifest.toml and
workspace.lock fixed the package file list.

All seven native verification commands passed in native-0001. Its terminal
comparison then rejected matching identities because it compared the CLI's full
executor-description envelope against only four digests. The corrected
native-0002 focused check passed the complete envelope, identities, source audit
and unchanged-source check. Rust production sources did not change between runs.

The standalone fork fetch refreshed its lockfile for the renamed package and
digest build dependency while retaining upstream versions. Three valid ICU
optional-feature graph differences showed why seeding must compare archive
identity/checksum separately from a lockfile's dependency graph. The corrected
seed verified all 255 upstream archives.

clean-0001 installed the exact CLI into an exclusively created fresh Cargo home
and target, matched archive identities and passed both generated-program cases.
It then refused the test consumer's unavailable serde_json=1.0.151 pin.
clean-0002 takes the frozen lockfile's actual 1.0.152 version. It verifies and
reuses only the retained installation bound to the same source, state, original
driver and installed binary digest. It repeats source-denial, identities and
runtime controls in new consumer directories, then passes library capture/replay,
forged-capture rejection, registry-only origins and an explicit corrupted-archive
checksum error. Its Cargo home is recorded as reused, not a second fresh home.
Both initial refusal and accepted follow-up remain intact.

## Limits and next independent task

Acceptance is the recorded offline candidate-registry rehearsal on macOS x86_64.
Source CI additionally covers Linux x86_64/aarch64 and the existing cross-stack
flows. Public registry ownership, verified publisher email, credentials, upload
and download were not verified or exercised. Optional Node/Python tooling,
Windows, performance and general project-adoption claims retain their prior
scope. Source digests do not authenticate binaries or attest a parent
application's full dependency graph; historical approvals are not upgraded.

The next task is a separately authorized public upload. Read the release guide
and exact inventory first. Preserve the frozen source and use the current
operational driver; confirm the intended crates.io account and credentials
privately on Intel, recheck the ten names, publish in dependency order, verify
public checksums and test a fresh public-registry installation. A bounded
publication task can use the fast Codex driver; any changed payload or failed
registry verification requires review before uploading a replacement candidate.
