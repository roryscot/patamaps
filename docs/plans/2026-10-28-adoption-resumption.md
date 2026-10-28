# Resume the original project-adoption goal

Status: prepared after the explicitly approved reservation recovery on
2026-10-28. No new qualification attempt has started. The full G0–G6 scope in
[the adoption plan](2026-10-15-general-project-adoption.md) remains unachieved;
completed C01–C19 native parity remains a separate milestone.

## Recovery complete

The [executed read-only review](../acceptance/project-adoption/approved-reservation-recovery-20261028/receipt.json)
confirms reservation 7dcd23fe-8910-4eb2-8533-d0227fb31f13 is finished and released.
The original request, compatibility lease and failed guard were archived with
their exact reviewed hashes. Only the four reviewed reservation fields changed.
The guard still records exit75/completed=false. At review, no active or queued
reservations remained; the same unrelated database was running and ready.
No file deletion, service interruption, limit change or qualification retry
occurred. This closes the ownership barrier, not the failed watch qualification.

## Next bounded increment

1. Establish resource readiness using read-only host observations before asking
   to extend the exhausted watch budget. Observe volume-available bytes,
   memory pressure/swap and identities of relevant running workloads over one
   bounded interval. Reuse existing scheduler and OS metadata commands; no
   unbounded filesystem scan, new diagnostic framework or stress workload.
   Any collector must bound its CPU, memory, output and wall time; uncertain
   enforcement keeps native diagnostic work exclusive. Record unreadable
   process data explicitly. Do not stop unrelated services.
2. Review the discrepancy between volume-wide free-space loss and owned output
   growth. The failed guard observed a 4,284,735,488-byte drop against its
   4,000,000,000-byte allowance; it did not identify a writer. Swap, other
   writers and filesystem accounting are hypotheses, not established causes.
   A later quiet snapshot does not explain the earlier event. If the evidence
   still cannot support a safe retry, report the specific missing observation
   or propose one scoped environmental remedy. Any service interruption,
   deletion or policy change requires its own concrete approval.
3. Request exactly one additional unchanged-owner W0 no-op/idle/SIGTERM attempt,
   with no automatic repairs, only after documenting why the environment is
   ready. The initial-plus-two-repair budget is exhausted; recovery approval
   does not extend it. Preserve the existing 900-second native, 1,800-second
   update and 2,100-second case bounds, 4GB/500MB/100GB storage policy and
   native-exclusive fallback. Reuse the qualified installation and accepted
   owner output; no fresh application build, dependency copy or new selection.
4. On authorization, freeze the exact installed helper, driver, CLI, selected
   pointer and input identities before execution. Require both independently
   queued native calls, a completed watch-update event, at least two idle poll
   intervals and exit130 on SIGTERM. Recheck preserved selection/attempt/ledger
   and owned-process absence. A failed run stays failed; stop at the one-attempt
   budget and do not retry or release uncertain ownership automatically.
5. Only after that pass, review the separately prepared active-parent-death
   case and its authorization/budget. It must observe the real native child
   before killing only the test-owned parent, then confirm cleanup and release
   within the frozen 60-second bound. It has not run. A prepared script or
   successful idle shutdown is not crash-recovery evidence.

The detailed W0/W1 contract remains in
[the watch plan](2026-10-28-original-owner-watch.md). No acceptance criterion is
removed or replaced by this order of work.

## Continue the full adoption plan

| Required work | Dependency and evidence still needed |
| --- | --- |
| W1 changed-generation development | Fresh private working owner/external state, independent expected generated/consumer bytes and frozen attempt budget. Actual failed/raced/cancelled builds must preserve selection; a valid edit must select and run the expected consumer. |
| Original-owner backend and browser behavior | Resolve the separately exhausted API-import budget before another import attempt. Use actual declared startup/configuration. Authenticate actual owner/user/guest flows and permissions; verify edited label visibility. Do not substitute marker bytes, private credentials or a borrowed database. |
| Rust and Next performance | Revalidate current compiler/harness bindings and cold-state preparation. Obtain the separate quiet-window decision before exclusive cold/warm/edit, RSS calibration, retained-disk and unchanged correctness checks. Functional elapsed time is not a benchmark. |
| Framework/configuration, deployment and installed owners | Close the remaining named support-matrix rows with actual retained/installed owner evidence, preserving explicit source, config, dependency and tool boundaries. Earlier scoped public-project passes do not replace incomplete Wargame/Seeder workflows. |
| G6 support/release decision | Reconcile all original requirements with current receipts, including failures and unavailable gates. Claim completion only when the required owner workflows and measurements are proved together. |

Reuse accepted results whose bindings still hold. Add product changes for
reproduced product defects; collector defects alone do not justify product
changes. Keep compact safe evidence and verified Rory commits/pushes. Private
source, raw process inventories, database data, bodies and logs stay private.
