# Resume the original project-adoption goal

Status: reservation recovery and resource readiness complete; the one approved
additional W0 no-op/idle/SIGTERM case now passes independent review. No further
case is authorized by that completed extension. The full G0–G6 scope in
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

Steps1–4 below are complete at the scoped
[single-extension result](../acceptance/project-adoption/original-owner-watch-single-extension-20261028/receipt.json).
Step5 was separately approved and run: all observed owned processes stopped,
but automatic lease release failed its60-second criterion. Its
[independent failure review and approved one-record recovery](../acceptance/project-adoption/original-owner-active-parent-death-20261028/receipt.json)
preserve that failure and the accepted selection. Full W0/W1 and all original
adoption gates remain open.


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
5. Review active-parent-death ownership and its case budget after the no-op
   pass. The separately approved initial case has now run and failed automatic
   lease release. Any future case must first resolve the ownership boundary,
   observe the real native child before killing only its test-owned parent,
   then confirm cleanup and release within the unchanged60-second bound.
   A prepared script or successful idle shutdown is not crash-recovery evidence.

The detailed W0/W1 contract remains in
[the watch plan](2026-10-28-original-owner-watch.md). No acceptance criterion is
removed or replaced by this order of work.

## Resource observation and admission checkpoint

The [executed readiness review](../acceptance/project-adoption/resource-readiness-20261028/receipt.json)
records three metadata samples over30.212s: available-space range3,231,744bytes,
net change-208,896bytes, unchanged swap usage and zero swap-in/out deltas.
The two selected known disk-image metadata records stayed unchanged. This is
a short quiet interval; it does not identify the earlier writer, establish
future stability or prove the full native verifier's memory bound.

The unchanged canonical run-project.mjs patamaps check subsequently exited0:
47,590,436,864bytes available;93,673,992,192 retained allocation upper bound;
2,326,007,808bytes remain under100GB after the full4GB reservation. It inspected
2,087 configured roots and took234.052s. That is admission-inspection elapsed
time, not an application performance measurement.

Preserve the earlier local inspection failures:10s and60s CPU limits stopped
two inventory checks before any admission result; a later wrapper discarded
the result when the root list exceeded64KiB. The corrected capture retains the
full root list privately and publishes only budget figures. These are inspection
failures, not Patamaps qualification failures or confirmed quota refusals.

Current evidence supports proposing exactly one guarded W0 extension using the
unchanged prior observer driver. The user subsequently granted exactly one extension, which
[passed independent no-op/idle/SIGTERM review](../acceptance/project-adoption/original-owner-watch-single-extension-20261028/receipt.json).
Each actual native call obtained its own fresh reservation and both released.
That extension is consumed; the admission checkpoint does not reserve future
resources or authorize another case. Keep the original
bounds and one-attempt/no-automatic-repair scope in the next increment above.
The earlier resource cause and all remaining W0/W1 acceptance stay open.

## Cancellation ownership is the next unresolved boundary

The actual parent-death result separates observed process cleanup from the
failed automatic-release requirement. The unchanged guard retained a cancelled
native lease because an unrelated container was already running. Three complete
stop inventories and explicit one-record human approval subsequently allowed
[metadata recovery](../acceptance/project-adoption/original-owner-active-parent-death-20261028/recovery.json);
the failed guard remains archived byte-for-byte.

Do not repeat the unchanged test expecting a different result or weaken its
60-second criterion. Review enforceable native isolation from existing container
access, or prepare a separately approved isolated service window if retaining
the current guard. Neither option is implemented/qualified by this checkpoint.
The earlier no-op/idle/SIGTERM pass remains valid; manual recovery is not proof
of automatic parent-death cleanup. Other original G0–G6 work remains required.

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
