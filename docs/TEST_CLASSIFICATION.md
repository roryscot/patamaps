# Test classification and compatibility policy

The owner’s 2026-10-14 goal makes substantive Rust-native capabilities the
completion criterion. [BUILD_PLAN.md](../BUILD_PLAN.md) owns the current matrix
and delivery gates. This document classifies the use of evidence; it does not
change original inputs, tests, expected values or historical results.

| Class | Required outcome | Existing evidence |
| --- | --- | --- |
| Native guarantee | Independent expected refusal/success for semantic correctness, private checked states, resource limits, ownership, evidence, proof closure, budgets, replay, signatures and host publication. | Native non-legacy crate tests; compile-fail documentation; governance crypto controls; Linux permission/crash/lifecycle tests. |
| Shared semantic comparison | Actual admission, bindings, provenance, ordered premises, loss, uncertainty dimensions, unique dependency/cost closure, source limits and unknown outcomes agree with the pinned reference for the declared shared profile. | `scripts/reference/compare.py`, `semantic.py`, `topology.py`, scientific comparison; original native-consumer expectations. Complete original and candidate outputs are retained. |
| Required wire interoperability | Required format/version, canonical bytes, hashes, signature algorithms/domains and consumed scientific formats are exact. | Canonical/digest/JSON vectors, original schemas/packs, independent signature vectors, SSSOM/RDF/RO-Crate controls. New successor domains remain explicitly distinct. |
| Workflow and installed consumer | A complete sequence produces usable checked artifacts, executes independent native consumers, preserves outputs on refusal/drift, and rechecks current state at authority boundaries. | Portable lifecycle, binding/migration/distribution drivers, workspace and scientific consumer fixtures. Older results require same-candidate refresh. |
| Platform guarantee | Actual required operating system/filesystem/UID/locking/crash behavior passes for the current candidate and packaged binaries. | Historical ARM64/ext4 host results; current ARM64/x86_64 Linux acceptance is open. Compilation or cross-compilation cannot substitute for execution. |
| Integration-specific compatibility | A named integration requires a particular JS behavior or public API. Record the integration and its observable requirement before making it a capability gate. | Existing TypeScript SDK/runtime/declaration tests and unchanged original callbacks. An existing test alone does not demonstrate an integration requirement. |
| Historical JS observable | Exception wording, prototypes, receiver quirks, object identity/array aliasing and incidental mutation remain useful historical observations; they do not gate the native goal by default. | Existing `fixtures/parity/*-controls.json`, SDK facade comparisons and the original 1,293-obligation ledger. No files or expectations are removed. |

Mixed corpora must be interpreted case by case. For example, the uncertainty/risk
corpora contain required qualitative states and safe-integer accounting alongside
SDK reference-retention controls. The former inform C05/C06; the latter are
integration-specific or historical. Labeling a corpus “historical” must never
erase its semantic negative cases. Canonical bytes, prototype-pollution refusal,
safe source paths and security-sensitive metadata handling remain guarantees
even when the surrounding JavaScript API is optional.

The preserved `fixtures/conformance.json` records all 53 original suites and
their earlier native destinations. It is a traceability index, not proof that
every substantive assertion in a suite is currently verified. The old parity
ledger remains immutable evidence for its recorded checkpoints. A new matrix
checkpoint records current capability results separately and does not relabel
old failures as passes.

## Compatibility decisions

1. Rust-native typed APIs and private checked states are primary. Thin language
   wrappers call Rust decisions and treat deserialized records as untrusted.
2. Original MetaMap wire records remain original records, with original version,
   canonical/hash convention and executor identity. Successor draft conversions
   report changed envelopes/bindings and perform a fresh evaluation.
3. Required interoperability is tested against original bytes or independent
   standards vectors. Do not normalize away a consumed signed/hash field to
   obtain agreement. New Patamaps approval domains do not accept old approvals.
4. Existing D001–D009 profile/difference records describe prior decisions and
   observed outcomes. They are retained; their existence does not establish
   owner acceptance of a newly required format or semantic difference. Review
   each against a demonstrated integration and current capability guarantee.
5. The owner explicitly excluded literal JS exceptions/identity/prototypes and
   incidental mutation as default requirements. No agent disposition of a
   substantive capability follows from that exclusion.
6. MetaMap is a reference, not an infallible oracle. A disagreement retains full
   reports, identifies the controlling semantic requirement and independent
   counterexample, and stays open if correctness or required interoperability
   cannot be established.

Every milestone receipt identifies the commands actually executed, source and
executor identities, fresh versus historical results, failed/skipped checks and
platform limits. “Implemented,” “verified,” “accepted” and “activated” remain
distinct states. Production trust/bootstrap, activation and registry publication
require separate authorization.
