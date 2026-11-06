# Paired Seeder browser context observation

The accepted corrected frontend served the same synthetic login form to
Chromium and WebKit with an empty session and a proxy that denied the API
origin. Each browser tried the default context and the exact owner device
options used in the real acceptance harness. The experiment applied those
conditions in opposite orders across the two browsers.

All four observations recorded a valid form, a completed click, one native
submit and one attempted login POST. The owner profile did not reproduce the
[real post-click WebKit timeout](../seeder-real-browser-timings-20261105/README.md).
The scope still differs from real authentication because the API was denied,
the database and owned user data were absent, and other projects had not run.
Independent review verified 31 frozen inputs, restored producer paths and
stopped owned processes and reservation release.
