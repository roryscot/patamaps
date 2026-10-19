# Cargo workspace observations

Use the native process provider to retain package, target, dependency and feature facts from Cargo. It does not infer a Rust symbol/call graph, business mappings, macro behavior or successful target compilation. The [actual Axum qualification](../acceptance/project-adoption/g3-actual-axum-replay-2026-10-19/receipt.json) uses this contract without an unrelated graph fixture.

Work in a reviewed owner root. An enclosing project's toolchain/configuration is still ambient configuration when it lies outside that root; the provider refuses it. Use a separate retained copy when needed. Select actual Cargo/rustc binaries (for example, paths reported by `rustup which`), record their SHA-256 bytes, and select an explicit metadata platform. Do not substitute rustup shims for those compiler binaries.

The following template uses the real Axum workspace layout at `fc78d5bcdb276bd6fb53cf2db55e91757eabb469`. Replace tool paths/digests, platform and owner identities before running it; other layouts need their own exact manifest/config/lock input list. A tool digest is `sha256:` followed by 64 lowercase hexadecimal characters. This template is not executable with placeholder values.

Save `workspace.json` in the owner root:

```json
{
  "schemaVersion": "0.1.0",
  "documentType": "workspace-config",
  "id": "urn:project:cargo-observations",
  "namespace": "my-project",
  "revision": "1",
  "sources": [{
    "adapter": "process",
    "id": "urn:project:cargo",
    "invocation": {
      "executable": "/absolute/path/to/patamaps",
      "arguments": ["discover-native"],
      "codeInputs": [],
      "bounds": {
        "maximumElapsedMs": 60000,
        "maximumStdoutBytes": 16777216,
        "maximumStderrBytes": 65536
      }
    },
    "inputs": [
      "Cargo.toml", "Cargo.lock", "axum/Cargo.toml",
      "axum-core/Cargo.toml", "axum-extra/Cargo.toml", "axum-macros/Cargo.toml"
    ],
    "config": {
      "provider": "cargo",
      "nonsecretInputs": true,
      "manifest": "Cargo.toml",
      "workspaceManifest": "Cargo.toml",
      "lockfile": "Cargo.lock",
      "workspaceMembers": "bounded-segment-globs",
      "cargo": "/absolute/path/to/selected/cargo",
      "cargoDigest": "sha256:<replace-with-64-lowercase-hex-digits>",
      "rustc": "/absolute/path/to/selected/rustc",
      "rustcDigest": "sha256:<replace-with-64-lowercase-hex-digits>",
      "cargoHome": "/absolute/path/to/cargo-home",
      "platform": "x86_64-unknown-linux-gnu",
      "features": [],
      "defaultFeatures": true,
      "view": "resolved"
    }
  }],
  "packs": [],
  "policy": "observation-policy.json",
  "projections": [{
    "path": "package-projection.json",
    "emissions": [{"path": "generated/cargo-packages.json", "language": "json"}]
  }],
  "context": {"purpose": "Cargo facts only; no business or operational admission"},
  "evaluatedAt": "2026-10-19T00:00:00Z"
}
```

Save `observation-policy.json`. This policy declares no business constraints; structural viability under it is not application acceptance.

```json
{
  "schemaVersion": "0.1.0",
  "documentType": "policy",
  "id": "urn:project:cargo-observation-policy",
  "graph": {"id": "urn:project:cargo-observations", "revision": "1"},
  "mappings": [],
  "constraints": [],
  "evidence": []
}
```

Save `package-projection.json`:

```json
{
  "schemaVersion": "0.1.0",
  "documentType": "projection-spec",
  "id": "urn:project:cargo-package-inventory",
  "select": {"kinds": ["cargo-package"]},
  "slots": []
}
```

Run `patamaps generate workspace.json --root /absolute/owner` from that owner directory, using the selected executable. Save its stdout in a fresh result file. The returned `baseline.outputs["generated/cargo-packages.json"]` contains the checked inventory JSON; this command does not install or activate it. Extract the returned `baseline` object with your JSON tooling and pass it to `patamaps verify-workspace baseline.json`. Verification checks retained record bindings; it does not rediscover source or rerun Cargo. Keep baselines and failed attempts rather than overwriting them.

