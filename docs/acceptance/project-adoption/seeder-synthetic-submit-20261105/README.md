# Focused Chromium and WebKit form submission on the accepted Seeder build

The first diagnostic failed before browser execution because the launcher
referenced a missing standalone runtime. Its cleanup tried to inspect a
missing process ID. The guard released, and a separate stopped-state check
restored all three moved producer paths with their original file identities.

The corrected diagnostic copied the selected standalone files and compiled
assets using the same hash-checked mapping as the real authentication
launcher. It ran two browser cases against the same accepted frontend with
the API origin denied by the proxy. No API or database started. Both
Chromium and WebKit accepted the synthetic form inputs, completed the
click, observed a native submit event and attempted one login POST.
WebKit recorded one browser error outside the diagnostic's named error
classes. It did not match the previous blocked-port signature. The form
handler console marker was absent in both browsers and is inconclusive.

This narrows the [real WebKit timeout](../seeder-webkit-submit-timeout-20261105/README.md)
without reproducing it. The focused cases omit the real API reset and
permission flow and leave authentication acceptance open. Separate review
rehash-checked 28 frozen inputs, confirmed producer restoration and owned
process shutdown, and verified reservation release.
