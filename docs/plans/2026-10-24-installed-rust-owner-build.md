# Fresh installed Rust owner builds

Status: accepted for the exact development-profile source/native pair at8c6de4,
workspace enginea5d602de, with pinned Miniserve0.35.0 on Linux x86_64.
This is the original G5/G6 installed-consumer requirement, independent of the
storage-blocked native G4 measurement run. Develop on Intel; use the existing
opt-in Linux qualification infrastructure for actual work. No Intel guard bypass,
cleanup, policy increase, registry publication or production activation.

## Fixed workload and reused contracts

Reuse scripts/qualify_miniserve_linux.py with its pinned Miniserve0.35.0 Git
revision, explicit selected source, original public test clone and unchanged
Cargo-registry context/executor. Reuse package.py, exact archive installation,
verify_installed_source, project-context/build/verify/exec-selected, existing
guardian and HTTP/refusal recipe. Do not add a build framework or replace tests.
The public CA bundle, host toolchain and eight uncaptured public test fixtures
remain explicit external inputs; complete dependency/OS/test-context closure
stays false.

The earlier fresh installed result verified retained-state/runtime replay and
explicitly set applicationRecompiled=false. It cannot prove this increment.

## Observable acceptance

1. Build a current checkout CLI solely for producing exact source/native
   archives. Verify archive SHA-256, distribution engines, installed source
   inventory and every shipped source member against the producing tracked
   checkout. A clean Git source must precede packaging.
2. Install the exact native archive. Independently cargo install the CLI from
   the fresh source archive with locked/offline inputs, an external target and
   prefix, and proof that CLI/workspace compilation used installed source paths.
   Declared dependency artifacts may be reused; do not call that a clean build.
3. Run the packaged Miniserve qualifier without Git, bound to its explicit
   source-inventory digest. Refuse missing binding or changed source before
   compiler/owner effects. Never fall back to a checkout compiler or qualifier.
   Make both producing checkout paths unavailable during both owner workflows;
   restore and verify them afterward.
4. Each installed compiler must build Miniserve from the selected source and
   original public registry inputs in a newly owned bounded executor. Recheck
   CPU2/memory6GiB/zero-swap/PID512,3GiB work quota, immutable input mounts,
   loopback-only network, stopped setup helper and capability-free workload.
   Copy the actual release binary before releasing unchanged upstream tests.
5. Each owner must pass the frozen19 upstream harness counts:
   43,15,15,22,6,13,4,9,2,11,2,5,8,15,57,45,5,39,9; total325, zero failed/ignored.
   Require all eight existing named HTTP controls, not merely eight arbitrary
   lines. Invalid config, wrong listener, wrong digest and authentic ARM64 must
   preserve the old selection. Stale runtime must refuse before marker effects;
   restored selected runtime and source/snapshot-unavailable verification pass.
   Registry snapshot/selected-member corruption likewise refuses before effects.
6. Verify source/package/CLI identities, unchanged upstream selected bytes,
   stopped owned containers/listeners, restored checkout paths and source
   inventory at completion. A changed installed member must refuse before a
   sentinel compiler writes its marker, then exact restoration must verify.
7. Review the exact CI source, archive/member hashes, both child receipts,
   registry/kernel/cleanup records and individual command outcomes independently.
   Publish compact scoped evidence and update the support matrix only after
   actual success. Preserve failed receipts; controls alone are not acceptance.

## Execution and retention

One focused manual Linux lane runs the two owner workflows sequentially.
Keep the existing combined4GB disk-growth/500MB reserve, per-command bounded
logs/deadlines and explicit external Cargo outputs. The whole qualification has
a60-minute deadline. No evidence/limit relaxation after observing failures.
Stop both owned executor records on failure; never stop another project's job.

Upload one bounded source/native package plus compact reviewed receipts and the
existing selected-state evidence, under a320MiB artifact ceiling and14-day
retention. Do not copy archives, extracted dependencies or raw owner logs to Intel.
Retain only compact reviewed evidence there. No automatic local deletion.

Commit/push this plan, then the minimal installed-mode/driver/workflow change
with focused source-integrity and contract controls. Allow one initial full run;
at most two repairs for demonstrated implementation/harness defects before
returning the exact unresolved cause. Do not repeat already accepted unrelated
Next or scheduler suites. G4 performance and owner-deferred applications retain
their existing status.

