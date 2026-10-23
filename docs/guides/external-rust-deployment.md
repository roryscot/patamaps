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
accept arbitrary Miniserve options, authenticated applications,
full dependency/test-context closure, performance, production activation or
registry publication. Fresh exact source/native package installation is now qualified for the frozen application as described below. A CI receipt and
digest chain are not an independently reproduced build or a signed attestation.

The new selected-execution command is a checkout feature added after published
patamaps-cli 0.1.0-alpha.1. For a first Rust integration, use the
[Rust quickstart](rust-project-quickstart.md). Broader Docker context coverage, complete dependency closure and exclusive
edit-loop measurements remain in the [enhancement backlog](../plans/integration-enhancement-backlog.md).

## Exact installed consumer

The [installed-consumer receipt](../acceptance/project-adoption/g5-miniserve-installed-20261023/ci.json) qualifies source/native packages created at c6b58517e19ef68b99ca9a7a215ed661cf01c390 using the frozen creating Linux compiler. Before packaging, all nine production source Git identities were checked against the producer. Exact archive digests, all 1,071 installed source members and bytes, and both installed compiler engine records passed. Source installation used a fresh Cargo prefix with locked/offline compilation after an explicit locked dependency fetch; its debug binary differs from the packaged release binary. This does not claim independent binary reproducibility or closed dependency provenance.

The driver inside installed source repeated selected-state verification and all eight HTTP controls with each installed compiler. Changed runtime content refused before command effects; restored bindings passed. Miniserve passed again after the producer and both test-installed compiler paths became unavailable. Full source membership/bytes, selected candidate bytes and its pointer were unchanged afterward. No fixture driver was imported, and Miniserve was not recompiled.

To repeat this focused maintainer qualification while the frozen artifact remains available:

    gh run rerun 39897900519

The lane refuses expired or changed frozen evidence. Its exact unpublished source/native packages remain in the linked run's 14-day artifact; compact receipts are committed. Import retained state with its archived directory modes intact. Python's default data filter discards those modes: the first attempt was refused, and a mode-preserving importer passed nine controls plus direct verification of the exact frozen state before the successful rerun. No stored binding was regenerated to make that import pass.

## Actual image and browser profile

The [image/browser qualification](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/ci.json) builds a linux/amd64 image from the exact selected bundle and digest-pinned Ubuntu base. The observed executable inside the running image matches the selected SHA-256 and native ELF target. Image/entrypoint/user/workdir settings were inspected; an actual entrypoint override was refused before startup. The original Miniserve executable, configuration, launcher and document were unchanged.

The image runs as 65532:65532 with readonly root, no source bind mount, one CPU, 256 MiB memory, zero swap, 64 PIDs, and kernel-verified 1 MiB /tmp and /dev/shm mounts. Its fixed loopback launcher uses host networking in dedicated Linux CI; this result does not establish network isolation. Chromium completed six controls: rendered listing, real file-link navigation and document text, history return, missing-document refusal, out-of-prefix refusal, and no script errors/off-origin requests. Both owned containers and the listener were confirmed stopped.

    gh run rerun 39899991879

The same lane repeats fresh source/native installation, all nine archive controls and two Linux socket controls. The [receipt](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/ci-receipt.json) freezes its 1,078-file installed source inventory; this is a later package than the 1,071-file installed-only milestone. The artifact retains compressed image and packages for 14 days; committed receipts and the [listing screenshot](../acceptance/project-adoption/g5-miniserve-image-browser-20261023/browser-listing.png) remain. Archive digests were checked at intake, but fresh image reload was not exercised.

At this historical image/browser snapshot, native Docker discovery required a complete UTF-8 context inventory. That run verified its binary-bearing context through digests and actual BuildKit/image observations. The newer [native snapshot-backed context](docker-context-snapshots.md) now qualifies opaque binary discovery, staging and actual image runtime under a new engine. Complete dependency/test-context closure, current external installed/browser replay, broader framework boundaries and practical development performance remain open. No registry publication or production/trust activation occurred.

The current native binary-context feature changes the workspace engine. Historical installed/image receipts remain frozen to their tested compiler; use the rerun commands above for those jobs. The [snapshot-backed Docker guide](docker-context-snapshots.md) describes the new contract and its separately qualified current-compiler path.
