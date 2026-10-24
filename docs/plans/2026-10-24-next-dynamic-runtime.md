# Pinned Next dynamic page and data-boundary qualification

Status: implemented and focused-preflight verified; runtime qualification pending.
This closes a specific original G3/G6 gap beyond the existing source/manifests,
auth/document and rewrite checks. Develop on Intel; run the existing bounded
Linux Next lane. Native G4 measurements still await storage admission.

## Fixed source and scope

Keep vercel/chatbot at c2f8235e1f3ea903ad8b7f61447c4f74164b5c58 with
Next16.2.10. Preserve all owner source/configuration bytes and the unchanged four
upstream page tests. Use the original owner configuration for this increment:
no rewrite overlay, standalone change, inserted route or model-provider fixture.
Reuse the existing trusted-owner HTTPS browser/auth/PostgreSQL harness and native
capture/compiled-observation contracts, not a new service or graph framework.

[Read-only source intake](../acceptance/project-adoption/g3-next-dynamic-runtime-20261024/intake.json)
pins the relevant public Git blobs. The dynamic page returns null; the shared
client shell extracts its chat ID and fetches /api/messages?chatId=....
Private data access is enforced by that actual API. An unseen valid ID returns
an empty200 response. A public chat is read-only for a non-owner. The dynamic
stream endpoint is a constant204 stub, not evidence of resumable generation.
Next16.2.10 supplies405 for unimplemented methods.

Verify native build records bind /chat/[id], /api/chat/[id]/stream and
/api/messages to their original physical App Router modules, including the
(chat) route group. Preserve native metadata's regexExecuted=false,
runtimeEstablished=false and httpMethods=not-observed; runtime witnesses are
separate evidence and never retroactively turn observations into admission.

## Frozen runtime expectations

Retain all sixteen existing auth/document groups and all four unchanged owner
page tests. Add these thirteen named groups:

| Group | Observable expectation |
| --- | --- |
| dynamic-owner-private-page-and-id-bound-data | Authenticated owner visits /chat/ID without redirect, browser fetches that exact ID, API200/private/non-readonly, seeded message visibly renders and composer is available. |
| dynamic-owner-second-id-replaces-visible-data | A second public chat ID yields its own message; the first private message is absent after navigation. |
| dynamic-cross-user-public-page-readonly | Independent authenticated user reads the public message; API reports readonly and UI has no composer. |
| dynamic-cross-user-private-data-refusal | Same independent user visits the private shell; its data request403s with no private content. Do not require a page-level403/404 from this null-page/client-shell design. |
| dynamic-guest-public-page-readonly | A real existing guest-session path reads the public message without a composer. |
| dynamic-guest-private-data-refusal | That guest's private data request403s and private content stays absent. |
| dynamic-unseen-id-empty-response | A fresh valid UUID returns the owner's defined200/empty/null-owner response without persisting a chat. |
| dynamic-missing-chat-id-query-refusal | The actual messages API returns400 for a missing required query ID. |
| dynamic-extra-page-segment-refusal | /chat/ID/extra returns404 without following redirects. |
| dynamic-stream-route-204 | The exact dynamic GET stream path returns204 with empty body. This qualifies matching only. |
| dynamic-stream-post-method-refusal | POST to the GET-only stream handler returns405. |
| dynamic-stream-extra-segment-refusal | A trailing extra stream-path segment returns404. |
| dynamic-fixtures-unchanged-and-no-generation | All seeded chat/message rows are byte-equivalent after reads/refusals; no generation POST was sent. |

Seed only two chat rows/two plain assistant messages through the already trusted,
new CI-only database connection. Do not patch owner code, call generation/upload
APIs, use production credentials or read an unrelated database. Keep IDs,
fixture content, passwords, cookies, signing material, raw HTTP and private logs
outside public records. The existing final credential/cookie barrier must cover
all new contexts and fixture values. Block and count any browser POST to the
generation endpoint before transmission; require zero attempts.

The positive owner/public cases and independent actors are countercontrols for
private-data refusals. Exact query-ID binding and distinct visible messages
must prevent a stale or hardcoded page from passing. Refused requests must leave
every seeded row unchanged. Only fixed labels, numeric statuses, booleans,
digests and original public source/manifest bindings enter evidence.

## Implementation and execution

Add an explicit opt-in to the existing qualifier/runtime/browser driver.
Reject unsupported flag combinations before effects; old profiles keep their
existing control sets. Add focused source/blob/native-binding and immutable-data
controls, then one manual existing Next Linux lane. Reuse original source
acquisition/privacy, current source engine verification, real production build,
native compiled observations, trusted database/migrations, HTTPS and cleanup.
No new VM, scheduler, provider framework, product policy or secret resolution.

Keep the existing4GB qualification growth/500MB reserve, two Cargo jobs,
2GiB Node heap, bounded command logs/deadlines and stopped owned listeners/
processes. Existing toolchain/regression bootstrap is separate from the main
qualifier's monitored interval; do not claim a whole-run memory/disk peak from
that interval. Upload compact nonsecret evidence only, with14-day retention;
retain reviewed receipts/source on Intel rather than dependency/output trees.

Commit/push the frozen plan before implementation. Allow one initial runtime
run and at most two repairs for demonstrated implementation/harness defects.
Preserve failures and every positive/refusal expectation. Review exact Git/
driver/engine/source/manifest bindings, all29 groups/four owner tests, private
evidence barriers and actual shutdown independently before updating support.
Performance, external models/BotID/upload providers, complete dependency closure,
other dynamic shapes and fresh installed replay of this increment remain open.

## Implementation checkpoint

The opt-in qualifier, pinned Git-blob/compiled-module bindings and thirteen
browser/API controls are implemented. All eleven new focused controls and four
source-acquisition controls passed on Intel, together with Node syntax, Python
AST, workflow YAML and diff checks. Fixtures remain in the recorded private
preflight directory. Runtime and support claims await the single selected Linux
lane and independent artifact review; no dynamic runtime acceptance is implied.
