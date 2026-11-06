# Mobile Chrome passes with visual-viewport-relative touch input

The focused real Mobile Chrome run measured a 361-pixel horizontal visual
viewport offset after scrolling the drawer link into view. Its layout
scroll stayed at zero. This exactly matches the displacement measured
in the earlier failed run. The test sampled a stable visible point at
(591, 306), sent a normal touch at (230, 306) relative to the viewport,
and observed a trusted click on the exact expected link at (591, 306).

The original real login, navigation and permission case and both invalid
and expired session cases passed. Both role cases opened and dismissed
the drawer. All 31 preflight controls and 12 direct HTTP cases passed.
The accepted frontend and original application source were reused.
Independent review verified ownership, preserved data and selected
artifacts, stopped resources and a released reservation.

This accepts the focused Mobile Chrome scope. Mobile Safari and the
complete five-project run still require independent acceptance.