## Implementation preflight

The existing Miniserve qualifier now accepts an explicit installed inventory
binding, validates it before effects and around each command, and checks the
relocated compiler against packaged source identities. Installed mode refuses
checkout compilation/artifact fallback; ordinary checkout mode remains available.

scripts/qualify_installed_rust_build.py packages current source/native archives,
compiles a fresh installed-source CLI with declared reusable dependency objects,
and makes the checkout compiler/qualifier unavailable during both independent
registry-backed application workflows. It requires the frozen19 harnesses,
named HTTP controls, native refusal/replay checks and actual executor cleanup.
Changed installed source must refuse before a sentinel compiler marker.

[Focused Intel preflight](../acceptance/project-adoption/g5-installed-rust-owner-build-20261024/preflight.json)
passed62 cases across five suites, plus three Python syntax/two workflow YAML
checks and diff validation. Ten cases are new; a historical passed receipt is
used solely as a schema fixture, not new owner evidence. No new application build
has run or been accepted. The opt-in cargo-registry-installed-build lane reuses
the existing Linux workflow, keeps sequential execution and the4GB/500MB limits,
checks the320MiB evidence ceiling and stops only named owned containers.

Initial run40118364424 at a482888 failed workflow validation before any job.
GitHub reports that the nested miniserve job requests actions:read but the new
caller allowed actions:none. The first bounded repair adds only contents:read
and actions:read to that caller, matching the existing registry caller. YAML
and diff checks pass; no application, storage, resource or acceptance criterion
changed. [Failure record](../acceptance/project-adoption/g5-installed-rust-owner-build-20261024/startup-failure.json).

The repaired [run40118700332](https://github.com/roryscot/patamaps/actions/runs/40118700332)
at8c6de4 has started the owner workflow after toolchain and focused controls
passed. [Observed run/job handle](../acceptance/project-adoption/g5-installed-rust-owner-build-20261024/run-40118700332.json).
No actual owner success or acceptance is claimed from a running job. Follow
this same handle to a terminal result; the separate in-memory review is prepared.
The native G4 cleanup approval remains pending. One of two permitted repairs
has been used, solely for reusable-workflow permissions.


## Accepted scoped installed-owner result

[Run40118700332](https://github.com/roryscot/patamaps/actions/runs/40118700332)
at8c6de4 passed, including owned-container cleanup and the evidence ceiling.
[Independent review](../acceptance/project-adoption/g5-installed-rust-owner-build-20261024/accepted-40118700332/independent-verification.json)
matched all1,203 packaged source files to Git, both exact archive/engine
identities, all60 original application files per owner and874 retained registry
members per owner against456 unchanged Cargo.lock checksums. Both fresh
installations compiled the real owner and passed the same19 harnesses/325 tests,
eight named HTTP controls twice, four prior-selection-preserving refusals,
registry corruption before-effects controls, stale-runtime refusal, restored
replay and all owned-container shutdown. Source/checkout restoration and the
changed-installed-source-before-compiler marker check passed.

The source CLI was freshly compiled from installed paths with declared dependency
artifacts reused. Native/source compiler binaries were each63,040,536 bytes;
both compiler digests and both newly built application digests matched in this
single profile. This is not a general reproducible-build or performance claim.
Observed workflow growth peaked at3,474,575,360 bytes under the unchanged4GB cap.

The first independent inspection stopped at an erroneous extra40MiB read cap
for a development compiler. Package creation has no such40MiB binary limit.
The [corrected inspector](../acceptance/project-adoption/g5-installed-rust-owner-build-20261024/inspector-correction.json)
uses the already-frozen320MiB whole-artifact ceiling while retaining every source,
digest, ELF, kernel, correctness and runtime check. The first failure and its
source digest remain preserved. No owner workload, criterion or product limit
was changed or rerun for this correction. Both allowed repairs have been used.

One194,599,593-byte CI artifact retains the exact packages/states until
2026-11-07T18:21:52Z. About100KB of reviewed receipts/source are retained on Intel;
no archive or extracted registry tree was written there by review.
Complete OS/toolchain/test-fixture closure and production activation remain
outside this accepted profile. Native/Next actual-project G4 measurements remain
unaccepted; the separate native cleanup approval is still pending.
