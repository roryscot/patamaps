# Actual-project development measurements

Status: planned; no new performance result is accepted. This implements the
original G4 measurement requirement separately from completed native parity and
the pinned installed Next runtime gate. The first workload is the already
qualified native Axum workspace. Next.js measurements remain a separate gate.

## Frozen workload and provenance

Use Axum commit fc78d5bcdb276bd6fb53cf2db55e91757eabb469 and its qualified
four-package, axum/ws profile. Reconstruct a new owner from the verified retained
source snapshot and the three captured workspace/policy/projection files in the
accepted native attempt. Verify those files against the original capture and
record every selected byte, working overlay and tool identity. The old temporary
owner currently lacks its source files; do not treat its surviving directories
as a usable checkout or alter it. Preserve the original snapshot, Git clone and
accepted state. Reuse the existing Rust capture/build/select/verify contracts.

The real source contains333 selected text inputs plus its retained context;
record the actual reconstructed counts/bytes rather than extrapolating timing
from a fixture. Add one explicitly described, doc-hidden public string constant
to axum/src/lib.rs for initial value cold and successive edits edit-1, edit-2,
edit-3. A tiny compiled Rust consumer must read that constant through the copied
Axum library and return the expected value. This is qualification instrumentation
in a derived source tree, not an upstream change or a new application. All459
existing library tests must still pass after initial and edited builds.

## Build and output contract

Use a freshly built, identity-checked Intel Patamaps CLI and Rust1.99.0. Keep
Cargo locked/offline, two build jobs, debug information disabled and incremental
compilation disabled, matching the previous qualified profile. Existing public
registry/toolchain inputs are explicit external dependencies, not hermetic ones.

Use one initially absent external Cargo target directory under the measured
work root across attempts. It is declared mutable compiler state with exclusive
output ownership. Reuse dependency objects normally; do not copy them into every
selected generation. Programs still compile source inside each native candidate.
Copy four library artifacts and the compiled consumer into an immutable bundle,
record their digests before verification, then run the existing library tests
and the consumer without modifying that bundle. Select those exact artifacts and
the generated four-package observation. Source-path changes may cause Cargo to
recompile local packages; record actual command evidence, not invented cache hits.

## Measurements and predeclared budgets

| Phase | Repetitions | Required result | Budget |
| --- | --- | --- | --- |
| Initial build | 1, with new target and state | New selected build,459 tests and consumer cold pass | At most900s wall time |
| Unchanged warm request | 3 | Same pointer/attempt/artifacts; verification not-repeated, cacheHits0 | Median at most30s; each at most60s |
| Source edit to verified selection | 3, values edit-1 through edit-3 | Changed input key and newly selected attempt;459 tests and matching consumer each | Each at most180s |
| Memory observation | Every measured child | wait4 raw unit and normalized bytes; calibration below | Largest reaped-process peak at most3GiB |
| Retained data | Before/after each timed phase, outside its timer | Logical bytes and allocated blocks, no followed links | New workload root at most2GB allocated; existing supervisor4GB run growth/500MB reserve/100GB retention also apply |

The comparison is between these three phases of the same retained workflow.
There is no alternative compiler/build-system baseline and no speed advantage
claim. Warm requests intentionally do not rerun application verification. Initial
build is cold only for the new application target/state: registry sources and OS
page caches are not cold or cleared. One initial trial and three later samples
cannot establish tail latency or a population estimate. A missed budget is a
failed or incomplete scoped measurement; do not loosen it after seeing data.

Reuse the per-child wait4/timing method in bench_phases.py with a retained-output
option. Darwin reports ru_maxrss in bytes; Linux reports KiB. Retain raw values,
normalize explicitly, and calibrate separate0/64MiB touched allocations before
measurement; require the peak difference between48MiB and96MiB. This is the
largest reaped-process high-water mark, not summed concurrent job memory, phase
allocation, or an enforceable native memory cap. Retain monotonic wall/user/system
measurements, commands, exit status, output digests and actual source/tool/engine
identities. Keep raw child logs private; public records contain bounded numeric
results and reviewed fixed summaries.

## Exclusive admission and retention

Prepare tools under the existing functional supervisor, then queue the measured
work separately with BUILDCTL_PHASE=benchmark through the same canonical
run-project.mjs patamaps entry point. A functional lease cannot be promoted.
Verify the live owned benchmark reservation, exclusive native enforcement and
absence of other active reservations before and throughout measured phases.
Refuse when an unreserved container or uncertain ownership remains. Do not stop
another project's workload or bypass storage admission. Preserve interactive
headroom and record the machine state; unmanaged OS/background activity is not
claimed to be absent. Do not run CI or another build concurrently on this Intel
host during measured intervals.

Retain every generated file/attempt/calibration/log under the inventoried project
work root. Extend the existing collector to use exclusive-created retained files;
no TemporaryDirectory/TemporaryFile cleanup is permitted for this run. No file,
cache, container or old state is deleted, no storage limit is raised, and no new
VM or scheduler implementation is introduced. Compact reviewed receipts belong
in Git; do not duplicate dependency trees or publish raw application artifacts.

## Acceptance and sequence

1. Commit/push this frozen plan; inspect current storage admission and source/tool
   prerequisites. Preserve every blocker as a scoped result.
2. Extend the existing collector with retained files and test timeout/nonzero,
   bounded logs, RSS-unit handling and ownership-preserving cleanup. Prepare a
   reusable Axum measurement driver around existing native commands and profiles.
3. Run focused controls, then prepare the current native CLI/source under the
   existing functional guard. Commit/push the verified implementation.
4. Acquire a new exclusive benchmark reservation and execute the frozen phases.
   Stop on source/tool mismatch, failed correctness checks, lost ownership,
   unexpected process/container activity or policy/budget refusal.
5. Independently check raw samples, calibration, units, source changes, all459-test
   summaries, selected artifact/consumer digests, no-op semantics, exclusivity and
   restored original inputs. Commit/push compact passed/failed evidence and update
   the support matrix. Only this actual Rust workload may be accepted from it.

Remaining G4 Next.js-scale measurements and all other open owner/deployment
requirements retain their original scope. No release, registry publication,
production activation or blanket performance/support conclusion follows.
