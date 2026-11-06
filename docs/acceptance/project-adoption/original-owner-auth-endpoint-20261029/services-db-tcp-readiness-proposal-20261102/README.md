# Approved TCP-readiness attempt — captured data ownership refusal

Exactly one revised attempt was approved against frozen manifest
1fe5c34365a928d11c2c3a9be8fbf27a1fd944f0f0afa6d1bcfcaf1528ba17f2.
All 423 bindings, 387 original API sources/two interpreters and 44 earlier failed
record preimages matched. Preparation beccff2 and actual launch dcf921a are
distinct; the exact frozen executable payload matched.

The original ownership validator passed after its normal heartbeat wait.
The 10s profile precheck passed without output. The pinned owned PostgreSQL
container started, with actual image/user/mount/CPU/memory/PID/read-only/capability
settings independently inspected. Bounded startup capture now retained the
fatal message: data directory "/var/lib/postgresql/data" has wrong ownership.
initdb completed, but the server refused startup. This establishes the failure
condition in THIS run; it does not retroactively prove the cause of every
earlier uncaptured exit 1. Locale/local-trust messages are warnings, not the
established fatal condition.

The new TCP check never declared readiness. All 32 bounded trace rows and
startup streams remain private: stdout 1,158 bytes, stderr 371 bytes, JSONL 9,864 bytes,
all below 4MiB/private mode. Recorded pg_isready responses included rejecting/
unresponsive states; no published-host TCP success occurred. No original
migration, seed, API, HTTP auth case or browser case ran.

The exact owned container 731b11b74ee5d2207555534808cbc12c5ae36c74b525c9c383e3fa767372ca64
and startup attachment/worker group are independently stopped. All test ports
18765/18866/13000 are clear. Owned data, generated credentials, raw proofs and
logs remain private and preserved. Protected Advocates database id/start/
restart identity matched. No old data was modified or deleted.

Read-only Docker archive headers reported UID 0:GID 0 for the data root and
PG_VERSION; host stat reported UID 501:GID 20. No Docker ownership attributes were
found on that host directory. These are observations from DIFFERENT views.
Archive metadata is not proof of the exact stat/geteuid values seen by the
server. The underlying host/container ownership projection remains uncertain.
The inspection streamed only the root header and the 3-byte version file, without
extracting database contents or starting a process inside the container.
The first Python xattr inspection call was unavailable; macOS's xattr CLI was
used instead. No application phase was repaired or reexecuted.

Request 663f239c-eeff-437c-b2ff-9b33019a5953 finished/released. Supervisor/guard
exit 1/completed=false preserved. Guard 6057770e-4ffb-4993-a0d3-37e7480a6cc0 digest:
80913722c10540477e912118e6c316bfe7b2c418cfcd87adbed91e43f8a50abc.
Native exclusive/4GB growth/500MB reserve/100GB retention stayed unchanged.
The single approval is consumed; no automatic retry or recovery followed.

Executed verification: all 423 frozen/driver hashes, 44 older preimages, actual
guard/supervisor result and release, protected DB identity, exact stopped owned
container config/mounts/limits, owned attachment group absence, listener closure,
private stream bounds/digests, captured fatal condition and stopped archive
metadata. The new readiness gate refused safely; this is not successful
authentication or a complete qualification of TCP readiness/attachment quotas.

The [candidate proposal](proposed-data-owner/PROPOSAL.md) is NOT APPROVED/NOT RUN.
It limits a Docker archive metadata operation to a NEW EMPTY owned data bind:
one frozen tar directory entry ".", UID501/GID20/mode 0700, no files or links.
An in-container non-root guard then requires process/data identity 501:20 and
mode 0700 before execing the ORIGINAL image entrypoint. Same image/user/caps/
read-only root and three binds remain; no privileged workload or new volume.
The prior data/containers are untouched. If setup or the guard fails, stop.

[Docker's copy documentation](https://docs.docker.com/reference/cli/docker/container/cp/)
describes stdin tar and archive UID/GID preservation; it does not establish that
this candidate works on the current bind mount. A runtime check is mandatory.
The existing bounded startup capture, container+published TCP readiness and
all 12 HTTP/five browser cases remain. Setup 30s stays inside 600s total; all other
bounds unchanged. No deadline increase, deletion, installed safeguard change,
foreign interruption or global activation is included.

Preparation only: 425 input hashes,Python AST,Node --check,sh -n, single-empty-tar
header check and normalized executable scope comparison passed. No ownership
metadata was applied, no new guard/profile/container/DB/TCP/API test ran.
Frozen manifest SHA-256:
99ac212622b370b39a5f3dc4eac7cd4a5c9d037fcc3b21352a76627d0075afac.
Direct one-attempt approval is required. Full G0–G6 remains unachieved.
