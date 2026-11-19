# Stable Mobile Chrome hit target without a recorded trusted click

The isolated real Mobile Chrome attempt found all 25 sampled points on
the edited link before scrolling and in three stable post-scroll
observations with the drawer animation stopped. It dispatched a normal
touch at the sampled point. The listener attached to the exact link
did not record a trusted click. The run stopped before the later
route and permission assertions and skipped two session cases.

The probe did not capture the actual event target, and the link-local
listener could be invalidated if the application replaced the anchor.
These limitations leave the source of the discrepancy unresolved.
A document-level observer can separate a replaced anchor, viewport
coordinate translation and an intercepting element.

Independent review verified all 31 preflight and 12 direct HTTP cases,
preserved data and selected artifacts, stopped owned resources and
reservation release. The full authentication matrix remains open.
