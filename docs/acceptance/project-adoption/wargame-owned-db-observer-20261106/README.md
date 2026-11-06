# Wargame database observer fixture on Norway

A socket-only PostgreSQL 18.6 fixture exercised the read-only observer under
the existing Wargame native guard. A separate synthetic client opened a
transaction, ran a known query, and left it idle. The observer reported
24 samples with the expected query label, including one at 4.975 seconds.
PostgreSQL terminated the client at the existing five-second setting. The
observer excluded its own session, returned no query text or parameters,
and detected server shutdown.

The first fixture stopped before starting PostgreSQL because its version
assertion expected the output to end at the version number. The corrected
check matched the exact version with the Postgres.app suffix present. The
original failure remains in the local run record. Independent review
rehashes both corrected fixture inputs and confirms that both reservations
released. The isolated database stopped, the tool image detached, and the
unrelated database matched its pre-run identity.

This fixture qualifies the diagnostic mechanism. It exercises no Wargame
application assertion. The exact [reference failure](../wargame-owner-reference-db-timeout-20261106/README.md)
still needs correlation with a traced owner run.

[Independent fixture review](fixture-review.json)

## Full focused owner reference passed

The unchanged owner command passed under the existing guard.

```sh
node scripts/check-persistence.mjs --native-test=boundary_reference::full_reference_boundaries_storage_recovery_and_ledger_are_exact
```

FIFO and priority each completed all 864 ticks with 2,000 orders. The test
checked native equality, independent terminal ledgers, cold recovery, and
all 866 stored history entries per plan. It exited successfully after
6,684.57 seconds, within the two-hour deadline. It reused the exact
executable from the earlier failed attempt. Independent verification
rehashed 150 frozen inputs and confirmed both completed plan artifacts.

The observer collected 32,335 samples and recorded no idle transaction at
or above its two-second threshold. The earlier five-second timeout did
not recur and its cause remains unresolved. The guard observed
1,392,017,408 bytes of growth, exited successfully and released. The
isolated database stopped, the tool image detached, and the unrelated
database matched its pre-run identity.

The earlier run's 116 successful cases and this focused success cover all
117 named native cases across separate invocations. The original aggregate
failure and focused timeout are preserved. This run does not supply a
single successful full-suite invocation, performance measurements, or
fresh installed Wargame owner acceptance.

[Independent reference review](reference-review.json)
