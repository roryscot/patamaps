# One owned-data ownership correction / authentication attempt — NOT APPROVED / NOT RUN

The revised TCP attempt is consumed. Its captured stdout proves PostgreSQL
rejected its data-directory ownership after initdb. No migration/API/auth/browser
case ran. The exact owned container and attachment are stopped; all data,
credentials/logs/failures remain, test ports close and reservation released.

Read-only archive metadata reports UID0:GID0 while host stat reports501:20;
the workload is configured501:20. Archive metadata is not proof of the exact
server-process view. The fatal ownership refusal is established; the underlying
host/container projection mechanism remains uncertain. Do not weaken non-root
execution or claim a verified repair from this inspection.

Request exactly ONE new authentication phase with these bounded changes:
1. For its NEW EMPTY owned data bind directory only, after container creation
   and exact image/user/mount/ownership-label checks, use Docker cp --archive
   with a frozen tar containing ONE directory metadata entry "." only:
   UID501/GID20/mode0700, no files/links/parent paths. Destination is exactly
   the owned RW /var/lib/postgresql/data bind. Check empty before/after.
   Timeout30s; recorded setup stdout/stderr64KiB with full lengths/digests.
   If Docker refuses metadata setup, stop; no privilege or filesystem fallback.
2. Same image/user501:20/read-only-root/dropALL/three binds. Invoke a frozen
   non-root /bin/sh guard that prints process/data numeric identity, requires
   process501:20 and data501:20/mode0700, then execs the ORIGINAL image entrypoint
   with postgres. Failure stops before initialization. No root workload,
   extra capability, named volume, new mount or old-data modification.
3. Fresh output paths only. Earlier data/containers/outputs are untouched.

Retain bounded private startup streams (kernel4MiB per file+guardian), daemon
log driver none, bounded readiness/state trace, container TCP5432 PLUS published
host TCP18866 in the SAME30s window. If ready, original migrations/seed and12
HTTP/five browser real-login/permission/label cases proceed with two isolated
owned users. All original API/bootstrap/browser code and assertions stay.

Same canonical4GB growth/500MB reserve/100GB retention/native exclusive.
The metadata step30s fits inside the UNCHANGED600s total guardian. Other bounds
remain:10s profile precheck before DB/credentials,20s heartbeat wait/30s ownership,
start/readiness30s each,migrate/seed120s,HTTP10s,PythonCPU90s/log4MiB,
browser20s-case/120s-global/retries0/wrapper180s. Container remains1CPU/512MiB/
swap0/PIDs128/UID501:20/ROroot/dropALL; observed data512MiB/16384files every5s is
NOT a hard FS quota. API18765/DB18866/frontend13000 stay127.0.0.1.
No new deadline is added to the total allowance. Stop only owned processes/
container, verify attachment/group and reservation release, preserve failures.
No automatic retry/repair/restart/recovery, deletion, installed safeguard/policy
edit, cap increase, unrelated interruption, package/frontend rebuild, external
registry/trust/parallel/production activation or other budget extension.

Docker documents that --archive preserves source UID/GID and stdin tar input:
https://docs.docker.com/reference/cli/docker/container/cp/
The tar is generated and validated during preparation. It has not been applied.
The new guard has shell syntax checks only, no runtime ownership proof yet.
This is a candidate correction with mandatory verification, not an accepted fix.

Frozen manifest SHA-256 is in preparation-review.json. All425 input bindings
(including387 original API sources/two interpreters), Python AST, Node --check,
sh -n, tar-header checks and normalized executable comparison pass.
No container/metadata/profile/ownership/TCP/API/application operation has run
in this new directory. The four earlier application extensions remain consumed.
After DIRECT approval recheck manifest,425bindings, prior actual receipt/
ownership/startup reviews, owner commit/protected DB and ports; bind the answer
and run monitor.py exactly ONCE. A changed scope needs a new concrete review.
