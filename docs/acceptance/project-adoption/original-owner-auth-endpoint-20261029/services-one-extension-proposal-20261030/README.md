# Approved additional authentication attempt — port precondition refused

Exactly one application attempt was approved under frozen manifest
49c414f92f6b38749f3fc6212a1e4e5ffd27d7f6d1b2095cf989d10ab50aba60.
All 421 inputs matched before/after, including 387 original API sources and 2
interpreter executables. Preparation revision 03ccfec and actual launch revision
1585f8482e4648220563a0fba0febf2886366d89 are distinct; the bound executable
payload matched. The executed payload is the prior frozen proposal, whose
[source changes](../../ownership-status-investigation-20261030/approved-one-shot/proposed-one-application-attempt/payload-changes.patch)
and original runner are preserved.

The existing 20s heartbeat wait was exercised, without changing any criterion.
All three full probes completed their 16 stage markers. The original validator
refused the first two stale-heartbeat samples and accepted the third fresh
sample with correct owner identity/ancestry, no cancellation and no other
active reservation. This was one application phase with existing readiness
polling, not three phase retries. Stage windows 389/117/133ms are functional
observations, not isolated benchmarks. Earlier 30s timeouts remain unexplained;
none was reproduced in this run.

The driver then failed its mandatory free-port precondition:
OSError, errno 48, Address already in use. Subsequent read-only inspection found
a foreign Python listener at 127.0.0.1:18766; its process predates this attempt.
API 18765 and forwarder 13000 had no listeners. No foreign process was signalled.
The existing listener and unrelated Advocates database remained running.

NO owned database/container, credentials, migration, seed, API, HTTP test or
browser case was created/run. This is a pre-service qualification failure,
not demonstrated defective application authentication or a Patamaps regression.
Authentication and permissions remain unverified; the full adoption goal stays
unachieved. No original application source or accepted frontend output changed.

Canonical 4 GB growth/500 MB reserve/100 GB retention/native exclusive remained.
Supervisor/guard exit 1 and guard completed=false are preserved. Request
6777725c-f925-4cd5-b866-59384c40af8b finished/released; guard
e3abcd6d-a268-4e0a-8a77-6876eef4a75b record digest:
ec7789feee188a1f2cf859bde808869046daa2d11ddc8f7d37837a8b17495c0c.
All 21 prior failed-record preimages and frozen inputs matched. Protected
database id/start/restart identity matched. No deletion, policy change,
automatic recovery or phase retry occurred.

The initial post-run reviewer also refused: its blanket assertion that all
three test ports must be closed encountered the same pre-existing listener.
That reviewer/source and failure record are retained. Only postprocessing was
corrected to require no owned-service survivor while preserving the foreign
listener; the frozen application was not repaired/re-executed. The corrected
review and separate saved-proof reviewer passed. The result's
ownedDataPreserved=true means no data was lost; no test database existed.
nextProducerPathsAndArtifactBytesRestored=false is unexercised browser cleanup,
not an observed restoration failure: that branch never ran.

Executed verification: all 421 frozen binding/driver rehashes; original validator
on the three saved proofs only; actual guard/supervisor interval, exit and
release checks; exact protected database identity; 21 failed preimages; absence
of new container/database/credentials/run directories; read-only listener/PID
inspection. Review code and safe outcomes are public; raw logs/proofs and
unrelated process details remain private. No ownership probe was added during
post-run review.

The consumed approval authorizes no further phase. The [new proposal](proposed-port18866/PROPOSAL.md)
is NOT APPROVED/NOT RUN. It changes only the isolated database loopback port
18766->18866 and fresh output paths. The API endpoint 18765, frontend 13000,
all assertions and bounds stay unchanged; the sandbox removes the old DB
network allowance and permits only the new one in its place. Port 18866 had
no listener during preparation and must be checked again before any launch.
Python AST/Node --check, 421 input rehashes and normalized payload equivalence
passed. Frozen manifest SHA-256:
f00a7525a3aa101a28706077d39a8a01685acd2ea081a5bf4791b8bd70ff91cb.
It requests one separately approved attempt without automatic phase repairs.


The port-only proposal was separately approved and executed. Its [preserved owned-profile parser refusal](../services-port18866-proposal-20261030/README.md) records that original migration/authentication code remained unrun. Earlier proposal and failure records remain historical.
