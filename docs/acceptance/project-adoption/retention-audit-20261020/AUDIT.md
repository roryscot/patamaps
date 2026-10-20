# Intel retained-data audit

Scope: Patamaps qualification outputs and the roots counted by its storage supervisor. No files were deleted during this audit. No application source is published by this report.

The refused run recorded 100,614,709,248 retained bytes, including 1,970 roots (1,965 scratch roots). These are conservative path-allocation totals, not unique physical storage. Separate `du` observations are a later snapshot and must not be added as a precise decomposition of the earlier guard total.

| Group | Observed allocated GB | Decision |
| --- | ---: | --- |
| Project-adoption runs | 30.43 | KEEP selected/current artifacts, private application snapshots, unique failures and receipts; do not bulk publish or delete |
| Capability installations | 11.20 | EXTRACT: retain each distribution archive, installed binaries and acceptance records; propose only extracted files verified against exact retained archive members |
| Cross-stack runs | 10.51 | KEEP fixture source, selected acceptance and unique failures; older full trees need a separate comparison before deletion |
| Managed quota workspaces | 9.29 | KEEP backing images and outputs; old failed quota is busy in virtualization, so no forced unmount/removal |
| Resource-reservation qualification | 3.83 | KEEP compact 57-unit/22-control evidence and stopped-workload proofs; mounted workspace retirement remains separate |
| Crates packaging work | 5.56 | KEEP: separate in-flight/release preparation must not be treated as disposable by this audit |
| target/debug/deps | 8.28 | REDIRECT: exact compiler-output deletion proposal; no verified backup, recompilation needed |
| Other compiler outputs | 3.5 | KEEP for now; installed/release binaries are not covered by the debug-deps proposal |

Repository routing: public Patamaps receipts, guard source patch, retention implementation and this audit belong in `roryscot/patamaps`. Existing Seeder/Wargame Git histories remain the authority for their application source. Their retained private working snapshots and raw logs remain on Intel; no claim is made that GitHub preserves their ignored data. They are excluded from deletion. No application acceptance record is copied into a different repository as a current-source pass.

Exact machine-local deletion proposals are linked in the private Intel handoff and identified by SHA-256 in their summaries. Approval is pending. The compiler-output proposal has 5,879 files; four excluded entries remain. Archive-identical extraction verification is recorded separately after it finishes. All inventories are proposals, not authorization.

Retention changes: native per-state attempt ceiling (default 8, max 64), no-op at capacity, refusal before copying another candidate, and supervisor full-run headroom reservation. Test/installation state is tracked separately; no automatic purge or approved-limit increase is introduced.

Archive verification completed: 118,202 files / 7,764,934,656 allocated bytes match their exact members in nine retained source archives; all archive digests match distribution records. No restoration was exercised. Together with the 5,879-file compiler proposal, this is 124,081 files / 16,045,592,576 bytes of summed allocation. Neither inventory is deletion authorization.
