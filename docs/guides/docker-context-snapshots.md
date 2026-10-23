# Docker contexts with opaque artifacts

This checkout feature adds `contextSnapshot` to the existing native `dockerfile` provider. It is newer than published `patamaps-cli 0.1.0-alpha.1`; an older CLI must refuse the unknown option. Existing complete text-only requests keep their prior shape and observations.

Use the existing project-context commands to capture and stage the whole reviewed nonsecret image context, including compiled executables:

    patamaps project-context-capture selection.json --root image-owner --destination sealed-image
    patamaps project-context-verify sealed-image
    patamaps project-context-stage sealed-image --destination staged-image

The selection uses profile `patamaps-project-context-selection-1`, `nonsecretInputs: true`, an explicit owner-relative `paths` list and `symlinks: refuse`. Use the capture result's exact digest. Review the selected bytes before capture: the nonsecret declaration does not redact arbitrary secrets. Existing blocked paths, including `.env*`, `.npmrc`, private-key names and build/cache roots, remain refused.

Configure the existing native adapter request (or workspace process source) with:

```json
{
  "provider": "dockerfile",
  "nonsecretInputs": true,
  "dockerfile": "Dockerfile",
  "context": ".",
  "contextFiles": ["Dockerfile", "bundle/launch.sh", "bundle/miniserve"],
  "completeContextSnapshot": true,
  "contextSnapshot": {
    "snapshot": "/absolute/path/to/sealed-image",
    "digest": "sha256:<exact capture digest>"
  },
  "target": "runtime",
  "platform": "linux/amd64",
  "frontend": "docker/dockerfile:1.10.0",
  "buildArgs": {}
}
```

This is a configuration shape; adapt the complete file inventory and paths to the reviewed owner context. The normal canonical adapter request envelope, invocation/request digests and text `inputs` are still required. Supply exact UTF-8 text for the Dockerfile and any default or Dockerfile-specific ignore file present in the snapshot. Other members can remain opaque; do not encode the executable as a JSON string or substitute a marker for its bytes. Every supplied context text must match its snapshot receipt, and `contextFiles` must equal all regular files in that snapshot. Nested context paths stay relative to the same owner root.

The provider verifies snapshot inventory, raw file digests and captured mode bindings without consulting the original owner. It refuses symlinks, unsupported file types, changed or extra members, mismatched text/digests and malformed references. Before payload traversal it enforces 1,024 regular files, 8,192 total entries and 512 MiB aggregate file bytes. Snapshot-backed observation output, including metadata, is bounded to 8 MiB. Directory-only COPY and other unsupported Docker grammar/effects retain explicit limitations.

Internal snapshot blob permissions are storage details. The captured manifest binds original file/directory modes; staging verifies payloads and restores those modes. Use the staged closed tree as the actual BuildKit context, and check its reported digest equals the declared snapshot digest. This is a cooperative verified capture/staging contract, not protection against arbitrary hostile writers after verification.

COPY observations include exact member digests, byte lengths, snapshot digest and whether a member was supplied as text. Metadata separates `snapshotBytesVerified` and `capturedModesBound`. Existing statements that compilation, Docker instruction execution, image contents, base-image identities and runtime listeners are unestablished remain false. These are source observations; actual image/runtime verification is a separate requirement.

The focused qualification entry is:

    gh workflow run native-capabilities.yml --ref feat/retained-owner-preparation -f qualification=binary-docker-context

It builds the current CLI, checks workspace tests/strict Clippy, captures the exact previously verified public Miniserve executable, exercises discovery refusals and owner-unavailable replay, and builds/runs the image from that staged context. Qualification is pending until its linked receipt is recorded; syntax or a prepared workflow alone is not acceptance. No registry or production activation is performed.

Earlier external-Rust installed/image receipts use frozen older compiler engines. Their recorded success does not apply automatically to this new engine; current invocations conservatively refuse an old producer/source mismatch. Repeat those exact historical jobs with `gh run rerun 39897900519` or `gh run rerun 39899991879` while their frozen artifact remains available, rather than mixing old selected state with a new compiler. Rebuild and reselect under the new engine for a current deployment.
