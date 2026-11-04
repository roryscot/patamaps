# Bounded original-owner startup diagnostic

All 12 original HTTP cases and the Chromium browser case pass. Both observed browser API instances become ready within the unchanged ten-second deadline (6.393 and 7.269 seconds). Firefox completes both real logins but its subsequent permission navigation records NS_BINDING_ABORTED; the remaining three projects do not run. Authentication is not fully accepted.

The unchanged original login handler awaits checkAuth and asynchronously pushes ROUTES.PREFLIGHT, whose generated route is /discovery. The test previously waited for the auth response and immediately navigated to /admin/users. A pending original redirect is a plausible cause of the observed navigation abort; this is an inference, not a proven product defect or explanation of the preceding WebKit readiness failure.

The next frozen attempt adds only an explicit assertion that the original /discovery redirect completes before continuing. All eleven original expectation statements, twenty-second case limit, 120-second suite limit, 180-second wrapper limit, inclusive 600-second phase limit, original API/source/permissions/limiter, and resource ceilings remain. No automatic retry or acceptance on cleanup is introduced.

Independent review rehashes 443 bindings and all 2,482 accepted artifact files, verifies 524 directory/mode records and exact pointer/manifest/attempt list, all three API processes reaped, owned container/browser groups stopped, lease released and the unrelated database unchanged. Typed startup observations and fixed-code redaction remain bounded and private; the controller's eleven controls and six actual helper controls pass. Earlier failures and data remain. No deletion or safeguard activation occurred.
