# Recorded sources and a distinct candidate

The pinned source replay and explanation assertions require a verified full
source composition alongside a separately evaluated candidate. A raw receipt
list cannot establish source membership or the relationship between those graphs.

Reuse `VerifiedWorkspace`, capture/replay, graph diff and existing governance.
A `patamaps-source-evaluation-draft-1` envelope binds a complete workspace baseline
and candidate capture under its own native address. Creation takes an already
verified workspace and explicit candidate inputs; verification reconstructs the
workspace and replays the candidate without live reads or provider execution.
The candidate must retain the workspace graph ID and its complete raw receipts.
An additional reserved receipt binds the full baseline digest and executors into
the candidate capture. Provider/source-only changes therefore require a different
capture and fresh approval even when semantic records are unchanged. Collision
with that reserved receipt refuses rather than replacing user data.

Inspection reports the source graph versus candidate-input graph, metadata-only
changes, and exact membership from recorded shards, including all occurrences.
It labels recorded ownership and provider declarations separately from truth,
authentication, current authorization and activation. Comparisons use both
verified baselines plus the existing candidate comparison so rejected expressions
and unavailable risk remain unknown. Reports are computed; serialized reports
cannot mint checked state. The existing inspector and renderer consume this
verified context rather than inferring provenance from labels or paths.

Acceptance: independently owned shards, identical/distinct/rejected candidates,
metadata-only and source-only changes, precise membership and duplicate counts,
full source/receipt/envelope substitution controls after rehashing, and private
checked-type controls. Capture creation, verification, comparison and inspection
must preserve all inputs, avoid source locator reads, and bind source changes into
the candidate used by existing artifact/approval verification. No signer, private
key or deployment action enters this API.
