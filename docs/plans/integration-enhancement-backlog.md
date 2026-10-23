# Integration enhancement backlog

Owner scope revision: 2026-10-21. The product stopping boundary is the
[C01–C19 native capability goal](../../BUILD_PLAN.md), with its identified-source
acceptance and explicit compatibility limits. The separate Intel adoption goal remains active and uses this backlog for priorities.
These tasks are not prerequisites for the capability milestone. Existing
implementations, failed runs and evidence are preserved.

The [former adoption plan](2026-10-15-general-project-adoption.md) retains detailed
G0–G6 requirements and historical checkpoints. The
[support matrix](../guides/project-support-matrix.md) records scoped results;
a passed fixture or metadata observation is not general support.

| Workstream | Existing result | Remaining work if selected |
| --- | --- | --- |
| Real Rust application onboarding | Explicit project capture, Cargo observations, scoped Axum transport and pinned upstream Axum build/tests/replay | Choose one owner application and correspondence; wire generated artifacts into its real handler and run its own positive/refusal tests. |
| Broader Next.js/framework integration | Selected production build, public HTTP/browser paths and declared observations | Qualify a named rewrite, route-group or Server Action boundary with non-writing controls. Authenticated backend/permissions remain unaccepted. |
| Retained builds and portable development loop | Controlled watch/recovery and scoped actual Rust retained workflow | Application-specific dependency closure, fresh installed workflow and measured edit-loop behavior; no blanket hermeticity or speed claim. |
| Deployment expansion | Scoped actual Linux output/runtime and deployment refusals | Remaining wrong-architecture/stale-contract controls or a chosen deployment profile. Production activation remains separate. |
| Performance acceptance | Existing functional timing records | Define comparison and acceptance budgets before exclusive measured execution. Diagnostic profiling remains separate. |
| Storage and reservation infrastructure | Installed qualified protocol3 reservations and bounded retention controls | Maintenance for demonstrated failures; no infrastructure prerequisite for parity. Preserve native/benchmark exclusive fallback. |
| Qualification tooling | Source-preparation privacy controls and retained failed runs | Repair only for selected qualification work; collector defects are not product defects without a reproduced product failure. |

## Current selected work

The latest focused increment is [native snapshot-backed Docker discovery and actual Miniserve image execution](../acceptance/project-adoption/g5-native-binary-docker-context-20261023/ci.json): the authentic binary is now captured opaquely and bound to COPY observations instead of being excluded from native discovery. Its current-engine Linux checks passed. Intel-native verification passed all 57 tests and rebuilt the CLI with the same engine; all six current capability regression jobs also passed. Earlier installed/browser receipts remain frozen to their tested engines. After these regression checks, continue broader Next boundaries, complete dependency/test-context closure and practical exclusive edit-loop measurements. The Nango-dependent app remains owner-deferred. G0–G6 general adoption is not complete.

## Earlier Next candidate checkpoint

Pinned Fumadocs source and frozen dependency preparation passed; see the
[preparation receipt](../acceptance/project-adoption/g3-fumadocs-source-preparation-2026-10-21/receipt.json).
The subsequent [production-build attempt](../acceptance/project-adoption/g3-fumadocs-next-build-2026-10-21/receipt.json)
failed at owner command pnpm --filter docs run build:pre in workflow
39625379329 on Patamaps commit 5048d309. Three source-acquisition tests, the
native release CLI build, source privacy/capture/staging and frozen install
passed. The selected source contained 2,792 paths / 47,825,903 bytes; copy
digests were checked before the pre-build. A read-only audit of the exact pinned
upstream commit 2919bf9 confirmed apps/docs defines build as
pnpm build:pre && next build && pnpm build:post; build:pre runs the owner's
fuma-cli/compiler registry generation. The compiler reported unresolved
package-local aliases and relative imports in packages/radix-ui. The source
files and their declared TypeScript alias configuration were present in the
pinned tree and selected inventory. This is evidence against source omission,
but does not establish whether the cause is an upstream compiler defect or an
unsupported build precondition. Next production compilation never started, so
this remains a failed project candidate, not a Patamaps product failure or a
G3 pass. Owner post-build / Orama, runtime, HTTP, browser, deployment and
installed workflows remain unverified. Preserve this failed run and its
artifact; do not patch the upstream candidate or retry the unchanged build.
Continue G3 with another unchanged real Next.js application whose production
build can run without unresolved owner-side prerequisites.

## Unfinished Next preparation checkpoint

At source b02430434dd25036e7a793341dc989a6e7b0459c, Fumadocs preparation
workflow run 39534703032 failed in its final collector with an undefined
safe_oids name. Recorded preparation commands, including frozen dependency
installation, returned zero; final report/budget aggregation did not complete.
No application build/runtime acceptance follows. Run 39533833003 previously
failed on an unsupported pnpm retry option. Preserve both failures; neither
demonstrates a Patamaps product defect. This work is deferred, not accepted.

## Hyperbound Next source candidate (2026-10-21)

