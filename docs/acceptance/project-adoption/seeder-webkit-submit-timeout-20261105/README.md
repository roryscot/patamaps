# Seeder WebKit submit timeout with a ready API

The unchanged authentication matrix used the previously accepted frontend and
froze 459 inputs. A test-wrapper trace measured Uvicorn import, application
configuration and server startup without changing the readiness or test
deadlines. All four observed API instances completed startup. The WebKit
instance reached the end of Uvicorn startup 7.83 seconds after bootstrap entry
and passed the original owned-listener readiness check. In the traced
instances, configuration and app import consumed 5.10 to 7.12 seconds and
server startup took 0.31 to 0.46 seconds. These timings describe this run and
do not establish the cause of the earlier startup miss.

All 31 preflight checks, 12 real HTTP checks and six Chromium and Firefox
browser cases passed. WebKit logged the stage immediately before the click
and recorded no API-origin browser events. Its original 20-second test
expired while awaiting the login flow. The trace does not establish whether
the click finished, the app handled submit, or WebKit attempted a transport
outside the observed request events. Eight cases were skipped after the
failure. Full five-project acceptance remains open.

The independent review verified resource cleanup, reservation release and
preservation of the selected frontend, owned data and the unrelated running
database. The next focused check will distinguish form readiness, click,
submit handler and outbound request without rerunning the frontend build.
