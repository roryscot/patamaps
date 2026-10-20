# crates.io alpha preparation

Status: active; preparation only. Owner requested Intel implementation, a clean
installation, an alpha candidate, and regular verified commits/pushes. Public
registry upload is a separate final action. Baseline: 60b898e2d433b49555c3928c35b3f4eb271e1f2f.

## Scope

Prepare the existing nine Rust crates at 0.1.0-alpha.1 and the explicitly named
patamaps-icu-collator 2.2.1-patamaps.1 fork. Preserve the UTF-16 patch, original
notices and source records. Use an isolated Intel release worktree and existing
4 GB growth, 500 MB reserve and 100 GB retention controls. Preserve unrelated
qualification work and all original inputs; delete nothing. No npm publication,
production installation, trust provisioning or consumer activation.

## Acceptance

1. Every shipped Rust source, test and required data include resolves within its
   own crate. Copies have an explicit origin inventory, a refresh/check command,
   and source-workspace build checks for stale inputs. Original files remain.
2. Source identity fragments come from the actual owning dependency crate, not
   copied production source. The packaged collation fork exports a digest of its
   actual production inputs. Existing captures/approvals remain historical;
   Cargo-normalized registry manifests can produce distinct executor identities.
3. Locked offline native formatting, Clippy and meaningful workspace/collation
   regressions pass. Independently recomputed engine identities match binaries.
4. Cargo creates and verifies all candidate .crate archives in dependency order.
   All archive names, versions, licenses, members, sizes and SHA-256 values are
   recorded. Path-only dependencies and external includes refuse. Every crate
   remains below the registry size limit. No upload credentials are required.
5. A fresh Cargo home, target and consumer install/use the exact archives through
   an explicitly isolated offline candidate registry rehearsal. No development
   path patches or symlinks supply own source. A source-unavailable control,
   tampered-archive refusal, CLI execution, library use, capture/replay and generated
   Rust consumer establish the scoped clean-install result. This is not a public
   registry download or a new platform claim.
6. An alpha release guide identifies crate order, exact versions/archives,
   installation commands, known draft/support limits, and pending public upload.
   Verify Rory identity, destination and new commit metadata before every push.

## Sequence

Commit this plan, then self-contained inputs/fork/source-identity changes and
focused verification. Commit/push each coherent verified checkpoint. Prepare the
candidate registry and archives, run fresh installation/negative controls, and
commit the exact release inventory and guide. Run broader checks once per complete
code/package boundary; repeat only for an observed failure or a subsequent change.

Registry resolution for the unpublished names uses a disclosed local rehearsal;
public crates.io name ownership, verified email, Cargo publishing credentials and
actual registry acceptance remain pending. Signing in on the website does not
publish or authorize a protected consumer. No general-adoption or performance
claim follows from crate installation.

## Implementation checkpoint

The alpha source changes use dependency-owned source fragments, self-contained
input inventories and per-crate actual-input digests. The separately named fork
is an explicit standalone workspace. Its original notices and inputs remain.
The source audit identified and repaired the missing legacy projection identity
binding. Native Python syntax, 256 crate-contained literal includes and all 79
production source bindings pass. Formatting/input synchronization passed in the
second preparation run. The first preparation refusal (nested Cargo workspace)
is retained. Locked native compilation/tests and exact archive/clean-install
acceptance remain pending under the shared Intel build reservation.

## Linux source acceptance

[Hosted run 39341691837](https://github.com/roryscot/patamaps/actions/runs/39341691837) passed all four jobs on source commit 6d6f31d1bb5a1e64380491b7053a3e2d84f57fe0: native Linux x86_64, native Linux aarch64, cross-stack source bindings and the Linux image/browser flow. The exact run/job state is retained in docs/acceptance/crates-io/2026-10-19/linux-ci.json. This is source acceptance; candidate archives, native Intel checks and source-unavailable clean installation remain pending.

## Intel source acceptance

All seven commands in native-0001 completed successfully: input synchronization, formatting, locked/offline all-target compilation and Clippy, workspace tests, doc tests and CLI build. Its final comparison failed because the verifier compared the complete executor-description envelope against only the four independently calculated digests; all four already matched. The corrected native-0002 focused rerun passed the complete envelope, four identities, 256 contained includes, all 79 production source bindings and unchanged-source check. The only inventoried differences between runs were the verification script and the standalone fork lockfile; Rust production sources were unchanged. Original failure and successful rerun are retained in the acceptance records.

The standalone fork fetch passed and updated its lockfile for the renamed package and build digest dependency, retaining upstream versions. The offline rehearsal now compares archive identity/checksum separately from optional dependency graphs; three valid ICU graph differences demonstrated the earlier over-strict equality. Candidate archives and clean installation remain pending.

## Exact candidate archives

Frozen publication source is commit 3f54166f8ad4f2071c88de145e2b20ed38355502, retained in the independent publishing-source-0001 Intel checkout. The checksum-verified offline seed contains 255 public upstream archives (24,920,478 bytes); it copies no Cargo credentials. Cargo package --locked --offline built and verified all ten candidates, totaling 3,070,893 bytes. Every archive passed the license, name/version, ordinary-member, normalized-dependency and 10,000,000-byte checks. Exact archive/member hashes, order and command records are retained in the acceptance directory; the frozen checkout stayed clean. Fresh source-unavailable installation is queued and remains pending. No package was uploaded.