The unchanged Hyperbound checkout at commit `7721da50e4a817dafb13a8e4cd10347e7ee884f7`
is a real Next 14.2.14 candidate with 54 App Router pages and explicit route-group
structure. Its declared Node version is 22.8.0 and installed TypeScript is 5.5.4.
A path-only profile selects 66 tracked inputs: 61 Next special files and the
package/runtime/configuration/lock files. It excludes `.env`, `node_modules`
and `.next`; no source bytes were added to the profile.

The supervised observation request `b8283792-531e-49b8-8fbb-ca7663bc5eca`
finished with confirmed workload stop and lease release, but the guard refused
before capture or staging because retained-output headroom was insufficient.
The failed guard record is retained at
`/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/d5c00cfa-dd7c-4720-a9bf-5d38900dd7d0/run.json`.
No Next build ran. Route-group/dynamic observations, configuration semantics,
runtime, browser, deployment and installed-consumer acceptance remain unverified.
The compact [receipt](../acceptance/project-adoption/hyperbound-next-source-20261021/receipt.json)
preserves the scope and exact result. Continue only after resolving headroom under
the existing retention policy; do not bypass the guard or remove files without a
fresh exact-list approval.

## Selection and completion rule

Select one workstream, named project, observable outcome, resource budget and
focused verification before starting. Reuse existing contracts. Broaden checks
only when changed behavior or an unresolved failure justifies them. Commit
verified increments with exact source identities. Do not repeat complete CI,
large evidence capture or storage scans merely to maintain momentum.

New evidence may expose a genuine C01–C19 defect; record its requirement and
reproduction in the capability plan. An enhancement does not become a parity
blocker simply because a qualification harness has a failing test.


## Selected increment: digest-bound ELF target preflight (2026-10-22)

Scope: add one native Rust read-only check usable as an existing owner build
verification command. Declare an exact artifact digest and linux/amd64 or
linux/arm64 target. Preserve existing project command/build contracts. Reject
unsupported targets, nonregular/oversize inputs, digest mismatch, truncated or
unsupported headers and mismatched machine; never execute the inspected binary.

Acceptance: focused malformed/binding/short-read tests; matching and wrong-target
checks on actual retained Linux binaries; CLI build and exact exit-status checks.
Use one exclusive guarded native run with a 1 GiB growth budget, two Cargo jobs
and incremental compilation disabled. No deletions or policy increases. This is
an enhancement: a header match does not establish loader, libraries, Linux OS,
runtime acceptance or immutability between a later separate check and launch.
G5 wrong-architecture runtime and stale generated-artifact controls stay open.
The source-bound Next case still waits for reviewed nonsecret API configuration.


Verification result: [scoped receipt](../acceptance/project-adoption/g5-elf-target-preflight-20261022/receipt.json)
records all 50 workspace tests and 11 artifact checks passing, including real
x86_64/ARM64 matches and wrong-target refusals. The native guard completed and
released its reservation. No architecture runtime or stale-contract gate is
reclassified; no parallel activation, package publication or deletion occurred.


## Selected follow-up: captured isolated Next configuration (2026-10-22)

Use the unchanged 923-file Next 14.2.23 source snapshot with an explicitly
build-only API URL http://127.0.0.1:1; keep network denied and Sentry disabled.
This is a lab projection, not the missing owner's real API configuration.
Capture and replay nonsecret configuration plus sandbox bytes independently,
refuse a missing environment reference before launch, and run Next through
native ProjectCommand using captured environment references only. Retain the
prior application failure; observe actual child status without suppressing
further prerequisites. Use one exclusive 512 MiB guarded attempt and preserve
source/dependencies, failed evidence and every unapproved file.


Owner decision (2026-10-22): defer this app and continue other gaps.
The [captured-configuration receipt](../acceptance/project-adoption/g3-next14-captured-lab-config-20261022/receipt.json)
passes captured-only native environment resolution, missing-reference refusal,
bounded launcher/log bindings and configuration replay with inputs unavailable.
Next compiled/typechecked, then prerendering failed Missing Nango public key
(NEXT_PUBLIC_NANGO_PUBLIC_KEY). No key was fabricated or raw dotenv ingested.
Preserve the application failure and earlier qualifier-bound failure. Do not
retry until reviewed configuration is available. Continue Linux deployment gaps.


## Selected deployment increment: native architecture selection (2026-10-22)

Use the same actual Rust runtime from successful x86_64/aarch64 CI artifacts,
with exact source/binary receipt binding. Native ProjectBuild must select the
declared linux/amd64 runtime and refuse the ARM candidate during verification,
preserving the prior selection; replay its bindings and run a harmless selected
runtime probe through the managed Linux executor. Reuse existing context/build
contracts. This self-hosting case complements independent project evidence; it
does not claim generic ELF loader validity or external application deployment.
Budgets: exclusive native 384 MiB growth (including retained CI archives and quota image); managed CPU1/memory256MiB/quota128MiB.
No production trust/activation, deletion or policy increase.


Verification: the [native architecture-selection receipt](../acceptance/project-adoption/g5-native-architecture-selection-20261022/receipt.json)
passes x86_64 selection, authentic ARM64 ELF_ARCHITECTURE refusal with the old
pointer unchanged, source/snapshot-unavailable replay and selected-runtime
usage-only Linux execution. Exact CI source/binary bindings were checked.
This is self-hosting evidence, not independent application deployment.

