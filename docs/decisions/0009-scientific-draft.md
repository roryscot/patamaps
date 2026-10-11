# R10 scientific profile implementation scope

The implemented native profile imports the pinned SSSOM 1.0 entity TSV contract, retains
raw UTF-8 source bytes and decoded cells, validates the unchanged MappingSet model,
preserves prefixes and scalar extensions, and keeps repeated assertions distinct.
Anonymous identities bind effective content, source scope, set context and duplicate
occurrence. Explicit source record IDs remain stable across content changes.
SSSOM confidence remains metadata and imported loss stays unknown; an exploratory
consumer must author its own tolerance, risk budget and irreversible declarations.

The first native input bound is 16 MiB, matching the compiler's strict JSON/capture
profile; the pinned TypeScript source reader allowed 64 MiB. This stricter resource
limit must be recorded as an intentional profile difference, not hidden truncation.
Export may change quoting and line endings while retaining effective fields and
metadata. Condensation must explicitly report changed origins. Literal, negated,
unmapped and undefined extension records refuse before graph construction.

The YAML 1.2 parser's event API refuses anchors, aliases, tags, directives,
duplicate keys and excessive depth before building metadata. The pinned
JSON Schema validator runs with remote/file resolution disabled and selects the
original MappingSet definition. These dependencies implement source syntax and
schema validation; they introduce no alternative admission engine.
[yaml-rust2 event API](https://docs.rs/yaml-rust2/0.13.0/yaml_rust2/parser/enum.Event.html),
[jsonschema resolving options](https://docs.rs/jsonschema/latest/jsonschema/).

Reuse the licensed original model, slot index, producer subset/selection manifest,
SKOS relation/law declarations and offline RO-Crate context bytes. Acceptance
requires native round trips and positive lookup behavior, strict policy/budget
negative controls, unknown loss/evidence preservation, independent pinned SSSOM
checks, full bounded crate inventory recomputation and tamper refusals. Syntax and
format conformance do not establish scientific truth. Preserve the known strict
parser defect of the independent checker rather than patching it for a pass.

The checked RO-Crate profile is closed to one exact captured SSSOM source and its
native artifacts. It replays admission, reimports every original assertion and
regenerates the complete file inventory and metadata. A self-consistent forged
manifest is insufficient. D009 requires every declared capture receipt to have
its exact bytes; the reference also supported partial raw-source inventories.
External producer sources remain explicitly labeled references and are never
fetched. D007 records the 16 MiB source bound and aggregate bounded topology work.

The official RO-Crate 1.2 context is pinned at
`sha256:27a661f6082735563d9f83145a63876cbe0c0b78624332d3ca05053253eb0d41`.
Its [CC0 license](https://github.com/ResearchObject/ro-crate#license), the SSSOM
model's BSD license and the MGI subset's CC-BY-4.0 attribution are recorded in
NOTICE. Format verification uses SSSOM-py 0.4.17, sssom-schema 1.0.0 and RDFLib
7.1.4 in a separate pinned environment with network access forbidden during
checks. All three SSSOM validation categories pass for source and both exports;
the known `strict=True` upstream metadata-parser defect remains a recorded
failure. Offline RDF expansion checks all 16 payload files and 121 triples,
without claiming universal RO-Crate validation or scientific truth.
