# Desktop WebKit real authentication with form readiness

The test waited for the pinned React DOM submit handler before filling the
login form and checked native input validity before the existing click. It
kept the original authentication and permission assertions, accepted
frontend and test deadlines. In both WebKit sessions the handler was absent
at the first observation after navigation and present after the wait. Both
then produced a native submit, the real POST 200, the owned user response
and the discovery redirect. WebKit also passed invalid and expired session
rejection. This supports the form-readiness explanation for the previous
post-click failures, without proving their precise timing.

All 31 preflight checks, 12 direct HTTP cases and nine browser cases across
Chromium, Firefox and desktop WebKit passed. Mobile Chrome logged in and
received the permissions response. Its first case then timed out while
awaiting visible UI. Five remaining browser cases were skipped. The owner
app renders a separate mobile navigation drawer after detecting its
viewport. The next harness check waits for that drawer and preserves the
existing exact link, route, heading and denial assertions.

Independent review verified preserved owned data, the unchanged selected
frontend and unrelated database, stopped owned resources and reservation
release. The full five-project matrix remains open.