Discovery requests locked, offline Cargo metadata. Prepare an absent dependency cache as an explicit, supervised step using the reviewed lockfile, then rerun discovery; do not let discovery update the lockfile. `declared-local` requests `--no-deps` and reports no resolved feature set. `resolved` reports the observed resolver graph. In the qualified Axum workspace, explicit `axum/ws` added `ws`, while disabling defaults retained the same workspace feature set. Neither result proves a target was built with a particular feature configuration.

Literal members remain the default. `bounded-directory-globs` allows a whole `*` directory segment; `bounded-segment-globs` additionally allows one prefix/suffix star such as `axum-*`. Recursive/multiple-star patterns, matching symlinks/files and missing captured manifests refuse. Literal exclusions require their separate explicit opt-in. See [Decision 0042](../decisions/0042-bounded-cargo-segment-globs.md) for bounds. Isolated packages without an enclosing workspace require `rootMode: "standalone-package"`.

Capture all required manifests and applicable nonsecret configuration/toolchain files. The supported Cargo config subset is matching `build.target` and `net.offline=true`; executable overrides and other unimplemented keys refuse. A selected toolchain file must name the exact selected rustc release. Private ambient config is not copied to make discovery succeed.

These records bind selected inputs and observed tool/cache output. Cargo can consult source-file presence and cached dependency metadata beyond the selected manifests; this is not a hermetic build or complete source/executable dependency closure. Use [retained contexts](retained-contexts.md) and [retained builds](retained-project-builds.md) for explicit build inputs and execution. Configured-path-unavailable replay is separate from operating-system denial of all host source/tools. The [support matrix](project-support-matrix.md) records current acceptance limits. This guide was added after the frozen 2026-10-19 package qualification; that archive's inventory remains authoritative for its contents.

For the separate existing-project Linux compilation gate, CI runs
[scripts/qualify_axum_linux.py](../../scripts/qualify_axum_linux.py) on the pinned
public Axum workspace. It explicitly fetches that source and locked registry
dependencies before offline metadata/build/test commands; this network
preparation is outside the native observation provider. A passing receipt must
include compilation of every observed workspace member and unchanged tracked
source, not merely successful metadata. The gate is pending execution when
introduced. It does not qualify a deployed server or hermetic dependencies.

The [actual Linux build follow-up](../acceptance/project-adoption/g3-actual-axum-linux-build-2026-10-19/receipt.json)
passed in CI39296124316 at4f31b73 (tested merge847b0e7, identical tracked tree):
all four pinned Axum workspace libraries compiled, and459 upstream library tests
passed with zero failures/ignored tests. All505 tracked source hashes remained
unchanged. The metadata provider continued to report compilation false; separate
Cargo commands established this build/test result. Registry/cache closure,
retained-project-build orchestration, independently inspected binary architecture,
HTTP deployment, Next Linux/application/browser qualification and performance
acceptance remain open. Timings are observations, not a cold-build benchmark.

A follow-up CI refinement makes the Linux build/test target explicit, checks the
actual proc-macro shared library's ELF64/little-endian/x86_64 header and refuses
tampered architecture/truncated header controls. It also retains an exact
compiler/engine/library payload with member-by-member digest verification.
Execution of this refinement is pending; the459-test receipt predates it.
Rust archive object architectures are not independently inspected by that header
check. Artifact retention does not establish installation, HTTP deployment or
production release authorization.

The [retained Linux payload follow-up](../acceptance/project-adoption/g5-linux-tool-payload-2026-10-19/receipt.json)
passed all four CI39301564209 jobs at2cf2eb9 (tested mergebf16fee, identical
tracked tree). All459 upstream tests passed with the explicit Linux target.
Independent bounded inspection verified the uploaded archive SHA-256, all ten
payload members, and compiler/proc-macro ELF64/x86_64 headers. The retained
payload is52,937,102 logical bytes (17,629,458 compressed bytes). Rust archive
object architecture and Intel/application runtime acceptance remain separate.
No library payload was installed or executed by this independent inspection.
