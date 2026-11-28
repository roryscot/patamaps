# Wargame owner browser results with a retained-tree failure

The retained Intel Wargame candidate used the same Rust API binary,
Next build ID and generated-bundle pointer as the
[earlier real network qualification](../g6-wargame-production-network-2026-10-18/receipt.json).
It ran the original Playwright config and both original spec files
through Wargame's candidate guard and unchanged production server
launcher in lab mode. Chromium headless shell revision 1248 was
installed by the pinned Playwright package and reused on the retry.

The first run timed out after 120 seconds before any test. The harness
had passed the lease token without the matching owner PID and directory,
so the nested server queued behind its parent. The second run passed
the complete lease binding. The scheduler cancelled the stopped queued
request, and both original test servers used the inherited guard.

Playwright exited 0 on the second run. Independent review confirmed
11 desktop and 11 narrow cases passed, with zero failed, skipped or
flaky cases. The wrapper exited 1 because its unchanged-tree check
caught 24 new Next APP_PAGE route-cache files. Every one of the 2,315
pre-existing production tree entries remained identical. The strict
whole-tree check remains failed, with the new cache outputs retained.

Both runs stopped their owned listeners. The exact lease archive and
process inventory confirm release. The unrelated database, Wargame
source inputs, selected binary, build ID and bundle pointer were
preserved. This records the real lab browser outcomes and the separate
retained-tree failure. Managed identity, persistence, installed
workflow and full owner acceptance remain open.
