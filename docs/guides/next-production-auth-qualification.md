# Pinned Next production authentication qualification

Scoped production authentication and private-document qualification passed in
[run 40013461564](https://github.com/roryscot/patamaps/actions/runs/40013461564),
source 00c9168. The [runtime receipt](../acceptance/project-adoption/g3-chatbot-production-auth-20261023/runtime.json)
and [independent verification](../acceptance/project-adoption/g3-chatbot-production-auth-20261023/independent-verification.json)
record the exact scope. Earlier failed receipts remain preserved. General
adoption, production deployment and complete dependency closure are unaccepted.

This is the focused qualification recipe for unchanged `vercel/chatbot` commit
`c2f8235e1f3ea903ad8b7f61447c4f74164b5c58`, Next 16.2.10 and the exact locked
dependency set. It is not an arbitrary-project authentication adapter.
See the [support matrix](project-support-matrix.md) for accepted results and
[current backlog](../plans/integration-enhancement-backlog.md) for open gates.

The `next-server-actions` choice in the manually dispatched
`native-capabilities.yml` workflow calls the focused `next-server-actions.yml`
lane. It runs the existing strict native regression gates, selected-source
privacy controls, the native source capture/stage and unchanged production
build/manifest observations before the optional `--runtime` phase in
`scripts/qualify_chatbot_next.py`. Runtime remains CI-only; the qualifier refuses
other platforms and local unguarded execution.

The upstream production proxy explicitly asks for secure cookies. The trusted
owner runtime launcher therefore starts a new PostgreSQL data directory, runs
`tsx lib/db/migrate.ts`, starts `next start` on loopback and terminates HTTPS in a
small owned loopback proxy. It does not replace the production cookie policy,
patch upstream source, use the development server, or connect to a user database.
The new private database is stopped when the qualification ends.

Browser bootstrap installs the locked Chromium revision without privileged OS
package changes, then launches and closes that actual browser to check the
runner's existing libraries. Initial auth-page readiness waits for the real browser session request to
finish within the existing twenty-second deadline. A missing dependency remains a failure; the four
upstream browser tests and all action/permission controls are still required.
Browser downloads retain their original ten-minute deadline. Playwright
[documents browser and system dependency installation separately](https://playwright.dev/docs/browsers#install-system-dependencies).

The owner boundary is explicit: after Patamaps captures have finished, the
launcher generates disposable database/signing material and a local TLS key.
These values are passed directly to the trusted owner process environment.
Patamaps does not read or resolve its `AUTH_SECRET`/`POSTGRES_URL` secret-reference
labels, and the values are never relabeled as nonsecret configuration.

The browser driver runs the four existing upstream authentication-page tests
unchanged against the production HTTPS origin. Its additional controls submit
real Server Action requests for invalid data, successful registration, duplicate
registration, wrong passwords and successful login. The off-origin request must
leave the new principal absent, and the same payload at the valid origin must
create it and establish a session. Document tests create/read through the real
owner API and require cross-user read/write and guest refusals, with the owner's
content unchanged afterward. These controls do not exercise external model or
upload endpoints.

Action-state collection uses the existing HTTPS proxy, correlates its bounded
live response with the exact request payload digest, and requests identity
encoding for actions. It does not synthesize or retry an action, rewrite its
body/status, or depend on the browser retaining the completed response body.

Published evidence contains fixed control names, outcomes, source/engine/tool
identities and shutdown results. Traces, video, screenshots, raw HTTP/cookies,
private server/database logs and generated secret files are outside the upload
directory. Credential/cookie evidence scans run before a successful result.
Private debugging files are local to the CI runner and are not promised to remain
available after runner teardown; the compact sanitized failure stage is retained.
Compiled server-reference/encryption material is never an uploaded observation.

The launcher reuses the existing process guardian, deadlines and workflow disk
monitor. It stops its owned PostgreSQL, Next, browser and HTTPS processes and
checks that their listeners have disappeared. No background owner service is
reused. The standard 4 GB workflow growth and 500 MB reserve remain in force;
Node's heap setting is not represented as a kernel memory quota or benchmark.

Source and configuration observation, a successful production build, and actual
runtime authentication are separate outcomes. Read the precise receipt and
failed-stage fields. These results do not establish production deployment,
external authentication providers, complete dependency closure, general project
support or practical edit-loop performance.

The separate [page-rewrite/canonical-session-proxy profile](next-rewrite-proxy-qualification.md)
now passes with an explicitly derived configuration and the same auth/document
controls. Its original internal session alias remains failed; it does not change
the unchanged-source result documented here.
