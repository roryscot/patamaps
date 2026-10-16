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

This checkpoint does not integrate contexts into `project-build`. A small binary/link CLI fixture and existing staging regressions pass. The real 1.60 GB selected context also passed offline verification, reconstruction, independent membership/hash/mode/link checks, and Next.js build plus TypeScript checking with the earlier configured candidate path unavailable. All reconstructed inputs remained unchanged; new candidate writes were confined to the declared Next output and TypeScript cache paths. See the [primitive receipt](../acceptance/project-adoption/g4-retained-context-2026-10-16/receipt.json) and [real-project receipt](../acceptance/project-adoption/g4-retained-context-2026-10-16/real-next-reconstruction.json). This used a retained qualification driver, not native project-build context integration. Runtime, generated-contract replacement and installed consumer qualification remain unestablished. G4–G6 remain incomplete.
