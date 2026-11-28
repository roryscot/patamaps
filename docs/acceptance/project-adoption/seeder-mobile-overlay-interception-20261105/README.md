# Seeder mobile drawer backdrop intercepts the visible navigation link

The focused Mobile Chrome run kept the original real authentication and
permission assertions and used a touchscreen tap with a three-second
action deadline. All 31 preflight and 12 direct HTTP checks passed. The
allowed user logged in, the drawer opened, and the original visible-link
and exact-href assertions completed.

The tap did not reach the visible link. Playwright reported a fixed open
element intercepting pointer events. Its reported class markers match the
original Seeder Sheet backdrop, including the full-screen inset and the
fade-in state. The two later session rejection cases were skipped. This
identifies the intercepting layer in this run. It does not establish that
every visible point on the link is blocked or explain the precise CSS
stacking order.

Independent review verified retained source and output bindings, stopped
owned resources, preserved owned data and a released reservation. The next
bounded check will determine whether the existing drawer exposes a
normally tappable part of the link. Full browser acceptance stays open.
