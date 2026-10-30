# Ownership timeout diagnosis and exhausted phase budget

The approved216-file removal completed and was independently verified; no more
files were deleted. Fresh normal admission succeeded for the original frozen
phase and both bounded repairs. All three stopped at ownership validation
before any actual authentication service or test.

Repair1 retained the same ownership probe/validator/30s deadline with private
diagnostic capture. Its traceback proves the timeout branch; no underlying
Node error was emitted. Read-only component inspection then observed:
full Scheduler.status exceeded30s; a separate Scheduler.requests sample took
20.727s; activation inspection took0.070s; memory/Docker queries took<0.1s.
These are functional diagnostic observations, not isolated benchmarks.

The final repair retained all reservation enumeration/native-finalization,
current heartbeat/cancellation, owner identity/ancestry, resource telemetry,
container checks and the same validator/deadline. It omitted only historical
display metadata not consumed by the native proof and changed no global tool.
It nevertheless timed out. Therefore display telemetry alone is not an
established complete cause; the precise remaining slow step is unresolved.

The phase's initial+2 repair budget is exhausted. Do not retry, increase a
timeout, assume other reservations absent, drop ownership checks, reset the
budget under a new directory, or claim application/authentication acceptance.

Smallest next investigation: add stage-level timings to read-only status
collection, identify the actual worst-case reservation/history cost, and fix
its latency while preserving every ownership/concurrency/cancellation/resource
criterion and historical record. A concrete new bounded qualification proposal
and explicit budget extension are required before another application attempt.
Existing native-I3/dynamic/benchmark decisions remain separate; no parallel or
production activation follows. No additional cleanup is currently requested.

All three reservations finished/released. No stale lease remains. Original
owner source, selected endpoint generation, API inputs and unrelated database
remain unchanged. The frontend endpoint milestone remains accepted separately.
Real auth, permissions, browser negative sessions and full adoption remain open.
