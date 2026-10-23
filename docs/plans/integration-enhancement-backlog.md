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
