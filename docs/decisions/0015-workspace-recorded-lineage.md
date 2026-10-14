# Offline workspace lineage verification

The C08/C15 audit of the pinned reference `provenance.test.ts`,
`source-replay.test.ts` and `current-sources.test.ts` found a substantive gap.
MetaMap reconstructs the source graph from the exact recorded configuration and
ordered discovery inventory. Patamaps checked each capture and each shard, but
did not reconstruct their relationship or the emitted workspace files.

[The retained observation](../acceptance/capabilities/source-lineage-gap-2026-10-14/observation.json)
changes a recorded discovery source ID and recomputes the baseline address.
The installed CLI reports ordinary drift against this inconsistent historical
record. It does **not** show that a forged record can obtain unchanged acceptance
or authorize deployment. The missing guarantee is complete offline record
consistency, before current-source comparison.

Reuse `workspace-baseline`, source receipts, composition, capture/replay and the
existing emitters. One shared pure assembly function will build both new records
and their offline reconstruction. A private checked wrapper will expose a
verified baseline only after recomputing configuration, ordered source inventory,
raw input bindings, discovery requests, composed graph, captures and every emitted
file. `check` must verify the historical baseline before reading current sources.
The CLI will expose this through `verify-workspace` without a root or cache.

The composed graph retains the authored revision and adds a
`workspaceLineageDigest` metadata binding over the workspace executor,
configuration and complete ordered discovery records. Provider version, source
revision and raw-input/code request changes therefore change the evaluated
capture even when semantic entities are identical. An earlier approval cannot
silently authorize the changed capture. This derived metadata does not transfer
ownership or establish the truth of a provider's declaration.

Process discovery retains the executable digest needed to reconstruct its
invocation/request address. This is a recorded digest, not authentication of a
provider, proof of discovery truth or a promise to rerun the executable. Offline
verification never follows source locators, loads a named adapter, reads a clock,
changes files or claims current authorization. Receipt-only raw bytes remain
explicitly unavailable to this reconstruction; ordinary graph replay may still
verify without them. Earlier baselines retain their old workspace executor and
are never silently relabelled as this implementation's results.

Acceptance requires independent controls for ordered/missing/duplicate discovery,
configuration/request substitutions, changed raw bytes and paths, changed packs,
individually valid captures from a different composition, altered outputs and
rejected evaluations. Rehashing an outer record must not conceal these changes.
Portable and process records must reconstruct with Node absent, with source files
unavailable and without executing the recorded provider. Current drift must remain
explicit and leave the saved baseline unchanged. Installed CLI verification and
required platform checks must bind their actual source and binary identities.

This repair does not by itself complete the 53-suite substantive audit. A distinct
candidate graph can still be evaluated through the existing compiler; any further
source/candidate comparison guarantee found during that audit stays open.
