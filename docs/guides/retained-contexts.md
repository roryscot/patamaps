# Retained project contexts

The opt-in context commands capture explicitly selected binary files, executable permission bits, directories and closed relative symlinks. They complement the existing UTF-8 project capture profile; they do not change that profile's dependency-tree or symlink refusals.

An owner supplies strict JSON such as:

```json
{
  "profile": "patamaps-project-context-selection-1",
  "id": "urn:example:dependencies",
  "nonsecretInputs": true,
  "paths": ["node_modules/tool/bin/tool", "assets/icon.bin", "empty", "tool-link"],
  "symlinks": "internal-closed"
}
```

Paths are explicit, owner-relative and include every link target required by the closed graph. Ancestor directories are included automatically; directories do not imply recursive discovery. The default symlink policy is `refuse`. No glob expansion, package installation, environment lookup, tool execution or secret-reference resolution occurs.

```sh
patamaps project-context-capture selection.json --root owner --destination fresh-snapshot
patamaps project-context-verify fresh-snapshot
patamaps project-context-stage fresh-snapshot --destination fresh-candidate
```

Snapshots contain canonical `selection.json`, addressed `manifest.json`, and a `data/` tree of binary blobs. Link targets and original permission bits are metadata. Snapshot blobs are private regular files; staging reconstructs declared interior directories, file modes and relative links. The destination root remains private. Existing destinations are refused. Failed partial snapshots/candidates remain for inspection.

Verification and staging require the snapshot, not its original source or source tools. Staging verifies all blob hashes and the closed link graph before creating the destination, then checks staged content, modes, links and exact tree membership. Descriptor-relative operations refuse symlink ancestors and nonregular files. Link resolution expands links before processing subsequent parent components.

Bounds: at most 262,144 selected paths plus ancestors; existing safe relative paths of at most 1,024 bytes and 128 segments; selection JSON below 16 MiB; context records below 64 MiB with the existing depth/value limits; each file at most 1 GiB and aggregate file bytes at most 16 GiB. Privileged mode bits, escaping/dangling/cyclic links, source-overlapping destinations and reserved paths such as `.git`, `.env*`, `.npmrc`, `target`, `.next` and Next encryption manifests refuse. `node_modules` is permitted only in this separate explicit context profile.

The owner must review the entire explicit selection as nonsecret. Filename refusals are not a secret scanner. The digest proves recorded content integrity; it does not establish owner authorization, dependency completeness, package provenance, platform compatibility, runtime behavior, ownership, ACLs, extended attributes, hardlink identity or crash durability.

The original context primitive checkpoint preceded native build integration. A small binary/link CLI fixture and existing staging regressions pass. The real 1.60 GB selected context also passed offline verification, reconstruction, independent membership/hash/mode/link checks, and Next.js build plus TypeScript checking with the earlier configured candidate path unavailable. All reconstructed inputs remained unchanged; new candidate writes were confined to the declared Next output and TypeScript cache paths. See the [primitive receipt](../acceptance/project-adoption/g4-retained-context-2026-10-16/receipt.json) and [real-project receipt](../acceptance/project-adoption/g4-retained-context-2026-10-16/real-next-reconstruction.json). This used a retained qualification driver, not native project-build context integration. Runtime, generated-contract replacement and installed consumer qualification remain unestablished. G4–G6 remain incomplete.


## Bind a context to a native build

The existing plan and Rust API remain available. Opt in with a separate strict JSON binding, profile `patamaps-project-build-context-1`, containing:

- `snapshot`: absolute path to the retained snapshot.
- `digest`: exact context digest returned by capture.
- `overlays`: a map from each changed existing context file to its old digest. Only captured project inputs or generated workspace outputs supply replacement bytes. Identical existing files need no overlay entry; unused, wrong, directory and symlink overlays refuse. Existing file modes remain those in the context; new selected text files are private and non-executable.
- `writablePaths`: at most 64 literal owner-relative new output/cache roots. They cannot cover existing context entries or selected/generated inputs. Unknown writes outside these roots refuse selection. Output selection remains the separate existing build-plan contract.

```sh
patamaps project-build-input-key plan.json --source owner --context binding.json
patamaps project-build plan.json --source owner --state retained-state --context binding.json
patamaps project-build-verify retained-state
python3 scripts/project_watch.py plan.json --source owner --state retained-state   --compiler /absolute/path/patamaps --context binding.json --runner /absolute/policy-runner --
```

Rust callers can use `build_project_with_context` and `project_build_input_key_with_context`, passing `Some(&binding)`; the legacy functions delegate without a context.

A binding declares a sealed content reference. Input-key observation binds that reference and explicitly reports context byte verification as not performed. It does not poll or rehash snapshot blobs. After dependency changes, capture a new context and update the binding digest. Each new materialization verifies the snapshot bytes. A no-op verifies the retained selection and reports execution verification not repeated and zero cache hits; it is not a new verification of the original snapshot store.

The native builder creates a fresh context candidate, applies only the declared byte replacements, and binds the context into its input key and receipt. It retains the selection definition and manifest separately from blob storage. Final selection and offline replay verify the materialized immutable entries, overlay bytes, modes, links and exact membership outside declared write roots, alongside existing source, graph, tool, command and selected-artifact bindings. Replay needs neither the original source path nor the original snapshot path. Failures before publication retain their outputs and preserve the earlier selection. Post-publication durability failures remain explicitly unconfirmed.

Composition retains the context's path/depth, node and aggregate-byte bounds. This does not establish complete executable dependency closure, arbitrary command effects, runtime behavior, current authorization or deployment activation.

Native unit and CLI controls cover binary dependency consumption, preimage-bound overlays, no-op behavior, source/snapshot-free replay, corruption, dependency mutation, unexpected writes and command failure. Real Next reconstruction/build evidence above used a qualification driver. The actual 1.60 GB project still needs qualification through this new native binding, generated-contract integration, runtime and installed-consumer checks.

The [native binding receipt](../acceptance/project-adoption/g4-native-context-binding-2026-10-16/receipt.json) records 82 package tests, 10 CLI controls and the 13-control context-backed watch suite through Intel's actual per-update supervisor. These are controlled workflow checks, not qualification of the full existing application through this API.
