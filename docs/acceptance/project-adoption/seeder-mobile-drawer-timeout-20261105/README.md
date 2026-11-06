# Seeder Mobile Chrome drawer opened before the permission UI timeout

The five-project run retained the form-readiness check and added a wait
for the actual mobile layout and visible drawer. It kept the original
login, permission, link, route and denial assertions and all deadlines.
All 31 preflight checks, 12 direct HTTP checks and nine desktop browser
cases passed again.

Mobile Chrome logged in, received the permission response, and opened the
mobile drawer. Its first case still timed out before recording drawer
dismissal. Five later cases were skipped. The failure's saved
accessibility snapshot contains the exact edited link as a link in the
drawer, and the expected admin route. This establishes that the link was
present in the captured state. It does not show when the link became
visible or which visibility wait consumed the remaining time.

Independent review verified stopped owned resources, exact producer
restoration, unchanged selected artifacts, preservation of failed owned
data and reservation release. The next focused Mobile Chrome diagnostic
should record link count and visibility before and after the original
assertion. The full browser matrix and the wider adoption goal remain open.
