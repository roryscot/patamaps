# Mobile Chrome delivered a touch at a different horizontal coordinate

The focused check attached its event observer to the document. The
accepted frontend still reported all 25 points on the expected link
after scrolling and settling. The normal touch was sent at (591, 306)
CSS pixels. Mobile Chrome delivered trusted pointer and touch events to
a different target at (952, 306). No trusted click reached the link.
The browser reported scale 1. The 361-pixel horizontal displacement is
measured; the relevant viewport offsets were not captured in this run.

All 31 preflight and 12 direct HTTP cases passed. The one Mobile Chrome
case stopped at the touch and two later cases were skipped. Independent
review verified preserved resources and selected artifacts, stopped
owned work and reservation release. The next check will measure the
visual viewport offset and use a coordinate inside that viewport.
