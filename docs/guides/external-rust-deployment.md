# External Rust deployment: Miniserve qualification

This profile qualifies unchanged Miniserve 0.35.0 at source commit
2cd9c495ef25f2fcef505615f603e9de8f981915. It complements the existing Axum and
Wargame results with an independently owned Actix application. The graph declares
deployment intent; it does not infer the application's business semantics.

The [CI receipt](../acceptance/project-adoption/g5-miniserve-source-runtime-20261023/ci-receipt.json)
records source compilation, all 325 default upstream tests on the selected Linux
GNU target, eight HTTP/startup controls and four refused selections. The
[Intel receipt](../acceptance/project-adoption/g5-miniserve-source-runtime-20261023/managed-replay.json)
records the exact selected state and creating compiler running again with CPU,
memory, swap, mount and writable-filesystem limits.

## Contracts used

The qualification uses the public native commands outside the cross-stack example:

    patamaps project-context-capture selection.json --root source --destination snapshot
    patamaps project-context-stage snapshot --destination staged
    patamaps project-capture source-profile.json --root staged --output source-capture.json
    patamaps project-exec source-capture.json cargo-command.json --root staged
    patamaps project-build plan.json --source owner --state isolated-state --context binding.json
    patamaps project-build-verify isolated-state
    patamaps project-exec-selected isolated-state runtime-command.json

These are command shapes, not a turnkey plan for another application. Declare
and review that application's paths, correspondences, tools, nonsecret settings,
outputs and verification requirements. A Rust component uses kind cargo-package.
Build state must be outside enclosing Cargo workspaces and within the applicable
supervisor's accounting roots. Commands are trusted; native execution alone is
not a sandbox. Use the existing project guard on Intel.

The exact owner recipe is in scripts/deployment/miniserve. Its reviewed
service.json admits only the fixed tested loopback/static-document profile.
prepare_bundle.py validates configuration before writing the bundle; the native
ELF checker binds its digest and target. probe.sh checks actual GET/HEAD/listing
behavior and refusals before native selection publication.

The selected artifact includes its launcher, nonsecret configuration proof,
document and executable. A late artifact change refuses project-exec-selected
before command effects. The cooperative state lock remains held through
execution and post-verification. A failed runtime/config/digest/architecture
verification preserves the previously selected generation.

## Reproduction and provenance

The focused manual entry is the existing native-capabilities workflow:

    gh workflow run native-capabilities.yml --ref feat/retained-owner-preparation -f qualification=external-rust

A dispatch builds the checkout CLI, fetches the exact upstream revision and
locked dependencies, stages captured build source, and runs explicit Linux GNU
release build/test commands. Failure controls reuse the produced executable.
The default tests use the original pinned public clone because their eight
reviewed TLS/auth fixture files stay outside every Patamaps capture. Their exact
Git blob identities are checked; unknown or changed fixtures refuse. No test,
source or fixture bytes are patched. That test data is an external dependency.

The artifact contains exact compiler/application bytes, licenses, selected state
and failed-attempt JSON records. Verify the GitHub artifact digest, inner state
archive digest, creating compiler digest and selection digest before use. The
Intel import also passed native verification using the same engine identity
before the Linux executor started. Preserve archive permissions; do not repair a
binding refusal by changing declared outputs or recomputing their evidence.

The managed run uses the cached pinned Ubuntu image, one CPU allowance,
268435456 memory bytes, zero swap allowance and a 67108864-byte filesystem
ceiling. Root is readonly, networking is isolated to the container, source is
not mounted, and /work is the only writable bind mount for outputs. It repeats all eight runtime
controls through the creating CLI's project-exec-selected command. The executor
confirms its own container/processes stopped before releasing the reservation.

## Acceptance limits

The result covers this source, target, configuration and controls. It does not
accept browser rendering, application-image builds/observations, arbitrary Miniserve options, authenticated applications,
full dependency/test-context closure, performance, production activation or
registry publication. It uses fresh relocated compiler bytes; the package
installer itself has not been exercised for this application. A CI receipt and
digest chain are not an independently reproduced build or a signed attestation.

The new selected-execution command is a checkout feature added after published
patamaps-cli 0.1.0-alpha.1. For a first Rust integration, use the
[Rust quickstart](rust-project-quickstart.md). Packaging/installation and exclusive
edit-loop measurements remain in the [enhancement backlog](../plans/integration-enhancement-backlog.md).
