# Browser login diagnostic

All12 HTTP cases, nine privacy controls, CORS, schema/seed and TCP readiness pass. First Chromium still fails; four projects are skipped. [Allowlisted events](allowlisted-events.json) show login OPTIONS200 then POST429.

The exact original middleware permits five requests/client/path/60s and counts OPTIONS. The12 HTTP cases consume three login requests; the added diagnostic login precheck consumes another before browser OPTIONS/POST. This new429 therefore does not explain the earlier20s current-user timeout. Both failures remain. The next frozen diagnostic moves only the explicit precheck to auth/me GET+authorization, preserving the real limiter, assertions, endpoint and deadlines. The full five-project arrangement must respect real quotas.

[Independent review](review.json) verifies438 inputs, real logins/permissions, ownership, selected-artifact restoration, stopped own services/groups/browser and released reservation. The protected-service check uses a genuine earlier retained preimage, corroborated by the worker actual pre/post sample. Collector schema/provenance corrections repeated no application work. Raw config/credentials/logs/data remain private.
