# 0023 — Native comparison diagnostics

Status: implemented and verified by focused, independent, full compiler, installed-consumer and actual Linux checks.

## Observed gap and scope

The [independent CLI baseline](../acceptance/capabilities/comparison-independent-2026-10-15T03-55-13.554475Z/receipt.json) verified viable and rejected captures, then observed that a duplicate graph identity made comparison refuse the entire report. Consumer-only and policy-only changes produced no diagnostic origins, and the CLI had no explicit diagnostic origin option.

Reuse capture replay, the stable-ID diff, the existing occurrence-aware record comparison and the bounded core impact traversal. Preserve original tests and reference bytes. This change supplies diagnostic information; it does not change admission, source extraction, captured results or authorization.

## Contract

- Rust compare_with_origins and CLI compare BEFORE AFTER --origin SUBJECT add up to 256 valid diagnostic subjects, including for identical captures. Existing compare remains the default without explicit subjects.
- diagnosticOrigins distinguishes graph edits, explicit diagnostics and conservative potential references from changed policy or consumer records. Graph document metadata alone does not seed dependency paths. Selector-based policy changes conservatively include potentially affected mappings rather than duplicating the admission selector engine. Origins are bounded to 256; consumer selection work is bounded to 2,000,000 entity-selection operations. Incomplete origin discovery makes all path reports unavailable.
- A duplicate-ID graph rejection retains an occurrence-aware comparison. Each changed identity retains the complete sorted digest multiset; a single-record digest is null for a repeated identity. Checked graph/admission paths remain unavailable for invalid graphs. The standalone core unique-ID diff continues to refuse ambiguity.
- issueDelta compares exact recorded findings as multisets. issueStages reports compilation, projection and path-tree differences only when the corresponding stage is known in both captures. Collection capture 0.2 preserves those boundaries. A rejected historical single-profile capture does not identify its failure stage. Unrequested or unevaluated stages retain null introduced/resolved changes; missing findings cannot become a false resolution.
- declaredPaths follows authored directions on the checked graph. admittedPaths independently recomputes admission using the exact captured graph, policy, packs, context and time, then follows only active authored mappings. An inactive mapping origin remains unavailable. Projection usability is a separate outcome.
- Recorded premise→derivation→result paths retain decision 0022's limits and validity boundary. A recorded claim is not promoted to a checked proof, admitted path, scientific truth, present authorization or unique causal explanation.

## Acceptance

Verify identical-capture explicit diagnostics, invalid/missing/bounded origins, duplicate graph occurrences, metadata-only changes, consumer/policy origins, introduced and resolved collection findings, unknown stages for legacy rejection and failed compilation, inactive mappings, deterministic immutable output, and all existing cycle/depth/output controls. Reuse the unchanged independent baseline driver after repair, requiring all four formerly unavailable capabilities. Refresh the compiler workflow, installed consumer and current platform/package evidence at the milestone.

The [final focused run](../acceptance/capabilities/comparison-diagnostics-focused-2026-10-15T04-04-15.632871Z/receipt.json) passes all comparison controls, core regression tests, CLI build, projection Clippy and original-source integrity. The [unchanged independent probe](../acceptance/capabilities/comparison-independent-2026-10-15T04-05-08.395382Z/receipt.json) passes with all four diagnostic capabilities required. Original cycle/depth/output assertions remain unchanged.

The full compiler run exposed an inspector test that expected duplicate-removal comparison to remain unavailable. The repair workflow now asserts a successful occurrence-aware comparison with the exact two-to-one digest inventory, keeps the invalid baseline paths unavailable, checks valid candidate paths, and retains approval-required status. Keeper-preservation and protected-edit assertions remain unchanged. This updates the former limitation to the new capability contract; it does not alter reference expectations.

The source-inspection and workspace candidate comparison controls had the same historical limitation. They now assert a comparable occurrence inventory while retaining rejected admission, null risk, unknown mapping transitions, all selected ambiguous records, unavailable unique-ID source-to-candidate deltas and no activation. Original reference expectations remain untouched.

[All ten complete compiler stages](../acceptance/capabilities/compiler-2026-10-15T04-12-38.667740Z/receipt.json) pass on the final formatted source, including unchanged reference comparisons, native repair/source/workspace integration, generated consumers, formatting and whole-workspace Clippy.

Current [installed diagnostic controls](../acceptance/capabilities/comparison-independent-installed-2026-10-15T04-25-12.071240Z/receipt.json) and [both Linux architectures](../acceptance/capabilities/linux-ci-38680593872/local-retention.json) pass on implementation 956f1a8. The [capability acceptance record](../acceptance/capabilities/package-reproducibility-956f1a8/capability-acceptance.json) records final workflow and archive outcomes.
