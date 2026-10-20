# Intel retained-data audit

Scope: Patamaps qualification outputs and the roots counted by its storage supervisor. The initial audit deleted nothing; the separately approved execution is recorded below. No application source is published by this report.

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

Supervisor installation verified: eight CI admission tests passed on source 3f82633 / identical-tree merge 572324e. Actual installed guard probe a7bff2e5 refused for insufficient headroom (exit 75) before launching its sentinel; no data was deleted and limits are unchanged. Native attempt-ceiling verification remains pending after the preserved canonical-number failure and correction.

## Approved execution and verified prevention

The user approved exactly the two inventoried lists. Exclusive maintenance rechecked inventory digests, file identities, archive hashes and job ownership before unlinking. It removed 124,081 approved files, no directories and no unlisted files. Nine recovery archives and four excluded compiler entries remain. See [completed receipt](approved-cleanup-completed.json). The summed allocation was 16,045,592,576 bytes; observed free space immediately increased by 3,421,507,584 bytes. APFS sharing and other filesystem activity prevent treating the allocation sum as physical reclamation. Rebuilding subsequently consumed space.

The earlier pending statements above describe the proposal stage and are superseded by this execution. Files outside those exact lists remain. Compiler outputs require recompilation; matching retained archive bytes were verified but filesystem restoration was not exercised.

The corrected source passed all five Linux capability CI jobs, including 27 native workspace tests and the three retention regressions. Intel rebuilt the development release CLI and independently passed all 27 workspace tests. See [CI receipt](corrected-native-ci.json), [Intel build](native-retention-build.json) and [artifact identity](native-retention-artifact.json). Older installed distributions remain unchanged.

A sampled old extraction contained 822,896,360 logical bytes under docs/acceptance. The source packager had copied historical generated evidence into every new distribution. It now retains required code, tests, fixtures and vendor inputs, plus bounded inline-Markdown-linked evidence. It refuses above 128 MiB total source payload, 16,384 source members, or 32 MiB / 512 linked evidence files. Directory references select an explicit index or receipt rather than a recursive copy. Existing historical records are not deleted.

[Local packaging verification](bounded-package-verification.json) passed 13 scope tests, checked 115 guide/plan file links, matched every inventory byte to the checkout and produced byte-identical source/native archives twice. Source payload was 75,367,286 bytes, compressed source archive 8,958,193 bytes. This receipt binds the exact precommit source hashes; installed-consumer CI for the packaging change is a separate gate. Production parallel execution remains disabled.
