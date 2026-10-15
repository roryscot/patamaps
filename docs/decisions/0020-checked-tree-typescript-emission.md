# Checked tree TypeScript emission

C07 source review found that the reference typed example executes a standalone
tree module and hydration helper. The native Rust tree workflow is verified;
the new emitter completes the target-language artifact surface using the same
checked tree rather than adding another policy engine.

The Rust API emits static Unicode JSON, parameter metadata and a standalone
TypeScript helper. The CLI exposes JSON (the existing default) and TypeScript
output. Helper hydration preserves template keys and cloned occupants, substitutes
whole segments once, validates supplied optional/catch-all values and applies
the native Unicode/UTF-8 and aggregate bounds. Returned paths have string types
rather than the template's literal types. Prototype-like data keys and export
bindings cannot change the helper's meaning.

Acceptance requires actual tsc/Node execution, API/CLI output agreement,
literal token and optional-value controls, input ownership, Unicode/resource
refusals, and refusal of a false literal-path type. Native compiler, installed
and Linux milestones must be refreshed for the changed source. Original
reference bytes, tests and earlier receipts remain intact.

The helper uses the native hydration whitespace set (ECMAScript whitespace,
including U+FEFF). U+0085 is retained literally by both APIs; it is not included
in that set. Installed acceptance compares this result directly with native
hydration and executes the alternate delimiter helper as well. This preserves
the existing native decision instead of introducing a target-language-only
restriction. JSON ingress still rejects lone surrogates.

The generated helper checks each substituted path before appending beyond its
16 MiB byte budget, the aggregate path bytes, and the complete serialized tree
(including JSON escaping). Installed controls cover a repeated token that would
expand one path beyond the limit and NUL data whose escaped JSON exceeds it.
The helper returns the tree only; the Rust API additionally returns its native
template/parameter envelope, whose full ingress bound remains in force.

Verified on the Intel candidate: [focused actual execution](../acceptance/capabilities/tree-focused-2026-10-15T02-00-12.275638Z/receipt.json),
[installed SDK/API/CLI and standalone runtime acceptance](../acceptance/capabilities/installed-resume-2026-10-15T02-11-38.187814Z/receipt.json),
and the [compiler milestone](../acceptance/capabilities/compiler-2026-10-15T02-01-50.627814Z/receipt.json).
Current Linux acceptance remains required after publication. Earlier failed
fixture, delimiter-typing and supervisor attempts remain preserved.

A requested governed TypeScript emission for a specification with a path tree
also includes `path-tree-N.ts`, using the binding emission's index. Its exact
checked helper bytes, media type, digest and length enter the existing complete
artifact manifest and proposal. Missing or changed helper bytes refuse through
normal prepared-artifact verification. This reuses the same emitter and grants
no authorization. All ten stages of the
[current compiler milestone](../acceptance/capabilities/compiler-2026-10-15T03-25-51.400752Z/receipt.json)
pass, including exact governed helper-byte and tamper controls. Installed and
Linux acceptance remain required for the changed artifact producer.
