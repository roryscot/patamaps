# Wargame native reference failure on Norway

The exact focused owner command failed during the FIFO reference plan.

```sh
node scripts/check-persistence.mjs --native-test=boundary_reference::full_reference_boundaries_storage_recovery_and_ledger_are_exact
```

The test ran for 421.49 seconds against isolated PostgreSQL 18.6 and reported
one failure. The server log records one connection termination for an idle
transaction. The Rust test reported a broken pipe from `advance_boundary`.
The last recorded checkpoint is FIFO tick 100. The exact idle statement and
the failing tick are unknown. The reference suite has two plans, FIFO and
priority. No completed reference artifact was produced.

The focused retry reused the existing executable. The independent review
rehashed 147 frozen inputs and confirmed the test exited before its two-hour
deadline. The existing five-second PostgreSQL idle transaction timeout and
4 GB growth cap applied. The guard observed 111,587,328 bytes of growth, exited
with status 1 and released its reservation. The owned database stopped, the
tool image detached, and the unrelated database identity matched its pre-run
record.

The earlier native run's 116 passing cases and its interrupted reference case
remain separate evidence. Full native persistence and owner acceptance are
open. Candidate operations between statements include frame decoding and
validation and JSON serialization. Timing those phases alongside the server
session would help identify the idle interval before attempting a repair.

[Independent review](review.json) · [Earlier managed and native evidence](../wargame-owner-managed-and-native-persistence-20261106/README.md)
