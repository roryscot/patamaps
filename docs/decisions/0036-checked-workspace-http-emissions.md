# Checked HTTP emissions in workspace baselines

Status: implemented with frozen integration controls; execution pending. G4 orchestration remains incomplete.

Extend existing WorkspaceConfig emissions.language with http-client and
axum-witness, using the existing checked projection emitters. Reuse generate,
WorkspaceBaseline captures/output bounds and verify-workspace reconstruction;
no separate graph or verification framework. Existing JSON/Rust/TypeScript
formats and standalone link behavior remain unchanged. HTTP formats use their
declared profile slots; a bindingSlot override must refuse instead of being
silently ignored. Multiple Rust modules use existing separate projections.

Workspace generation records output strings; this change does not write generated
files, build an application, select a candidate or activate it. Module source
locators/digests remain owner declarations; the integrating driver must capture
and recheck actual module bytes. Reconstructed output bindings are not code
execution, source authentication, current authorization or Serde equivalence.

Acceptance uses the controlled real Axum transport consumer: generate admitted
client/witness outputs through a workspace; compare them with standalone link on
the exact composed checked graph (integration consistency, not independent parser
validation); compile and run the actual consumer with the workspace-derived bytes.
Verify the baseline after configured graph/policy/projection/pack paths are
unavailable and external PATH is empty. A rehashed tampered output must refuse;
an HTTP bindingSlot override must refuse. Retain every failed attempt. Real
Wargame schema/native-witness/Next qualification and general orchestration remain
separate required adoption work, not replaced by this controlled consumer.
