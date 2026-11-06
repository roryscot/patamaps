# Seeder API import comparison on Intel

An import-only diagnostic investigated the fresh API startup deadline from the
[corrected frontend authentication attempt](../seeder-corrected-frontend-auth-attempt-20261105/README.md).
The first probe loaded the original API in 5.74 seconds, then stopped at its
2,000-module bytecode preparation cap after discovering 2,641 modules. That
failure and its private evidence were preserved. A fresh probe covered the
observed module set within the same 64 MB source-byte cap, 40-second child
deadline and 128 MB guarded growth allowance.

| Original Python startup mode | Import and Uvicorn configuration times | Median |
| --- | --- | --- |
| Existing interpreter behavior | 4.85 s, 6.15 s, 6.61 s | 6.15 s |
| Private checked-hash bytecode cache | 5.67 s, 6.10 s, 7.48 s | 6.10 s |

The 43.84 MB private cache produced no consistent speedup across the three
samples per mode. The slowest cached trial exceeded the slowest baseline trial.
The comparison covered import and Uvicorn configuration with networking
denied. It did not exercise application lifespan, database connections,
listener readiness or browsers. It leaves the cause of the 10-second startup
miss unresolved and does not justify using the cache in the authentication
runner.

The separate verifier rehashed both probes' frozen inputs, checked all 2,641
cache headers and allocations, recomputed the medians, and confirmed both
reservations finished and released. Next, record bounded phase timestamps in
the actual isolated API process while preserving the original readiness
deadline and authentication assertions.
