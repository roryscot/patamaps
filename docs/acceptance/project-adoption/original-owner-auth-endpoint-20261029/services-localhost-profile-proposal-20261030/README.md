# Approved corrected-profile attempt — database exited before readiness

Exactly one corrected-profile attempt was approved against frozen manifest
42cf17ef56ad3f5e9f0c72e385f38d159c1a55b25f5b0e0b2e15fa4de2f317c1.
Preparation revision 2cf5196 and actual launch 1b27f52e8cef65ed57fa831556cb91a94f043263
are distinct. All 422 bindings including 387 original API sources/two interpreters
matched before/after; all 36 prior failed-record preimages remained unchanged.
All required ports were free before launch and passed the original bind checks.

The original full ownership validator accepted the third fresh proof after two
stale-heartbeat refusals under its existing readiness wait. The pinned Python
profile precheck then exited 0 with zero output, before database creation.
This accepts syntax/minimal execution of the corrected owned profile only.
The API bootstrap's three confinement controls remain unexercised.

A fresh owned PostgreSQL container started under the same inspected limits,
image/user/mounts and DB 18866 binding. The original readiness loop failed after
its 30s bound: OWNED_POSTGRES_NOT_READY. Read-only postmortem shows the container
exited 1 about 4.6s after start, OOMKilled=false and Docker State.Error empty.
This does not establish slow startup. The root cause is unknown.
The current runner discarded pg_isready output, and log driver none retained
no server startup stream. Do not claim a diagnosis that those missing logs
cannot support or increase a failed deadline to obtain a pass.

NO original migration, seed, API, HTTP auth case or browser case ran. The
database failure precedes those operations. No new live ownership/database
probe or restart was performed during postprocessing. Accepted frontend and
original application source are unchanged; authentication remains unverified.

The exact owned container 335cb0b920db5996a39e8533302436b4534e1eec40cc543a9e3867f4d1566ea4
is independently stopped/PID 0, matching ownership labels, image, mounts and
1 CPU/512MiB/no swap/128 PIDs/UID 501:20/read-only-root/no-capabilities/no-log settings.
API 18765/database 18866/frontend 13000 have no listeners. Owned cluster files,
credentials and raw logs remain private. Data at review: 40,443,904 allocated
bytes/968 files, not a peak or restoration claim. Prior stopped test clusters
remain. Unrelated Advocates database id/start/restart identity matched.

Request 5c8c6daa-4712-4dee-930f-fcb7cd2f7b72 finished/released. Supervisor/guard
exited 1 with completed=false. Guard 379f0002-edfe-4dcd-9454-73f8772a019c digest:
6fdef11bbcee4e6541ed6eabfab19e76a2311b61d6fbdc093f2db967cd0a41fe.
Canonical native-exclusive 4GB growth/500MB reserve/100GB retention stayed.
No deletion, installed safeguard/policy edit, foreign interruption, automatic
recovery or phase retry occurred. All prior initial-plus-two and three separate
application extensions are consumed.

Executed verification: complete 422-binding/driver rehash, 36 historical preimages,
actual supervisor/guard interval/result/release, protected database identity,
exact owned-container state/configuration and listener closure, profile stream
lengths/digests, saved-proof validation, stopped data metadata and bootstrap
boundary review. Commands and safe JSON outcomes are preserved here; raw
credentials, logs and proofs stay private. No full adoption acceptance follows.

The [next proposal](proposed-database-startup-trace/PROPOSAL.md) is NOT APPROVED /
NOT RUN. It requests one diagnostic authentication phase with bounded startup
stdout/stderr and readiness/state capture, preserving the SAME database image,
settings, start/readiness 30s bounds, 600s total limit and all original auth cases.
An exited DB fails immediately; if readiness succeeds, original migration/
authentication/browser assertions proceed. This adds observation, not a
demonstrated root-cause fix. No timeout increase or automatic retry is proposed.

Docker start --help confirms --attach captures stdout/stderr. The proposed
attachment inherits the existing guarded worker group; exact owned-container
cleanup precedes group cleanup. Planned streams have 4MiB kernel file limits and
guardian checks; readiness JSONL has 4MiB writer/guardian bounds with 4KiB per
recorded response plus full lengths/digests. Docker daemon log driver stays none.
No attachment or revised readiness driver has run. Preparation only: Python
AST/Node --check, all 422 hashes and normalized application payload comparisons
passed. Frozen manifest SHA-256:
e4a8936a0c62da5186208a3f87a621b3ae7fa842b58897c0740607b734bd4fad.
Full G0–G6 remains unachieved; other pending execution permissions are separate.
