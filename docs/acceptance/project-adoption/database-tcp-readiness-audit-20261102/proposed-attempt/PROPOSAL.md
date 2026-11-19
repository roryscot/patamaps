# One TCP-readiness/startup-capture authentication attempt — NOT APPROVED / NOT RUN

This replaces the unexecuted e4a8936 startup-capture proposal. That proposal and
all previous failures remain unchanged. Resuming the goal does not authorize
this attempt or reset any consumed initial/repair/one-attempt budget.

Read-only inspection of the actual pinned PostgreSQL image found that its
entrypoint starts a temporary Unix-socket-only server with listen_addresses=''
before final startup. The existing pg_isready omitted host/port and PGHOST/
PGHOSTADDR were unset, so it can accept that temporary server without proving
final TCP or the API's published DB route. This source-derived false-positive
path has NOT been reproduced in a new live test. The earlier exit1 root cause
is still UNKNOWN; startup capture remains necessary.

Request exactly ONE additional authentication attempt with:
- Same previously prepared bounded startup stdout/stderr and readiness/state
  capture: Docker start --attach in guarded worker group,4MiB kernel file limits
  per stream,4MiB readiness JSONL with4KiB per response/full lengths/digests.
  Daemon log driver remains none. Guardian stops exact owned container before
  group cleanup; independently verify attachment stop and reservation release.
- Explicit pg_isready TCP127.0.0.1:5432 inside the owned container, then a plain
  TCP connection to the API's host-side127.0.0.1:18866 route (at most1s).
  BOTH must succeed inside the SAME30s readiness deadline. This strengthens
  readiness; it does not prove database credentials, schema or authentication.
  Those remain the original migration/seed/API assertions.
- Fresh output paths and the source-audit evidence binding. No original API,
  bootstrap, application migration or browser assertion is changed.

If DB readiness succeeds, continue all12 original HTTP and five original browser
real-login/permission/edited-label cases with two isolated owned users/roles.
If startup/readiness fails, preserve it and stop. No automatic phase retry,
repair, restart, deadline increase or alternative database engine follows.

All existing limits stay: canonical4GB growth/500MB reserve/100GB retention,
native exclusive,600s total guardian,30s start/30s readiness/30s full ownership
probe,20s heartbeat wait,10s profile syntax precheck before credentials/DB,
migration/seed120s,HTTP10s,PythonCPU90s/log4MiB,
browser20s-case/120s-global/retries0/180s-wrapper. Original other-port,
outside-write and dotenv-read denial checks remain mandatory.

Same pinned PostgreSQL image and actual inspected1CPU/512MiB/swap0/PIDs128,
UID501:20,readonly-root/dropALL, exact three binds and bounded tmpfs.
Observed data512MiB/16384files every5s remains NOT a hard filesystem quota.
Only API18765/DB18866/frontend13000 on127.0.0.1; recheck all ports before launch.
Never interrupt the existing foreign18766 listener or unrelated Advocates DB.
Preserve all previous containers/data/credentials/logs/failed records.
No deletion, installed safeguard/policy edit, cap increase, package install,
frontend rebuild, global/registry/trust/parallel/production activation or other
pending I3/dynamic/performance budget extension is included.

The pinned entrypoint SHA-2569c440299ae04a0a79d55b8bf03307036d890a40979d2fb698073c9050d4b20a5
was read with docker cp from a STOPPED owned container, not executed.
Official sources: https://www.postgresql.org/docs/16/libpq-connect.html#LIBPQ-CONNECT-HOST
and https://www.postgresql.org/docs/16/app-pg-isready.html.
Original ready/failed containers had equal normalized configuration and identity
files; that comparison does not explain the exit.

Preparation only: all423 bindings including387 original API sources/two
interpreters rehashed, Python AST/Node --check and normalized executable change
comparison passed. No TCP connection, ownership probe, profile test, container
start/restart, original API import or application run was performed here.
Frozen manifest SHA-256 is in preparation-review.json. After DIRECT approval,
recheck that manifest,423 bindings, original owner commit, prior actual failed
receipt/postmortem, protected DB identity and required ports; bind the answer
then run monitor.py exactly ONCE. Changed scope requires fresh review.
