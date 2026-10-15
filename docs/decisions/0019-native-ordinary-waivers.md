# Native ordinary compiler waivers

The pinned MetaMap viability compiler allows ten ordinary policy findings to be
waived by exact code and subject at an explicit evaluation time. The native
compiler implemented six, so a valid temporary unknown-lossiness waiver was
rejected as invalid. The same gap affected undeclared impact direction and
unverified determinism/reversibility.

The native allowlist now includes those four findings. Waivers retain their
reason, attributor, exact subject/code scope and exclusive expiry boundary.
The finding remains a warning with its waiver identity; original graph bytes
and policy bindings remain intact. Missing declarations, unsupported operations,
proof integrity, graph bindings and authentication remain protected. A compiler
waiver grants no consumer opt-out: strict projection still rejects unknown loss,
and capture/replay reproduces both that refusal and an expired waiver.

Focused controls first demonstrated native rejection before the repair.
Verification receipts record the unchanged pinned reference bytes, the native
scope/expiry controls, strict consumer refusal and subsequent milestone results.
This change does not authorize registry publication, production trust or activation.
