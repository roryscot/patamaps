# Read-only database readiness audit and proposed TCP correction

No application, container, profile or ownership test was run in this audit.
The original initial/repair budgets and three separate application extensions
remain consumed. Resuming the goal did not extend them.

Current Norway checkout was clean at beccff2. Both previously owned containers
remain stopped. Their normalized image/runtime settings and identity-file
bytes/modes match, excluding only deliberate per-attempt names/passwords/paths.
This comparison does not explain the database exit. Full environment values
were compared privately in memory and were not printed or published.

The actual pinned image's /usr/local/bin/docker-entrypoint.sh was read using
docker cp from a stopped owned container; its tar was parsed only in memory.
Source SHA-256:
9c440299ae04a0a79d55b8bf03307036d890a40979d2fb698073c9050d4b20a5.
The safe line references/excerpts are in review.json; full source stays private.
That entrypoint starts a temporary socket-only server with listen_addresses=''
for initialization, stops it, and only later executes the final server.

The existing runner's pg_isready command omitted host/port. The inspected
container has no PGHOST/PGHOSTADDR override. PostgreSQL documents that an
unspecified host uses a local Unix socket on Unix systems:
[libpq host selection](https://www.postgresql.org/docs/16/libpq-connect.html#LIBPQ-CONNECT-HOST).
Consequently, the old readiness check can accept the temporary initialization
server while the final TCP server/API-facing route remains unavailable.
This is a source-derived readiness-contract defect; a live false-positive
scenario was NOT reproduced during this audit.

The earlier reported successful database readiness sample must therefore be
scoped to its Unix socket. No host TCP readiness, credentials/schema validation,
migration success or authentication acceptance follows from that result.
The separate exit-code 1 startup failure remains unexplained; neither a startup
fix nor a passing application result is claimed.

A new [unexecuted proposal](proposed-attempt/PROPOSAL.md) supersedes the earlier
unexecuted e4a8936 startup-capture proposal, which remains unchanged. The new
payload preserves its bounded private startup/state capture, and requires:
- explicit pg_isready -h 127.0.0.1 -p 5432 inside the owned container;
- successful host-side TCP connection to 127.0.0.1:18866;
- both within the same 30s readiness window, with a host-connect bound of 1s.
The original migrations/seed/API assertions still establish the subsequent
database identity and real login/permission outcomes. A TCP connect by itself
does not prove database authentication.

[pg_isready options](https://www.postgresql.org/docs/16/app-pg-isready.html)
define the explicit host/port selection. All 12 original HTTP and five browser
cases remain unchanged. Database image/settings, 4GB/500MB/100GB/native-exclusive
policy, 600s total deadline and every other bound remain. The new code only
strengthens readiness, retains startup evidence and uses fresh output paths.
No installed safeguard, original API/bootstrap/frontend or unrelated service
was changed, no data was deleted, and no registry/production/parallel activation
or automatic recovery/retry was performed.

Verification actually executed: source copy/digest and entrypoint-order review;
stopped-container/configuration and identity-file comparison; host-environment
presence flags only; complete 423-binding rehash/original owner commit; Python AST,
Node --check and normalized payload-change comparison; independent saved-audit
reviewer. These are inspection/preparation checks, NOT runtime qualification of
the new readiness branch or Docker attachment. No fixtures substitute for the
required real-project run.

New frozen manifest SHA-256:
1fe5c34365a928d11c2c3a9be8fbf27a1fd944f0f0afa6d1bcfcaf1528ba17f2.
The old e4 manifest and its no-result state were independently rechecked.
The latest current scope requires a DIRECT one-attempt approval before launch;
do not execute the superseded pending proposal or infer approval from goal
resumption. Full G0–G6 remains unachieved, and other pending lifecycle/dynamic/
performance execution decisions remain separate.


The revised TCP proposal was separately approved and executed. Its [captured data-ownership refusal](../original-owner-auth-endpoint-20261029/services-db-tcp-readiness-proposal-20261102/README.md) records safe refusal before original migration/auth/browser execution; no full runtime acceptance follows.
