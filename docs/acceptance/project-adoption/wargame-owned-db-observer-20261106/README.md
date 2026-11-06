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