The initial state-location error remains failed. Later 128 MiB quota preparation
exhausted a lowered native aggregate growth budget and required reviewed stop
recovery. All original records/image remain. A preparation-only retry used a
64 MiB quota/448 MiB native ceiling, reused passed selections and succeeded.
CPU/memory/quota/mount restrictions were inspected before launch; container
stopped and all reservations cleared. No deletion, trust/activation or parallel
rollout. External deployment, stale generated contracts and performance remain
open. The owner-deferred Next app remains deferred.


## Selected increment: verified selected-artifact execution (2026-10-22)

Add a Rust API and project-exec-selected CLI entrypoint using the existing
ProjectCommand/capture/build-selection contracts. Hold the cooperative state
lock, verify selected source/generated/compiled bytes before command execution,
and recheck selection/pointer afterward. Preserve existing project-exec behavior.
Preflight failure must prevent command effects. Failed/mutating commands remain
refused; no automatic rollback of arbitrary effects or deployment authorization.

Acceptance: captured cwd/environment execution; stale output prevents a marker
side effect; competing build/run cannot acquire the live lock; post-execution
artifact/pointer mutation refuses; owner death stops ordinary descendants and
releases the cooperative lock. Then qualify an authentic older Wargame-generated
client against a native selected current client before any module/network use.
Keep application sources/compiler unchanged; preserve genuine failures.
Use native exclusive fallback and existing storage policy, with 384 MiB growth
ceiling for the implementation checks. Preserve the creating CLI as a verified
compressed recovery copy before rebuilding. No deletion or registry publication.


Implementation checkpoint: the [selected-execution receipt](../acceptance/project-adoption/g5-selected-project-exec-20261022/receipt.json)
passes 50 workspace tests and 10 CLI controls on Intel, including three termination
signals, competing executor/builder refusal and stale-before-effects refusal.
The 384 MiB exclusive guard completed with exit 0. The creating CLI has a
compressed recovery copy whose decompressed digest was checked; restoration
and re-execution were not exercised. Authentic generated-client qualification
subsequently passed in the scoped result below. Existing project-exec remains available;
the new selected gate is opt-in and has not been published to crates.io.


The [authentic generated-client receipt](../acceptance/project-adoption/g5-authentic-client-selected-exec-20261022/receipt.json)
passes native HTTP TypeScript compilation using 106 captured compiler files
(9,947,809 bytes), selection-bound module loading, authentic older-client
refusal before module loading, and restored-current-client execution with the
selection pointer unchanged. Source snapshot unavailable; original app untouched.
The exclusive 128 MiB guard completed and released its reservation.

The first retained prebuilt-client attempt failed because its TypeScript source
did not equal the new native emission. It remains failed and preserved; the
corrected attempt compiled that actual emission. Byte selection does not infer
a source/compiled relationship that owner verification failed to establish.
This closes the selected-artifact startup refusal increment, not deployment G5:
external deployment and performance remain open. Backend/client-generation
compatibility is not established by this startup-only check. No new network qualification, production activation,
parallel execution, publication or deletion. The Nango-dependent app stays deferred.


The [CI receipt](../acceptance/project-adoption/g5-selected-project-exec-20261022/ci.json)
records all six applicable PR jobs passing for implementation a22ff8d, including
x86_64/ARM64 native acceptance, source binding/replay, actual Axum qualification
and the Linux image/browser path. The focused push job also passed the new
selected-execution controls. The Fumadocs workflow-dispatch-only job was skipped.
The final evidence/docs checkpoint changes no implementation and skips redundant
CI. The enhancement goal remains active; this is scoped acceptance, not completion
of all G0–G6 requirements.

## Selected increment: external Rust service deployment (2026-10-22)

Project: upstream Miniserve v0.35.0, annotated tag object
0d5748f579c6c4895d170fe1e5cb752f38479c71, source commit
2cd9c495ef25f2fcef505615f603e9de8f981915. Primary provenance:
https://github.com/svenstaro/miniserve/releases/tag/v0.35.0 .
Freeze the GitHub release asset metadata and check each downloaded digest.
Phase one uses official linux-musl x86_64/ARM64 binaries; this is prebuilt-runtime
qualification, not rebuilding that source or attesting reproducibility.

Reuse native ProjectContext/ProjectBuild/ProjectCommand and the existing managed
Linux executor. Capture a reviewed nonsecret service configuration, explicit
static document, bundle-preparation code and HTTP probe. Select exact bundle
outputs; refuse wrong config, digest and ARM target while preserving selection.
Export only through project-exec-selected, then independently verify all exported
bytes before starting the owned container. With configured snapshot/source
unavailable, selected binding replay must still pass.

Runtime acceptance: actual Linux x86_64 startup; exact GET body, HEAD length,
directory listing and missing/out-of-prefix refusals; invalid CLI port and a
wrong-listener readiness refusal. Preserve all HTTP/process logs. Inspect actual
CPU/memory/swap/quota, readonly root, no host networking/source mount, and only
/work writable before launch; confirm owned processes/container stopped afterward.
No browser, authenticated service, source build, complete dependency closure,
production deployment, trust activation or installed-package pass follows.

