# Retained benchmark controller

The benchmark controller now uses the already retained configured-provider
executable. A later rebuild of the shared target/debug CLI cannot change the
prepared controller bytes.

A fresh canonical guarded functional run passed all 13 existing measurement
controls, rebuilt the CLI, and prepared the original Axum source. With the
shared compiler path temporarily unavailable, the retained executable returned
the identical engine and computed the prepared owner input key. The shared
compiler's bytes and mode were restored; all 337 owner inputs, protected prior
records, plan, binding and tool/coordinator digests were independently checked.
The reservation finished and released; measured target/state remain absent.

The initial attempt passed controls/build but refused stale parent heartbeat
before creating measured work. The retry waited at most 15 seconds for a fresh
heartbeat; it changed no ownership criteria, policies or budgets. Both attempts
remain retained. No files were deleted by this follow-up.

See [independent review](review.json), its [source](review-source.py), and the
[preserved first refusal](initial-refusal.json). This is functional preparation,
not benchmark execution or performance acceptance. The database stop/benchmark/
restart window still requires its separate human approval.
