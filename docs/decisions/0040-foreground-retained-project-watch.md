# Foreground retained project watch

Status: implemented; native controlled lifecycle and all four Linux CI jobs passed at f2bdeb8 (run 38872872081).

The example-specific development loop is insufficient for arbitrary owner build
plans. Reuse project-build-input-key and project-build; keep capture, admission,
command execution, artifact snapshots and atomic selection in Rust. The
foreground Python controller supplies only polling, debounce, policy-runner
routing, event reporting and ordinary process lifetime management.

Start outside any allocating lease. Each update runs through the explicit policy
prefix. No runner means refusal unless the Intel development environment supplies
the installed supervisor. An inherited allocating token refuses. A busy/pause/
capacity exit75 is retained as a failure and never automatically retried for the
same observed key. Restart or a declaration change is an explicit retry boundary.

The controller watches its actual parent. Small wrappers watch actual parents on
both sides of the policy runner, so a detached runner child is also stopped after
abrupt runner loss. Each wrapper owns only its newly created ordinary child group;
graceful stopping has a bounded escalation. Independently detached, adversarial or
externally owned processes are excluded. Outputs and partial attempts remain.

A zero runner exit is insufficient: native selected-build binding verification
and a matching current declared input key are required before reporting a
completed update. This repeats structural/artifact verification, not application
runtime commands. The underlying native build report distinguishes actual command
execution from no-op verification not repeated.

Controlled Linux CI uses a kernel-lock runner fixture inside its existing
isolated resource lane. That tests routing/lifetime and does not establish Intel
storage-supervisor acceptance. Native Intel controls use its actual installed
supervisor for every allocating update. Parent/runner death, signal handling and
failure retention must be measured rather than inferred from process code.

The scoped workflow is not complete application context/dependency capture,
arbitrary readiness/HTTP semantics, real-project performance, deployed behavior
or installed-consumer qualification. Those G4–G6 requirements remain open.

Inspection deadlines are owner-configurable with --inspection-timeout-ms,
1000..3600000 milliseconds, preserving the 30000 default. The same bounded
budget applies separately to input observation and selected-binding verification.
A timeout still refuses the update; it does not retry the same failed key or
skip native verification. Controlled subprocess checks cover both timeout paths,
success with an explicit budget, invalid declarations and unchanged key matching.
This is budget configurability, not measured native watch/performance acceptance.


An internal opt-in __guard-container OWNERSHIP_JSON path is separately qualified
by [seven managed controls](../acceptance/project-adoption/g3-cargo-registry-context-20261023/container-ci.json).
It accepts exactly one never-started container with a valid frozen ID/token and
matching Docker owner label, derives docker start --attach internally and stops
that container through the existing stop_owned helper before ordinary attach
process cleanup. Changed ownership refuses cleanup; a heartbeat or exited attach
process is never proof that the container stopped. The qualification observes
actual Docker Running/Pid state, including owner SIGKILL and recovery of an
observed survivor from an independent matching ownership record. It removes no
objects. This path is not invoked by the default foreground watch loop, does not
auto-discover containers, does not enforce arbitrary owner build reservations,
and does not activate concurrent execution. Ordinary __guard behavior and its
existing regression controls remain intact.
