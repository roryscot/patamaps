# One authentication attempt with bounded database startup evidence — NOT APPROVED / NOT RUN

The previous corrected-profile attempt is consumed. Its10s profile check passed.
The fresh PostgreSQL container then exited1 after4.6s, without OOM or a Docker
engine error. Readiness failed within the unchanged30s limit. No original
migration, seed, API, HTTP case or browser case ran. The exact owned container
is stopped; data, credentials, logs, old failures and the unrelated DB remain.
The evidence does NOT establish slow startup, a root cause or an application bug.
Existing Docker log driver none and discarded pg_isready responses prevented
capturing the server's startup error. Do not merely extend the deadline.

Request exactly ONE additional diagnostic authentication phase. Keep identical
pinned PostgreSQL image, container user/mounts/CPU/memory/PID/readonly/capability/
tmpfs settings and ports. Add ONLY bounded evidence capture:
- Start the owned container with supported docker start --attach, retaining its
  stdout/stderr in PRIVATE files. Each Docker-client stream has kernel RLIMIT_FSIZE
  4MiB and the guardian also observes the existing4MiB per-file cap. The Docker
  daemon log driver remains none. Attachment stays in the existing guarded worker
  process group; guardian stops the exact owned container before group cleanup.
- Observe start state within the existing30s Docker-start bound, then preserve
  pg_isready responses and exact owned state under the existing30s readiness bound.
  Readiness/state JSONL is bounded4MiB, each response stream records at most4KiB
  plus full lengths/digests. An exited container fails immediately; no restart,
  repair, timeout increase or automatic phase retry follows.
- If readiness succeeds, continue the unchanged original migrations/seed/API and
  all12 HTTP/five browser login-permission-label cases. If it fails, preserve
  the error and stop. No success criterion is relaxed. Data goes in a fresh
  output directory; previous containers/data/credentials/outputs remain untouched.

The already accepted profile syntax is unchanged. Its10s no-API-import precheck
still precedes credentials/database creation. Native exclusive canonical
4GB growth/500MB reserve/100GB retention and600s TOTAL service guardian remain.
All original other-port/outside-write/dotenv denial controls,20s fresh heartbeat
wait/30s ownership validator, migration/seed120s, HTTP10s, PythonCPU90s/log4MiB,
browser20s-case/120s-global/retries0/180s-wrapper remain unchanged.

Only fresh owned PostgreSQL may start/stop:1CPU/512MiB/no swap/PIDs128,UID501:20,
readonly root/dropALL/no added caps, three declared binds and bounded tmpfs.
Observed512MiB/16384-file data ceiling every5s remains NOT a hard FS quota.
API18765/DB18866/frontend13000 remain loopback127.0.0.1; recheck before launch.
Never touch the foreign18766 listener or unrelated Advocates database.
No deletion, package installation, frontend rebuild, installed safeguard/policy
edit, cap increase, unrelated interruption, automatic reservation recovery,
registry/trust/parallel/production activation or other budget extension.

Before launch bind direct human approval to frozen.json SHA-256 from
preparation-review.json; rehash all422 inputs and prior failure digests.
Run monitor.py exactly ONCE after approval. Earlier initial-plus-two and all
three application extensions remain consumed. This proposal adds observation,
not a demonstrated root-cause fix, and is NOT AUTHORIZED by the consumed attempt.
Python AST/Node --check, all input hashes and normalized executable comparison
pass in preparation only. No new Docker attachment, ownership probe, profile
check, database, original API import or application has run here.
Independently verify final attachment/owned-service stop and actual reservation
release; preserve failure without automatic repair or recovery.
