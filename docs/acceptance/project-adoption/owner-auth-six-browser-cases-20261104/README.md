# Six scoped real-owner browser passes

The unchanged original API and accepted compiled frontend pass all 12 HTTP authentication/permission cases and 31 bounded preflight controls. Chromium and Firefox each pass the original real-login/navigation/exact-permission-denial test, an invalid-session UI rejection and a genuinely expired original-API-signed-session UI rejection: six browser cases total.

The original positive test remains byte-for-byte at the start of the extended spec, including real password login for both isolated users. Only negative sessions use seeded local storage. Each negative test requires the real original API's401, the original UI's unauthenticated redirect, token removal and absence of privileged content. No positive token seeding, source API change, limiter bypass, header spoofing or relaxed assertion occurs.

WebKit's positive case times out at the unchanged 20-second bound. Its privacy-safe trace records client page errors and no API request. Its two negative cases and both mobile projects' six cases are unrun. The full browser matrix and authentication increment remain unaccepted.

Independent review rehashes 444 bindings and all 2,482 selected files/524 directories/modes, original pointer/manifest/attempts; confirms four API instances, owned browser groups/container and proxies stopped; and verifies the reservation released and unrelated database unchanged. The 1.25 GB declared job allowance stays inside the original 4 GB ceiling; all other resource/time bounds remain.

The collector initially expected failed instead of Playwright's timedOut state. That evidence-only schema correction and its failed review remain preserved; no application rerun was used to repair the collector.

A separate anonymous Chromium/WebKit startup diagnostic enters no data and disables API access. Its setup failures remain. It preserves the original three unavailable producer paths and verifies restoration before ending. The purpose is to identify the client-side startup error; it cannot accept authentication. Raw configuration, tokens, user data and page-error text remain private on Norway.
