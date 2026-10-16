# Explicit project inputs (draft profile 1)

The native commands accept existing projects without a catalog directory layout:

    patamaps project-capture project.json --root /absolute/project --output capture.json
    patamaps project-verify capture.json --output verified.json

The output path must have an existing parent and refuses replacement by default.
This stage captures inputs; it does not execute discovery, compile a project, admit
correspondences, verify an HTTP API or activate a deployment.

A profile has this shape:

```json
{
  "profile": "patamaps-project-inputs-1",
  "id": "urn:project:owned-service",
  "nonsecretInputs": true,
  "inputs": ["backend/Cargo.toml", "frontend/package.json"],
  "components": [
    {"id": "api", "kind": "cargo-package", "root": "backend", "entrypoints": ["backend/Cargo.toml"]},
    {"id": "web", "kind": "next-app", "root": "frontend", "entrypoints": ["frontend/package.json"]}
  ],
  "nonsecretConfiguration": {"publicOrigin": "https://example.invalid"},
  "secretReferences": {"database": "DATABASE_URL"}
}
```

Each entrypoint must be selected in inputs and fall below its component root.
The root "." denotes the whole selected project. Component kinds are next-app,
cargo-package, configuration, contracts and deployment. They declare owner intent;
a next-app label alone does not prove that Next is installed or a route exists.
No project commands execute here. Later stages use the existing workspace
providers and checked projections with these exact SuppliedInput records.

Select only files the owner has reviewed as nonsecret. Captures retain complete
UTF-8 bytes. Configuration is owner-declared data; it is not a redaction
instruction. Secret references contain environment variable *names*, never
values. Neither command looks up those names. Never supply a secret-bearing file
because a desired field appears harmless. The guard also refuses .env/.env.*
(including examples), .git, node_modules, target and .next inputs; it cannot
recognize arbitrary secrets embedded in an innocently named source file.
Provide independently reviewed nonsecret configuration documents where needed.

Strict native JSON rejects unknown fields and duplicate keys. Explicit file
paths replace globs: at most 1,024 inputs and 128 named components. The profile
is bounded to 256 KiB; raw inputs and the serialized capture each stay below the
normal 16 MiB CLI limit. Paths must be normalized and relative. All path
components are opened with NOFOLLOW on supported Unix hosts; symlinks, FIFOs,
directories and non-UTF-8 inputs refuse. The root itself must not be a symlink.
Selected files are re-read before return to detect ordinary edits. This is
sequential file observation, not an atomic filesystem snapshot or protection
against a malicious host.

The capture binds the complete definition and sorted exact input records using
the existing native canonical digest. It contains no absolute source root.
Offline verification needs only the record, checks membership, content bytes,
lengths and hashes, and reports verified-project-input-bindings with admission,
tool execution, rediscovery, secret resolution and activation not performed.
Anyone can author another coherent capture: hashes are integrity bindings, not
source authentication, current authorization or a signature.

Run the focused native tests through the Intel supervisor:

    cargo test -p patamaps-workspace --test project --locked --offline

The retained existing-project driver scripts/project_qualification.py records
read-only selected-input capture and offline replay against Wargame and Seeder.
That qualification is explicitly limited to G1, not their full runtime acceptance.
See the [general adoption plan](../plans/2026-10-15-general-project-adoption.md)
for the required HTTP, framework, development, deployment and installed stages.
