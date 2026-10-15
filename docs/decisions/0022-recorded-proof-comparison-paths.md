# Recorded proof dependency paths in native comparison

C09 review found that declared graph directions did not explain a removed
premise through its recorded derivation to the inferred mapping. Comparison now
adds `recordedProofPathsBefore` and `recordedProofPathsAfter`, separate from the
existing declared graph report. Origins include changed graph identities and
added, removed or changed derivation identities. Edges are premise mapping to
recorded derivation ID, then derivation ID to recorded result mapping ID.

The report describes recorded identifiers even when the verified capture records
rejection. It establishes no proof validity, admission, current authority or
unique causal responsibility. Duplicate derivation IDs remain explicitly
ambiguous; cycles terminate. Unavailable consumer and risk results stay unknown.

Traversal permits 256 origins, depth 64, 10,000 visits, 20,000 indexed edges and
2,000,000 traversal operations. Indexed identifier bytes and a conservative
serialized-path-record budget are separately bounded at 16 MiB. Exhaustion is
explicitly incomplete; excess origin count is unavailable. The comparison also
retains occurrence-aware constraint/evidence/waiver deltas and recorded support
presence changes without claiming evidence validity or scientific truth.

[Focused comparison tests and clippy](../acceptance/capabilities/comparison-focused-2026-10-15T03-22-29.079682Z/receipt.json)
pass actual rejected-premise traces, immutable inputs, repeated reports, cycles,
duplicate proof IDs, evidence changes and origin/depth/output bounds. C09 remains
open for explicit diagnostic seeds, consumer/policy-derived origins, structured
introduced/resolved issue stages and admitted-versus-declared path reporting.
