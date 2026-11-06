# Seeder mobile link hit testing and locator tap disagree

The focused Mobile Chrome case logged in and opened the drawer. All 25
points in one clipped-link sample resolved to the exact link or a
descendant. The subsequent normal Playwright locator tap nevertheless
timed out and reported pointer interception during its actionability
checks. No force action was used. The original route and later assertions
did not complete, and two session cases were skipped. This result does
not establish that the drawer backdrop continuously covers the link.

The independent review confirmed all 31 preflight and 12 HTTP checks,
selected artifact and owned data preservation, stopped resources and
reservation release. The next diagnostic can sample the actual link
after scrolling and settling and verify that a normal touch dispatches
a trusted click on it. Full authentication remains open.