Budget: native exclusive preparation with 192 MiB per-run maximum growth under
the unchanged existing retention/reserve policy; managed CPU1, memory256MiB,
64MiB output quota. Reuse the pinned cached Ubuntu image; no Docker restart or
unrelated service changes. No deletion. If admission fails, retain evidence and
use another safe action rather than bypassing accounting.

Phase two remains required: build the same pinned application's source on Linux,
repeat the native selected runtime workflow with its produced artifact, and
qualify an exact installed Patamaps consumer. Practical exclusive edit-loop
measurements and broader framework boundaries remain separate open requirements.

Execution refinement before application work: cached native test archives do not
contain a Linux Patamaps CLI suitable for pre-publication service verification.
Use a dedicated, manually dispatched Linux CI job first. It builds the unchanged
Rust implementation and pinned Miniserve source, runs the owner's default test
suite, and verifies HTTP before native build publication. Failure controls reuse
that compiled binary; they do not repeat the Rust compilation. Commands have
existing parent-death cleanup, bounded logs/deadlines, and two-second-or-faster
4 GB growth/500 MB reserve monitoring on the isolated CI host. This is separate
from Intel's still-required managed CPU/memory/quota acceptance.

The native Intel configuration preflight uses a smaller 16 MiB exclusive growth
ceiling. Its ten controls cover valid projection, duplicates, unknown/auth-file
settings, boolean/overflow/privileged ports, public binds, path traversal, target
and nonsecret declarations. No full six-job regression rerun is required for
these script-only changes; the focused manual workflow must pass. Preserve
failed runs, and do not claim fresh package-installer acceptance from a copied
standalone compiler. The goal and managed-runtime/installed/performance
requirements remain intact.

The focused job is called through the existing registered native-capabilities
workflow with qualification=external-rust. Its reusable workflow runs only that
manual selection; unrelated native/Next lanes are skipped. Original source
compilation/default tests, runtime gates and retained artifact export must pass
before this increment can be accepted.

[Intel configuration preflight](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/receipt.json)
passed ten frozen cases and syntax checks under the exclusive 16 MiB guard.
Actual application source/build/test/runtime acceptance awaits the focused CI.

The [dispatch checkpoint](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/ci-dispatch.json)
records run 39880581447 at 3a043e7. Its focused external-Rust job was confirmed
live after the configuration controls passed; unrelated suites were skipped.
Resume by polling that same run, never restarting because an observation timed
out. On success inspect its actual command/runtime receipts and preserve exact
compiler, application and selected-state artifacts before the bounded Intel
managed replay. On failure inspect the frozen diagnostic before changing code.
No source/runtime/installed/deployment gate is accepted by this dispatch record.

Run 39880581447 subsequently failed before source capture at the privacy guard.
The [verified failure artifact](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/failure-39880581447.json)
is retained. Review found eight fixed public tests/data Git blobs, including TLS
fixtures. The correction excludes all eight fixture contents from every Patamaps capture and
published payload, rejects unknown/changed fixtures or new key/dotenv paths,
and keeps the complete default test suite in its original pinned public Git clone.
Its target cache is shared with the staged build; the produced runtime is frozen
before owner tests. These public test data remain an explicit external dependency;
no hermetic/full test-context acceptance follows. The staged application build
still uses captured source. No upstream code/test/fixture bytes are patched.
Five frozen selection/privacy controls must pass before one focused retry.

The corrected [fifteen-control preflight](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/source-privacy-controls.json)
passed under a fresh exclusive 16 MiB Intel guard. It validates the privacy
selection correction, not the application source/runtime pipeline; one focused
CI retry is required. The prior failure remains authoritative for its run.

