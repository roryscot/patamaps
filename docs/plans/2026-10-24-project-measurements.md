# Actual-project development measurements

Status: prior driver controls and historical native preparation passed.
The retained-state layout repair passed all28 focused Linux controls and the
actual Intel native refusal/selection/verification/no-op check. Fresh functional
Axum preparation with the current compiler is in progress. Current-compiler preparation and the separate approved
quiet exclusive window are still required before actual measurements. No new
performance result is accepted. This continues original G4 separately from
completed native parity and pinned installed Next runtime qualification.

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
| Retained data | Before/after each timed phase, outside its timer | Logical bytes and allocated blocks, no followed links | Combined work and external retained state at most2GB allocated; existing supervisor4GB run growth/500MB reserve/100GB retention also apply |

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

Retain generated controls, target, calibration and logs under the inventoried
project work root; native attempts live under the explicitly bound external
retention root. Count both roots in the unchanged allocation budget. Extend the existing collector to use exclusive-created retained files;
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


## Collector implementation and initial admission history

The existing bench_phases.measured function now accepts retained output paths,
a monitoring callback and bounded logs; it records exact-child wait4 usage and
private stdout/stderr/stdin without deleting files or publishing stderr text.
It reserves its measurement record before command effects and retains failure
records. Explicit RSS units reject unsupported platforms/values; failed launch
records use unknown memory rather than inventing a zero observation. Darwin
exit-race cleanup reuses the existing qualified process-group helper. Recorded
command arguments must be nonsecret; private input belongs in retained stdin.

[Focused native controls](../acceptance/project-adoption/g4-project-measurements-20261024/collector-preflight.json)
passed9 cases on Intel: success/privacy, nonzero, timeout, monitor cancellation
with an unrelated session preserved, log refusal, existing output/record refusal
before effects, launch failure and RSS units. These small controls do not execute
the64MiB calibration or an application benchmark. The opt-in Linux control lane
checks the same platform-sensitive collector without heavy application builds.

[Storage admission](../acceptance/project-adoption/g4-project-measurements-20261024/storage-admission.json)
refused with exit75 for insufficient retained-output headroom. No native compiler
preparation or measurements ran. The earlier approved13,132-file inventory now
has10,924 absent paths and2,208 changed files, with zero unchanged entries; that
approval cannot authorize deleting the regenerated files. All files and limits
remain unchanged by cleanup. Prepare an exact current redundant-data review
before requesting further deletion approval; preserve the current compiler cache
needed for preparation. The measurement driver and actual performance gates
remain unimplemented/unrun at this checkpoint.


A targeted follow-up found mounted, finished quota volumes whose backing images
and mounted contents both contribute to conservative retention accounting.
Actual container state/labels confirmed the two owners stopped; normal detach
returned exit16 and a virtualization process has a filesystem handle. No force,
container stop/deletion or image deletion followed. [Diagnostics](../acceptance/project-adoption/g4-project-measurements-20261024/storage-followup.json).
The independent running container remains untouched and also precludes the
frozen exclusive benchmark until an appropriate quiet window is authorized.

The alternative [exact cleanup review](../acceptance/project-adoption/g4-project-measurements-20261024/publication-cleanup-review.json)
proposes3,491 generated compiler files in five old alpha-publication dependency
directories, totaling4,592,123,904 allocated bytes. The full inventory remains
under .tools/retention-review-20261024-publication-deps/, outside the package
payload.845 excluded entries, all directories, current target cache, source,
archives, installed executables and receipts remain. All ten frozen crates
match their publication hashes. Compiler-file backup/recompilation/exact-byte
recovery have not been verified. This changed list needs fresh user approval;
no proposed file has been deleted.


