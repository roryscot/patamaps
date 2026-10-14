# Native constraint evaluators

This closes the Rust-library customization gap identified in C03 of the
[capability plan](../../BUILD_PLAN.md). MetaMap’s pinned `constraints.ts` permits
registered evaluators to inspect the graph, active mapping set and evidence.
Patamaps reuses native admission and adds an explicit host-supplied registry;
it does not install a second policy engine or deserialize executable code.

The observable contract is:

- Register a unique constraint kind with an evaluator identity and canonical
  SHA-256 implementation binding. Built-in evaluators cannot be replaced.
- Evaluators borrow immutable checked graph, policy, active mappings and explicit
  context/time. They return typed findings or `CheckError`; they cannot return an
  admitted state, remove another evaluator’s findings or alter graph authority.
- Custom findings use the registered kind as their code namespace, have known
  origins and no pre-applied waiver. Bounded findings/text, evaluator failure,
  unwind panic and exhausted/cancelled controls refuse admission. Custom findings
  cannot impersonate a built-in waivable code.
- Use `WorkControl` before and after each callback and expose cooperative polling
  during the callback. In-process Rust callbacks are trusted host code, not a
  sandbox: a callback that never returns cannot be forcibly preempted by this
  API. An elapsed/cancelled callback that returns cannot mint admission.
- The generation’s canonical address binds only the custom evaluators actually
  used, sorted by kind in UTF-16 order. Unused registrations do not alter semantic output.
  The binding is caller attribution of an implementation, not authentication or
  proof that supplied code matches the digest. The host owns that association.
- Default capture/replay, CLI, artifact preparation and protected publication
  install no caller callbacks. They refuse the unknown kind. A serialized custom
  generation does not restore checked state or become a replayable/governed
  candidate. This preserves the reference boundary: both `replay.ts` and
  `semantic-replay.ts` explicitly reject a supplied `constraintRegistry`, and
  `replay.test.ts` verifies capture/replay of an unknown-kind refusal. Portable
  custom execution is not a missing reference capability.

Reference: pinned [legacy capture](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/src/replay.ts#L443),
[semantic capture](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/src/semantic-replay.ts#L298)
and [negative replay control](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/src/__tests__/replay.test.ts#L286).

Acceptance includes a real native custom-policy success/refusal, immutable input
checks, missing evaluator, duplicate/built-in registration, invalid identity or
digest, spoofed/over-limit findings, failure/panic, cancellation/elapsed control,
changed used binding versus unused binding, stale graph and structural refusals,
and refusal by default capture. Existing built-in/semantic workflows and their
canonical results must remain unchanged when no custom evaluator is used.