Previous continuation handle (subsequently failed): [focused retry 39882477708](https://github.com/roryscot/patamaps/actions/runs/39882477708)
at source 303bc19728d37b5ea29cfa98bae17a4cce4a99b2, job 120182858099.
The job was confirmed live in compiler/source/test/HTTP qualification after its
configuration controls passed. Inspect the [observation](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/retry-39882477708.json)
and poll this exact handle; do not restart on an observation timeout. On terminal
success inspect commands/default-test totals, refusal/pointer/runtime assertions
and artifact digests before any acceptance, then do the existing bounded Intel
managed replay. Package-installer, managed runtime and performance remain open.

Run 39882477708 then passed privacy review/context capture/staging and failed
when the qualifier used unsupported component kind rust. This is a qualifier
error, not a demonstrated product defect; its [verified artifact and compiler](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/failure-39882477708.json) remain preserved.
A shared source-profile constructor now uses the declared cargo-package kind.
The [real-source Intel intake](../acceptance/project-adoption/g5-miniserve-config-preflight-20261022/native-source-intake.json)
passes 60-file exact staging, 39-text-input native capture/verification and all
fifteen config/privacy controls under a completed exclusive 64 MiB guard.
Cargo build/tests now explicitly select x86_64-unknown-linux-gnu. No application
build or runtime acceptance follows from the intake.

After committing this correction, dispatch only qualification=external-rust.
The latest exact handle will be saved in
.tools/project-adoption/miniserve-deployment-20261022/CURRENT_RUN.json; inspect it
and revalidate that exact run before waiting or retrying. Preserve both earlier
failures. Do not rerun unrelated suites or treat this source intake as G5/G6
completion. On success inspect actual owner-test/runtime/refusal results before
bounded Intel managed replay and installed-package work.


## Verified external Rust source/runtime checkpoint (2026-10-23 UTC)

Run 39884102308 at 36e6525 completed successfully. The [source/runtime receipt](../acceptance/project-adoption/g5-miniserve-source-runtime-20261023/ci-receipt.json)
binds the unchanged Miniserve 0.35.0 revision, 325 default upstream tests
(19 harnesses, zero failures/ignored), eight startup/HTTP controls, four native
config/listener/digest/architecture refusals with old selection preserved,
source-unavailable replay and stale runtime refusal before effects.
The exact creating compiler, application and selected-state archive were retained
and digest-verified. Its test data remains an explicitly external public Git
fixture dependency outside all captures.

The [Intel replay](../acceptance/project-adoption/g5-miniserve-source-runtime-20261023/managed-replay.json)
imported the exact state without changing archived modes. Native verification
passed on Darwin with the same engine record; the creating Linux CLI then
verified and executed it inside the existing managed executor. Actual kernel
CPU1/memory256MiB/zero-swap and a 64MiB writable quota were verified, root remained
readonly, networking isolated and no source was mounted. /work was the only writable bind mount for outputs. All eight runtime
controls passed again, every imported byte and selected pointer stayed unchanged,
and only the owned container/process group was stopped before reservation release.
Preparation transport reset after completion was resolved by checking authoritative
finished guard/request state before launch; no work was restarted or lease forced.

This closes this external source-built runtime/selection/replay increment, not
all G5/G6. The [guide](../guides/external-rust-deployment.md) records usable command
contracts and limits. Next work is fresh exact source/native package installation
on this same selected application workflow, then application-image/browser and practical exclusive
edit-loop evidence. Reuse the frozen successful compiler/application/state rather
than repeating source builds without a new reason. Broader framework boundaries,
full dependency closure and the owner-deferred Nango app remain unaccepted.
No registry publication, production/trust activation, parallel rollout or deletion.

## Selected increment: exact installed external Rust consumer (2026-10-23 UTC)

Reuse successful Miniserve run 39884102308 and artifact 12472158570, SHA-256
8fe5985620e6f584024499d5936ce2528d256a6145a35c94dd2f0aa866755d39.
No new Miniserve compilation/default-test run is needed. Freeze and verify the
producer's production-source Git tree/blob identities before pairing its native
compiler with the current source payload. Keep the existing bounded package
format and archive installer; share the existing installer instead of copying
the fixture workflow. Refuse duplicate normalized members and retain all failures.

Acceptance: exact source/native archive digests; complete installed inventory
membership/bytes; fresh native archive prefix and fresh Cargo install from that
source; both installed compiler engine identities; selected bindings and all
eight real Miniserve controls from a driver inside installed source, outside
examples; late-artifact refusal before effects; restored selected state; runtime
with both test-installation compilers and the producer compiler unavailable.
Verify source inventories again afterward. No graph compiler on request paths.

First run eight frozen extraction controls and actual package-scope validation
under a native-exclusive 32 MiB Intel guard. A --check-scope packaging option
performs the existing bounded selection without creating unused archives or
executing a binary. Existing size/evidence limits are unchanged.

Use one focused manual CI lane with two Cargo jobs, per-command deadlines/log
bounds and monitored 4 GB disk growth / 500 MB reserve. Only artifact download
receives GitHub's scoped workflow credential; no credential enters capture or
application commands. Do not repeat the unrelated six-job suite unless changes
or failures require it. No registry/trust/production activation, deletion or
parallel rollout. Application-image/browser, dependency closure and performance
remain separate unaccepted requirements.

Intel preflight completed under native guard 261c9e93-29d8-4a58-9bc5-7d74ea936c16 (exit 0): eight archive controls passed; actual bounded source selection passed with 1,071 files and 75,840,756 bytes including its inventory. No package archives or binary execution occurred in that preflight. All nine production Git identities match the frozen compiler's source. The focused `external-rust-installed` workflow is prepared; installed application acceptance remains pending its execution.

The first installed-consumer CI run [39897080202](https://github.com/roryscot/patamaps/actions/runs/39897080202) failed after successful exact packaging and fresh locked/offline Cargo installation. The installed native compiler matched its source identity, then refused imported context with PROJECT_CONTEXT. Read-only comparison showed Python data_filter discards directory modes (including bound 0700 context directories); the frozen archive itself was unchanged. The importer now retains validated archive modes while keeping data_filter path/type checks. A ninth regression control and direct native verification of the exact frozen state are pending under the same 32 MiB native guard. No product binding, archived state or acceptance criterion was changed.

The correction passed Intel native guard 9ff566ec-2568-4cbd-9d09-823336cda845 (exit 0): all nine archive controls, followed by actual project-build-verify on the exact restored frozen state. Native source/binary behavior and declared state bindings were unchanged. This directly verifies the import repair before repeating the focused installed-consumer CI lane.

## Completed installed external Rust increment (2026-10-23 UTC)

[Run 39897900519](https://github.com/roryscot/patamaps/actions/runs/39897900519), source c6b58517e19ef68b99ca9a7a215ed661cf01c390, passed the focused lane after the independently verified mode-preserving import repair. The [CI provenance](../acceptance/project-adoption/g5-miniserve-installed-20261023/ci.json) and [receipt](../acceptance/project-adoption/g5-miniserve-installed-20261023/ci-receipt.json) freeze exact package/engine identities and 1,071 installed source files. Fresh native extraction and locked/offline Cargo source installation both passed installed-source execution of all eight real runtime controls. Late artifact mutation refused before effects; restoration passed; runtime passed again with the producer and both test-installed compiler paths unavailable. Selected bytes/pointer and the complete installed-source inventory remained unchanged. Miniserve was not recompiled or retested.

Artifact 12477786702 is 18,287,962 bytes, digest sha256:ccb9af37ece3fb209aeec5681462abd6864a09ed8a717d78945399d51910d067, independently verified at intake. Raw package archives remain in that 14-day CI artifact; only compact receipts were retained locally and committed. This is an unpublished exact-package qualification, not registry publication, independent binary reproducibility, complete dependency closure or all G5/G6 acceptance. The first failed attempt remains preserved. Both Intel preflight reservations finished without forced recovery, policy changes or deletion.

## Selected increment: real Rust application image and browser (2026-10-23)

Reuse the exact Miniserve executable and selected bundle from the completed external Rust source/installed milestones; no new owner source build or test run. Extend only the focused installed-consumer CI lane with an explicit application-image option. BuildKit must build a linux/amd64 runtime image from the digest-pinned Ubuntu base and an exact bounded bundle context. Verify actual image identity, configuration, file bytes/ELF target, nonroot user and runtime limits; export a compressed image for scoped replay. Exercise real Chromium listing, file-link navigation, return navigation and missing/out-of-prefix refusals. Refuse an actual entrypoint override before startup. Confirm the owned container stopped and its listener disappeared; retain failures and objects, never prune/delete.

The frozen launcher binds loopback. The dedicated Linux CI container therefore uses host networking, with no published port or public listener. This is deliberately a CI functional profile, not network isolation or production deployment; Docker documents host mode as sharing the host network namespace (https://docs.docker.com/engine/network/drivers/host/). Enforce/read back one CPU, 256 MiB memory, zero swap, 64 PIDs, readonly root, no host bind mounts, bounded 1 MiB /tmp and /dev/shm. Chromium tools run outside the image and selected source using the existing pinned Playwright lockfile, not the fixture workflow. Only artifact download receives the scoped workflow credential.

Use the existing monitored 4 GB CI growth/500 MB reserve and per-command log/time bounds. The lane is manual and focused; do not repeat the unrelated full suite. Source/native installs are relevant to the modified installed-source recipe and repeat in this lane. Compact receipts/screenshots remain useful evidence; binary packages and compressed image stay in the 14-day CI artifact. No Intel application workload, registry push, production/trust activation, policy increase or deletion.

Newly observed remaining adapter gap: native_docker.rs requires complete contextFiles to equal UTF-8 captured inputs. A precompiled executable cannot be honestly included as text. Do not encode it or omit it while declaring a complete capture. This increment verifies real image effects through the selected binary/context digests and actual BuildKit/image observations. Binary-bearing Docker context discovery needs a separate native contract change and controls; this result alone cannot complete all G5. Dependency/test-context closure, broader framework boundaries and exclusive edit-loop measurements remain open.

First image attempt [39899222207](https://github.com/roryscot/patamaps/actions/runs/39899222207), source e7f314e, passed fresh installations, image construction, exact base identity, and actual entrypoint-override refusal. It stopped before positive runtime at a non-reusable socket bind with EADDRINUSE. The [digest-verified failure](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/first-attempt.json) preserves this result and confirmed-stopped owned container. TIME_WAIT after earlier HTTP probes is plausible; that historical cause is not established by the available logs. The preflight now permits completed connections' TIME_WAIT while retaining active-listener refusal. Two Linux counterexample controls and preflight TCP-state evidence run before/with the focused repeat; they are pending, not already accepted.

The second [image attempt 39899637159](https://github.com/roryscot/patamaps/actions/runs/39899637159) passed both Linux socket controls and observed only TIME_WAIT (TCP state 06) before successful startup. Exact image runtime bytes/ELF, kernel CPU1/memory256MiB/zero-swap/PIDs64, readonly root and two 1MiB writable mounts passed. Chromium rendered the real listing without page errors or off-origin requests, then the strict accessible-name selector timed out. The [retained failure and screenshot](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/second-attempt.json) plus DOM trace show the genuine a.file link href /qualified/status.txt; its rendered CSS icon affects the accessible name. Select that exact observed href/class and assert its DOM text before the same real click/history/refusal checks. Do not change the app, remove controls or extend timeouts. Both owned containers and listener stopped. This is still failed browser acceptance until the corrected focused run completes.

## Completed real Rust image/browser increment (2026-10-23)

[Run 39899991879](https://github.com/roryscot/patamaps/actions/runs/39899991879), source 5a5deaee455b5101a548e53936b5f3afccba0306, passed the focused lane. The [CI provenance](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/ci.json), [image receipt](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/image.json) and [browser receipt](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/browser.json) record exact source/native installs (1,078 source files unchanged), BuildKit linux/amd64 image construction from the pinned base, exact selected executable bytes/ELF, an actual entrypoint override refused before startup, kernel CPU1/memory256MiB/zero-swap/PIDs64 and two verified 1MiB writable mounts. Chromium 156.0.8078.4 passed all six listing/link/history/missing/prefix/error controls. Both owned containers and the listener stopped; no foreign object was touched.

The frozen loopback profile uses host networking on the dedicated Linux CI runner, with readonly root and no source bind mount. It is not network isolation, production acceptance or a benchmark. Nine archive controls and both live-listener/TIME_WAIT counterexamples passed. Earlier failures remain preserved; corrected discovery of the real file link did not change upstream application bytes or acceptance requirements. Miniserve was not recompiled or retested.

Artifact 12478337862 is 51,031,520 bytes, digest sha256:a26e3fdd1dac97ee208db426ea5f78ea1f2671e189682e83b54bad820987c3c5. Its exported compressed image is 32,951,944 bytes, digest sha256:12de2713be67b295f22714df7077639a521fe3495f4226107e8d7007ecf5c3a2. Both digests were independently verified at intake. Binary packages/image remain in the 14-day CI artifact; compact receipts and a listing screenshot were retained, with no duplicate local ZIP/image. A fresh image reload was not exercised. Binary-context native Docker discovery, dependency closure, framework boundaries and practical performance remain open. No registry push, trust/production activation, retention-policy change or deletion.

## Selected native change: binary-bearing Docker discovery (2026-10-23)

Add an optional contextSnapshot {snapshot,digest} to the existing dockerfile provider; leave legacy text requests unchanged. Reuse sealed project-context verification rather than introducing binary JSON encoding or a second capture format. Before traversing payload bytes, bound this view to 1,024 regular files, 8,192 total entries and 512 MiB total file bytes; refuse symlinks, malformed/relative snapshot references, digest mismatches, unselected extras, nonsecret/blocked-path violations and unsupported file types. Bind every supplied text member (especially Dockerfile and active ignore files) to the verified snapshot. The complete contextFiles must equal its regular-file inventory. COPY observations receive member digests/lengths and snapshot lineage, while instruction execution, image contents and listener claims stay false.

Acceptance: preserved legacy behavior; real non-UTF8 payload/owner-unavailable replay; changed text/binary/modes/membership and wrong digest refusal; closed directory/nested COPY/ignore behavior; absent ignore-text refusal; privacy/path/symlink/unknown-key controls; size/count limits checked before payload traversal. Exercise canonical native request/response, not only internal parser functions. Run focused/all workspace tests and CLI controls against a new binary; qualify the exact public Miniserve executable as a real snapshot-backed image context without recompiling it. Rust source/engine changes justify a current full capability regression checkpoint after focused checks pass. Historical old-engine deployment receipts remain frozen; never relabel them current or bypass old-state engine refusals. No Intel unsupervised builds, storage-policy increase, registry/production activation or deletion.

Initial native push [39901712630](https://github.com/roryscot/patamaps/actions/runs/39901712630) compiled successfully and passed 56/57 workspace tests. The failing new mode case changed internal stored-blob permissions; retained contexts deliberately restore executable permissions from the digest-bound manifest rather than the blob's storage mode. The control now changes captured manifest mode and asserts staged mode 0755. Metadata separately states snapshotBytesVerified and capturedModesBound. The loader/binding acceptance rules were not weakened. A corrected Rust run and real public-binary qualification are pending.

## Verified native binary-context checkpoint (2026-10-23)

The [focused current-engine run 39902567350](https://github.com/roryscot/patamaps/actions/runs/39902567350), source 7b1eee15d29fa51fe4b2bc68049cc2e0748fee79, passed 57 workspace tests, strict all-target workspace Clippy, ten CLI discovery/replay/refusal controls and all eight actual Miniserve image runtime controls. The [receipt](../acceptance/project-adoption/g5-native-binary-docker-context-20261023/ci.json) and [native observations](../acceptance/project-adoption/g5-native-binary-docker-context-20261023/discovery.json) bind the genuine 7,663,536-byte executable by digest without supplying it as JSON text. Exact seven-file context staging, original-owner-unavailable replay, BuildKit construction and image executable bytes passed. The runtime used readonly root, no host source binds, isolated networking, one CPU/memory256MiB/zero-swap/PIDs64. Its owned container stopped. No owner compilation or test rerun, registry push or activation occurred.

The current workspace engine is sha256:dcab076597bb431171bcefc5b2d97b513c6b5c91d51d26d6689a7d81136d76b0. The [snapshot guide](../guides/docker-context-snapshots.md) records limits and usage. Historical installed/browser receipts remain frozen to their older engines. Full current capability run 39902969665 and an exclusive Intel-native 128MiB regression reservation 9dce136c-68e5-4fbc-a197-a58fc2ba896e are in progress; do not label them passed until their authoritative results complete. The prior Intel compiler is preserved before rebuilding. Complete dependency/test-context closure, broader Next boundaries and practical edit-loop/performance requirements remain open.

Intel-native verification also passed: [57 workspace tests and rebuilt native CLI](../acceptance/project-adoption/g5-native-binary-docker-context-20261023/intel.json), guard fca9dc34-5bcc-4d5e-92a8-083eb8f8cefc, exit 0 under the existing exclusive 128MiB run allowance. The previous compiler was preserved, the new Darwin compiler engine equals the Linux engine, no new container survived and reservation 9dce136c-68e5-4fbc-a197-a58fc2ba896e finished. This is functional verification, not performance acceptance. Full capability run 39902969665 remains pending at this checkpoint.

## Completed current regression checkpoint (2026-10-23)

[Full run 39902969665](https://github.com/roryscot/patamaps/actions/runs/39902969665), source 7b1eee15d29fa51fe4b2bc68049cc2e0748fee79, passed all six required capability jobs: Rust metadata/selected execution, retention, native Linux x86_64/aarch64, source bindings/watch/actual Axum, and Linux image/browser. The [terminal API receipt](../acceptance/project-adoption/g5-native-binary-docker-context-20261023/full-regression.json) records individual job/step results and GitHub-reported artifact identities. Large regression artifacts were not downloaded or described as locally digest-verified. Current production trees match the tested source; only documentation/evidence changed afterward.

The selected native binary-context change is implemented and verified on Intel and Linux, with actual public-Rust image runtime evidence. This closes that named source-discovery gap. It does not close complete dependency/test-context provenance, remaining real Next rewrite/Server Action/runtime/permission boundaries, current-engine external installed/browser replay or practical exclusive cold/warm/edit-loop measurements. Continue those original G0–G6 requirements; keep the Nango app deferred and the whole adoption goal active.

## Selected Next Server Action candidate (2026-10-23)

The retained Avaelus/Seeder app has no use-server source files and empty rewrite lists, so do not relabel it as Server Action runtime evidence. Pin public https://github.com/vercel/chatbot.git at c2f8235e1f3ea903ad8b7f61447c4f74164b5c58 (181 tracked files, no AGENTS.md): Next16.2.10, pnpm10.32.1, real Auth.js credential actions, Postgres migrations and four upstream auth-page browser tests. Source/actions and build prerequisites were reviewed at that exact commit rather than mixed web-cache revisions. The Nango app remains deferred.

First establish frozen source acquisition/privacy, opaque source capture/staging, native text capture, the unchanged owner's production build command and exact compiled Next manifest observations. Reuse the existing partial Git acquisition implementation with an explicit required-omission profile; .env/.npmrc and excluded-only blobs must remain absent, including the public .env.example template. Do not pull Vercel environments or use any existing application credentials. Keep upstream bytes unchanged. Use the current CLI with source-engine verification and the existing bounded native project-exec contract. Build-mode configuration is explicit and nonsecret; secret references remain labels. Report any owner-chosen migration skip honestly, not as database acceptance.

Then qualify actual production Server Action login/register/validation/origin and permission behavior using a new isolated CI-only database and generated test signing material kept outside source captures and published evidence. Upstream four auth tests cover page rendering/navigation only; they do not prove login success or action security. Add those runtime controls explicitly. No external model-provider, upload or production-authentication claim. A build alone does not close this phase. If secrets are required by owner programs, use an explicit trusted owner boundary; do not declare keys nonsecret or weaken the compiler's no-resolution rule.

Use one focused manual Linux lane with Node22.23.3, two Cargo jobs, a 2GiB Node heap limit, monitored 4GB workflow disk growth/500MB reserve and per-command time/log bounds. Keep work outside Cargo parents. Preserve failures; upload compact nonsecret receipts, never raw environment/server-reference encryption material, authentication cookies or private test credentials. No Intel unguarded build, storage-limit change, user database access, source deletion or registry/production activation. New Next manifest shapes must be reviewed explicitly; do not ignore unknown fields to obtain a pass. Existing source-acquisition controls plus real source/build/manifest evidence are the acceptance for the first increment; the complete framework/runtime requirements remain active afterward.

First Chatbot run [39908203690](https://github.com/roryscot/patamaps/actions/runs/39908203690), source c30d5bf, passed four actual Git acquisition controls plus pinned source privacy/capture/staging. It stopped before dependency installation: npm rejected loading /dev/null as both user and global configuration. This was harness configuration, not an application or Patamaps product failure. The [verified failure record](../acceptance/project-adoption/g3-chatbot-source-20261023/first-attempt.json) is retained. Bootstrap now supplies two distinct empty isolated config files. No app source, credential policy or build criterion changed; owner production build and manifest/runtime acceptance remain unverified.