The [Linux collector run40077251568](https://github.com/roryscot/patamaps/actions/runs/40077251568)
at a322f65 also passed all9 controls; [verified log/source summary](../acceptance/project-adoption/g4-project-measurements-20261024/linux-collector-controls.json).
The same collector/workflow source digests match the Intel preflight. No resource
warnings occurred. The source-only implementation and both platform controls are
verified; actual calibration, real-project driver/builds and timed acceptance
remain pending. The exact3,491-file publication-cache deletion request is open;
none of the proposed files has been deleted and no unrelated container has been
interrupted. Fresh approval for this inventory remains pending.


## Real Axum driver checkpoint

The source-only coordinator in scripts/bench_axum_retained.py and trusted build
helper in scripts/bench_axum_build.py implement reconstruction, captured-config
checks, pinned tools/environment, retained logs, source edits, copied immutable
artifacts, all459-test receipt checks, unchanged selection checks and restoration.
Functional preparation and benchmark execution require separate live canonical
reservations. The coordinator checks supervisor identities and live ownership,
refuses other active reservations or any running container during measurement,
and checks the frozen disk/wall/RSS budgets. A final native selected-build
binding check is outside the seven performance intervals. Passing driver gates
does not set actualBenchmarkAccepted; independent evidence review remains required.

[Intel driver controls](../acceptance/project-adoption/g4-project-measurements-20261024/driver-preflight.json)
passed23 checks:13 focused Axum contract/refusal cases and10 collector cases,
including graceful guardian cancellation without leaving its owned workload
running. Source parsing and the JavaScript ownership-probe syntax also passed.
The opt-in Linux lane discovers both test files. These fixture checks do not
establish that a real build/preparation or any performance budget has passed.

Native admission remains exclusive. Interactive-memory telemetry uses macOS
normal memory-pressure status and its reported free percentage, reduced by one
percentage point before estimating capacity against the existing interactive
reserve. It does not treat bare free pages as available capacity and is not an
enforceable native memory reservation. The3GiB per-child observation limit remains
unchanged; other unmanaged processes and aggregate memory are not measured by it.

SSH to admin@norway was verified from the agent session. buildctl status showed
zero running/review-needed requests, while one running container was observed.
The previous storage refusal and exact3,491-file deletion proposal remain pending;
no listed data, container or policy was changed. Actual native CLI preparation,
RSS calibration and all seven real-project samples remain unrun. This measurement
work remains an integration enhancement beyond completed MetaMaps native parity.

The [focused Linux driver run40080670912](https://github.com/roryscot/patamaps/actions/runs/40080670912)
at84922fa passed all23 controls; only the control job executed. The
[verified log/source record](../acceptance/project-adoption/g4-project-measurements-20261024/linux-driver-controls.json)
matches the Intel control source and workflow. This adds platform verification
of the driver controls, with actual native preparation and measurements still
unrun and unaccepted.

## Historical native admission blocker after driver verification

A [fresh canonical check](../acceptance/project-adoption/g4-project-measurements-20261024/admission-recheck.json)
at51f285e again returned75: insufficient retained-output headroom. The installed
run-project entry point loads the approved policy and reserves its full maximum;
it exposes no per-job lower-growth option. No direct-engine substitute,
installed-control edit or policy change was used. No native preparation began.

The [actual Intel unleased-entry control](../acceptance/project-adoption/g4-project-measurements-20261024/unleased-entry-refusal.json)
exercised the installed supervisor imports and the coordinator entry point.
Preparation refused MEASUREMENT_OWNERSHIP_UNAVAILABLE before destination
creation. This adds a real refusal-path check; it is not a live-owned success,
application build, calibration or timed acceptance result.

The same retention/approval blocker was present at the fa50041 collector
checkpoint, the51f285e driver checkpoint, and this fresh check. Independent
driver controls are finished. The next required native preparation and measured
execution cannot proceed under the unchanged admission rules without an external
state change. The pending exact3,491-file inventory still has its original
digest; approval has not been exercised and per-file identities must be checked
again before any removal. A quiet benchmark window is a separate later
requirement; the unrelated running container remains untouched.


## Approved cleanup and native preparation (2026-10-25)

The owner explicitly approved the existing exact3,491-file inventory. The
[executed cleanup receipt](../acceptance/project-adoption/intel-native-resume-20261026/approved-cleanup.json)
and [independent review](../acceptance/project-adoption/intel-native-resume-20261026/independent-verification.json)
verify all approved identities/journal paths and their subsequent absence.
All845 excluded paths, five parent directories and ten independently rehashed
crate archives were preserved. The existing scheduler transaction and legacy
lease serialized cleanup and were archived afterward. Available space increased
by an observed4,055,404,544 bytes; physical gain is not guaranteed by the summed
4,592,123,904 allocated bytes. No other deletion or policy change occurred.

The unchanged canonical supervisor then admitted functional preparation.
Source7ebc10c rebuilt the current Intel CLI and verified enginea5d602de.
Historical compiler/state, retained snapshot, original335 source files/333 text
inputs and protected records passed their bindings. Explicit instrumentation
produced the new337-input measurement owner; configured tools, plan and
coordinator/supervisor digests were verified. Cold Cargo target/state remain
absent. Both preparation commands exited0, supervisor exit0 was observed and its
functional reservation fully released. This does not execute the frozen
application correctness, calibration or timing phases.

Measured child intervals were18.490s for CLI rebuild and10.445s for source
preparation. The outer supervisor interval was220.943s. Its difference includes
admission/accounting/finalization and other overhead, which was not isolated.
These are functional observations, not cold/warm/edit acceptance, an end-to-end
watch latency, or an enforceable native resource-cap claim.

The exclusive benchmark must queue again in benchmark phase. A single unrelated
database container is still running; no service was stopped. Its temporary
stop/run/restart requires separate approval. Every original timing, memory,
correctness, disk, ownership and restoration requirement remains unchanged.
Actual measurements, independent measurement acceptance, Next-scale measurement
and full original owner qualification remain open. JSON timestamps use UTC.

## External retained-state repair contract

The old work/state path lies beneath a Cargo.toml ancestor, which native
project-build refuses. Preparation now requires an explicit --state path inside
the project's existing registered retention root. Resolve and bind that cold
path, require an existing parent, refuse occupied/dangling paths, Cargo ancestors
and overlap with the work root, and persist it in preparation. Run consumes the
same bound path; old preparations without this field require fresh preparation.

Keep Cargo target and control files under work. Include both work and external
retained state in every before/after footprint, deduplicating shared inodes and
not following links. The original combined 2 GB allocation budget, all timing/RSS/
correctness budgets, four-package 459-test requirement and canonical 4 GB/500 MB/
100 GB policy remain unchanged. Bind projects.json with supervisor digests so
the accounted-state declaration cannot silently change after preparation.

Acceptance requires the focused state/refusal/combined-footprint controls and a
tiny actual native project-build layout check: the old Cargo-descendant state
must refuse nonzero with PROJECT_BUILD_STATE_ISOLATION before creation, while
the external resolver path must select, verify and no-op. The tiny check is a
layout fixture, not an Axum build, benchmark or measurement pass. Then perform
fresh actual Axum functional preparation with the current compiler. No quiet
window or database interruption is part of these functional checks.

The first [native functional verification admission](../acceptance/project-adoption/g4-external-state-20261027/intel-admission.json)
for this repair refused75 before any test/controller fixture started. Its
reservation finished and released; no policy or deletion changed. Python syntax
and diff checks passed. Use the existing focused Linux control lane for the
unchanged-interface/unit controls while keeping the actual Intel native layout
fixture and real Axum functional preparation explicitly pending. This does not
replace either native requirement or any measurement acceptance.


The [focused Linux run40518822369](https://github.com/roryscot/patamaps/actions/runs/40518822369)
atc742765 passed all28 measurement controls in0.707s; only the selected control
job executed. The [source/log-bound receipt](../acceptance/project-adoption/g4-external-state-20261027/linux-controls.json)
records exact producing source and unchanged local control digests. These unit
checks cover the external-state resolver/refusals and combined-root accounting;
the actual Intel native layout fixture, fresh current-compiler Axum preparation
and all real performance measurements remain separate acceptance requirements.


The [actual Intel layout review](../acceptance/project-adoption/g4-external-state-20261027/native-review.json)
now passes all18 focused controls and five command results: the old state refused
with PROJECT_BUILD_STATE_ISOLATION before creation, while the accounted external
state selected, verified bindings, and returned an unchanged no-op without
repeating verification. Independent review rehashed all seven fixture inputs in
three locations and the exact24-byte selected output. The supervisor exited0 and
released its native reservation. This is a layout fixture, not an Axum build or
performance measurement. Fresh real Axum preparation is queued separately.

[Two preceding fixture failures](../acceptance/project-adoption/g4-external-state-20261027/native-initial-attempts.json)
remain preserved: byte/text concatenation in the assertion, then omitted policy/
projection files referenced by the fixture plan. The latter refused before
candidate execution/selection. Neither demonstrates a product defect. The final
fixture includes those exact digest-bound files; no acceptance criterion changed.
The later canonical admission succeeded without further deletion or policy change.
