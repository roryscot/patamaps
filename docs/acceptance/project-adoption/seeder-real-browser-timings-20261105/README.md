# Real Seeder login timing on the accepted frontend

The original cases and limits ran on Norway with additive timing markers.
The freeze bound 464 inputs. Removing only the timing lines reproduces the
prior browser test byte for byte. All 31 preflight controls, 12 direct HTTP
cases and six Chromium/Firefox cases passed. WebKit again timed out and eight
following browser cases were skipped.

In the failing WebKit case, the API reset finished at 9.023 seconds, the
login page loaded at 10.589 seconds and Playwright reported the click
returned at 10.934 seconds. The test still recorded zero API-origin browser
events before its 20-second deadline. This localizes this run's failure
after the click and before an observed login request. It does not identify
whether native form submission, client handling or transport caused the
failure. [The synthetic comparison](../seeder-synthetic-submit-20261105/README.md)
reached the POST in both engines with the API denied and a simpler browser
context. Its result does not prove real login.

The unchanged reviewer first refused the instrumented spec at a raw-byte
equality assertion. A separately retained reviewer verified the exact
original bytes after removing timing lines, then applied the existing
ownership, result, resource cleanup and preservation checks. It confirmed
reservation release and preserved the failed authentication result. The
full browser matrix remains open.
