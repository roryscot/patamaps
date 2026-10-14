# Bounded inspector focus

The pinned reference explanation test requires the explicitly selected record
to remain visible when subject/mapping limits truncate the surrounding view.
The native inspector took the first IDs in key order before considering focus,
so a known selection could disappear from its rows.

Keep the existing checked report, immutable capture and limits. Order each view
by the explicitly selected ID for its record kind, then declared dependencies,
then other records, with stable ID order within each group. Apply the limit only
after that ordering. Keep all duplicate occurrences within a selected ID's row;
the limit counts IDs, never chooses one conflicting occurrence.

Acceptance: last-in-order entity and mapping selections survive limits of one;
selected duplicates remain ambiguous and complete; omitted counts stay exact;
missing selections remain explicit without fabricated records or bindings; input
captures remain byte-identical. Original assertions and reference tests remain.
This fixes focus retention, not source-to-candidate attribution.
