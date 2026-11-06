# Real HTTP authentication passes; first browser project times out

The original API migration/schema setup and seed completed against a fresh
owned PostgreSQL volume. The actual non-root process and data owner matched;
both container TCP5432 and published TCP18866 readiness passed. All12 original
HTTP cases passed: two real password logins/current-user identities, distinct
permissions and permission checks, plus missing/invalid/expired sessions and
wrong password. No response tokens, passwords or user records are published.

The first Chromium browser case timed out at its unchanged20s limit waiting
for the current-user response after login. The other four projects were skipped.
The cause remains unproven; source inspection is not runtime request evidence.
No authentication/browser/full-owner acceptance follows from the HTTP pass.
A bounded request/status/CORS diagnostic is the next step; do not widen timeouts.

The independent review verifies431 bindings, the actual1GB native-exclusive
reservation and unchanged4GB machine ceiling, stopped owned database/attachment/
worker and browser group, required ports closed, previous failures retained,
unavailable-producer paths/artifact bytes restored and unrelated database start
identity unchanged. Reservation finished/released; guard/supervisor1 stay failed.
Owned database data remains private and retained.

JSON uses fixed case labels, counts/flags and source/proof digests only.
Raw credentials, configuration, response bodies, traces and inventories remain
private. The published verifier writes its complete result to private storage.
