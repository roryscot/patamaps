# Approved database-port 18866 attempt — owned isolation profile refused

Exactly one attempt was approved against frozen manifest
f00a7525a3aa101a28706077d39a8a01685acd2ea081a5bf4791b8bd70ff91cb.
All 421 inputs, 387 original API sources and 2 interpreter executables matched
before/after. The prepared source revision is 1585f84; actual launch revision is
2cf5196bcefe42a2094e30ffd9d60f6dbacb8108. All three required ports were free
before launch; the driver's original port check also passed.

The existing heartbeat wait accepted its third proof after two stale samples;
the original validator and full probe were unchanged. The owned pinned
PostgreSQL container started, passed readiness and used exact inspected 1 CPU,
512MiB/no swap/128 PIDs/read-only-root/nonroot 501:20/no-capabilities/no-log limits.
Its port was 127.0.0.1:18866 and only its three declared binds were mounted.

The next migration wrapper exited 65. Preserved stderr identifies the failure:
sandbox-exec: host must be * or localhost in network address.
The owned profile used (local ip "127.0.0.1:18765"), which the parser rejected.
Python/bootstrap and the original migration code never executed. The absence
of controls-migrate.json and all seed/server outputs corroborates that boundary.
No users were seeded; no API, HTTP auth case or browser case ran. This is a test
configuration failure. Real application authentication/permissions remain
unverified; no application migration defect is established.

Guardian cleanup stopped the exact owned container 67842c21a033ce700cc7b53e2a115d1ef41c12711e7305cd375b55f17aec4791.
Independent inspection confirmed stopped/PID 0 with matching ownership labels,
image, mounts and limits. All test ports 18765/18866/13000 had no listeners.
Protected Advocates database id/start/restart identity remained unchanged.
Owned cluster data remains: 47,927,296 allocated bytes/1,267 files at post-run
review; this is a final observation, not a peak or hard filesystem quota.
Generated credentials, raw logs, container and data remain private and preserved.
No deletion, policy edit, unrelated service interruption or automatic retry ran.

Request 8ed098c4-e093-4050-9086-1473983cc97d finished/released. Guard
8c5308e9-b52c-49fb-b63a-895f2eacabaa and supervisor exited 1, completed=false.
Guard record digest:
5de9ae7e1139a2098529d9c672226c1af36fb20af9ba7efc5b427e9dd6e8577a.
All 28 prior failed-record preimages and all 421 frozen bindings matched.
Native exclusive/4GB growth/500MB reserve/100GB retention stayed unchanged.
No ownership probe was rerun during postprocessing.

Executed checks: independent result reviewer, Docker stopped-state/actual
limits/mount inspection, listener closure, protected database identity, old
failure digests and complete frozen rehash; original validator applied only
to saved proofs; parser-error and bootstrap-boundary review; stopped owned
data inventory. One saved-review invocation initially used an incorrect
relative path from SSH home; no reviewer executed then. The absolute-path
invocation passed. Application execution was not repeated.
The browser cleanup field remains unexercised because that branch never ran.
The actual initial-plus-two budget and both one-attempt extensions are consumed.

The [next proposal](proposed-localhost-profile/PROPOSAL.md) is NOT APPROVED/NOT RUN.
It changes the three owned profile host selectors to localhost with the SAME
exact ports. That selector permits IPv4/IPv6 loopback; actual API/database bind
addresses and HTTP URLs remain 127.0.0.1. The original deny-all-other-network,
other-port/outside-write/dotenv denial checks and all auth assertions remain.

It also adds a single 10s profile parse/execution check with pinned Python -c pass
before generating credentials/creating another DB. This imports no original API;
64KiB per recorded stream, excess causes refusal with lengths/digests retained.
A parse-check failure stops the phase without automatic repair or another DB.
The extra check fits inside the unchanged 600s service deadline. The installed
Apple profile example supports selector spelling; no corrected profile was run.

Preparation only: Python AST/Node --check, 422 input rehashes and normalized
payload comparison passed. Public patch shows all changes; the original API/
bootstrap/frontend code remains unchanged. Frozen manifest SHA-256:
42cf17ef56ad3f5e9f0c72e385f38d159c1a55b25f5b0e0b2e15fa4de2f317c1.
One separately approved application attempt is proposed, with original 12 HTTP
and five browser cases and all existing resource/deadline limits. No installed
safeguard change, global activation, unrelated interruption or deletion follows.
Full G0–G6 adoption remains unachieved.


The profile correction was separately approved and executed. Its [profile-pass/database-startup-failure result](../services-localhost-profile-proposal-20261030/README.md) preserves the accepted syntax check and subsequent unknown database exit. Historical proposal and failure records remain unchanged.
