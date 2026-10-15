# Patamaps executable specification

Draft 1, 2026-10-11. This file owns the Patamaps portable protocol and semantic boundaries. [BUILD_PLAN.md](../BUILD_PLAN.md) owns delivery gates; [fixtures/conformance.json](../fixtures/conformance.json) owns reference provenance and case destinations. The README owns product scope. [Current naming and verification](acceptance/2026-10-11-patamaps.md) identifies the renamed candidate. Prior acceptance records retain their original source and protocol identities.

The project is a correspondence compiler: independently owned descriptions of concepts and implementations produce checked static native structures. Semantic identity survives an implementation move. A locator describes physical placement; it does not convey ownership, policy support, signing authority, or permission to execute code.

The implemented compiler profiles are `patamaps-routing-draft-1` and `patamaps-semantic-draft-1`. Pure `patamaps-governance-draft-1`, inspection, `patamaps-workspace-draft-1` orchestration and the bounded scientific profile are implemented and verified on macOS and Linux. Two separate native consumers exercise routing and scientific artifacts. `patamaps-linux-root-draft-1` passes actual independent-UID, concurrency, five-phase SIGKILL and governed lifecycle checks on the recorded ARM64/ext4 guest. Unknown operations reject; absence of an evaluator is never an affirmative result.

## Wire and addressing

Portable input envelopes require `schemaVersion: "0.1.0"` and an explicit `documentType`. The implemented types include `graph`, `relation-pack`, `policy`, `projection-spec`, `derivation`, `composition-request`, `path-tree`, and `capture`. Unknown envelope fields reject. Entity attributes, provenance-bearing metadata and explicitly declared extensions are JSON data, with no implied capabilities. Inputs are decoded strictly before conversion to typed Rust values; a plain `serde_json` deserializer is not an ingress substitute.

Optional typed fields may be absent; explicit null rejects unless the declared value itself is arbitrary JSON or explicitly nullable. A projection's semantic `budget` must be present: a named budget or explicit null. Missing is not an opt-out. The distinction survives serialization. JSON object keys are unique after escape decoding, Unicode must consist of valid scalar values, and trailing text rejects. Numbers use the RFC 8785 binary64 domain, including numeric integer tokens; negative zero becomes zero. Arbitrary scientific numeric text belongs in string metadata when its original spelling matters. No Unicode normalization occurs.

New content addresses are `sha256:` followed by 64 lowercase hexadecimal digits over RFC 8785 canonical UTF-8 bytes, without a trailing newline. Property order uses UTF-16 code units and number rendering uses ECMAScript behavior. Array order remains significant for addressing. Query and generated-entry ordering is deterministic by stable ID. Equal unordered declarations have the same semantic result, while differently ordered source documents can have distinct exact-input addresses. Input order in composition lineage remains significant.

Addressed output records omit only their own `id` and `digest` when computing their address; an ID is `urn:patamaps:<record-type>:<digest-hex>`. Generation addressing includes explicit time/context and exact graph, pack and policy digests. Projection addressing includes the generation and specification digests. A serialized output is evidence, not a restored checked capability. Linking against a saved generation reruns admission and compares its complete canonical record.

Rust checked types have private fields and no public deserializer. Safe public callers can construct untrusted wire data, then obtain checked state only through its validator. Generated native code carries no checked compiler capability or authorization. The SDK and CLI use the same core functions.

## Graph and scoped ownership

Entities, mappings and authorities share a graph-wide stable identifier namespace. Identifiers have an ASCII URI-style scheme, a colon, and a nonempty non-whitespace remainder. Entity kinds are open nonempty strings. Relations use lowercase namespace/name tokens and are owned by exactly one supplied pack. Network schema or pack resolution is forbidden. Embedded core definitions and explicitly supplied pack values are checked locally.

Mappings retain separate nonempty, unique source and target groups. One-to-one, one-to-many, many-to-one and many-to-many impose the declared group sizes. Every endpoint must exist and satisfy the pack's allowed kinds and cardinalities. Forbidden relation cycles reject using a bipartite entity/mapping traversal, preserving n-ary assertions without a Cartesian edge expansion. A descriptive `transitive`, `inverse`, or `symmetric` flag is not a proof permitting executable inferred bindings.

Pack IDs, versions and optional exact digests must match supplied values. Conflicting entity/mapping/authority/pack declarations reject composition. Identical declarations may deduplicate. Cross-shard references are checked after composition; a single shard is not necessarily a standalone valid graph. Composition is not inference and never silently changes an authored ID.

Authorities bind a concept, source entity, fact scope and declared/observed/generated/inferred provenance. Canonical roots cannot overlap fact scopes for one concept. A delegated authority must identify its parent, preserve the concept and narrow the parent's facts. A wildcard scope cannot be invented below a bounded parent. Delegation cycles, candidate parents and independent overlapping branches reject. Resolution returns root, effective leaf and delegation chain. Candidate-only ownership remains explicitly ambiguous; inspection can show it, but a requires-authority constraint cannot treat it as resolved. Graph ownership grants no host or signing permission.

## Admission and projection

Evaluation receives an explicit RFC 3339 logical time and a context object containing primitives or primitive arrays. The core reads neither the clock nor the filesystem. Policies name an exact graph revision or digest. Each mapping needs exactly one policy declaration. Direct IDs and nonempty selectors can select mappings; no-match selectors, empty selectors and overlapping coverage reject. All comparisons that require a context key must receive it, including branches of an any/not expression. An `exists` test has its declared absence semantics.

Determinism, reversibility, coverage and loss are authored facts subject to conservative checks, not facts inferred merely from Rust's type system. Reversible output requires a lossless mapping and a compatible declared transform. Ordinary compilation rejects unknown loss unless an explicit scoped waiver covers that finding. Projection loss requirements remain separate. Applicable mappings form the active set; inactive mappings retain their exact declared reason. Rejection does not produce a checked generation.

Initial constraints are requires-mapping, forbids-mapping, unique-target, requires-authority and requires-evidence in the core namespace. Unsupported kinds or parameters reject. Evidence is supports, contradicts or inconclusive; high scalar confidence cannot make inconclusive evidence support. Ordinary contradiction of an active subject rejects. Evidence bound to a typed assessment instead contributes to that dimension and the consumer's explicit uncertainty requirements. Ordinary waivers list exact codes and subjects, require a reason/attributor and expire at the explicit evaluation time. Only the ten policy findings listed in `admission.rs` are waivable, matching the pinned reference: required evidence/mapping/authority, contradicting evidence, forbidden mapping, non-unique target, undeclared lossiness/impact direction and unverified determinism/reversibility. A waiver retains the warning, original mapping and exact policy binding; projection requirements remain independently enforced. Malformed inputs, unsupported operations, stale bindings, semantic integrity and later authentication failures cannot be waived.

Projection uses the admitted active mapping set and an explicit entity selector. Each named slot declares relation, incoming/outgoing role, target-kind requirements, loss permission and exactly-one/zero-or-one/one-or-more/many cardinality. Missing, ambiguous, wrong-kind or unwanted-loss links reject before any output write. Results retain the selected subject, exact target metadata, mapping IDs and full graph/generation/specification bindings.

The draft native dispatch demo intentionally has the signature `fn(&str) -> String` in Rust and `(input: string) => string` in TypeScript. It statically references ordinary consumer symbols; the compiler does not open, load or execute locator-named code. Rust semantic IDs are opaque validated strings, so adding a preceding entry cannot retarget a public ordinal variant. Rust locators are `rust:crate::module::symbol`, with ASCII identifier segments and [reserved keywords](https://doc.rust-lang.org/reference/keywords.html) refused. TypeScript locators are `typescript:./relative-module.ts#symbol`; `.js` imports target the consumer's normal NodeNext resolution. Path traversal, invalid identifiers, ambiguous target-language locators and reserved generated names reject. Other signatures need an explicit later emitter profile. JSON strings and metadata are escaped; TypeScript data uses `JSON.parse` so `__proto__` remains an ordinary property.

## Declared laws, proofs, uncertainty and risk

A pack with an explicit `laws` array declares executable semantics; descriptive flags alone permit no inference. Exact direct imports bind pack ID, version and canonical digest and form an acyclic dependency graph. Reverse accepts one binary premise; chain accepts two ordered binary premises with the same middle identity. Context and endpoint-kind conditions must match. Unknown laws, incompatible roles and unsupported n-ary inference remain distinct refusals. Loss propagates conservatively; no derived assertion receives premise ownership or signing authority.

Executable packs require a policy `semantics` record. Its interpretation, proof inventory, limits, assessments, uncertainty requirements and risk budgets are required fields. Every inferred mapping carries an exact `metamap:derivation` back-reference for interoperability. Proof checking regenerates the result and binds complete premises, child proofs, exact packs/imports, context, evidence and assessment values. Fully readdressing a forged proof cannot bypass regeneration. Active results require active premises; partial, nondeterministic or irreversible premises cannot produce stronger declarations. Disjoint active relations refuse outside ordinary waiver handling.

Identity, context, provenance, completeness, causal-relevance and conflicting-authority are separate dimensions. Each is supported, contradicted, unknown or explicitly reasoned not-applicable. Assessments bind subjects/revisions, evidence scopes, assessor and optional measurement model. Contradiction dominates unknown; incompatible models become unknown; direct support cannot erase an unknown premise. Scalar confidence stays source metadata and never establishes a probability or typed support. Consumer requirements determine allowed states and evidence obligations, including not-applicable contributors.

Semantic projection binds a consumer and explicit budget choice. A matching consumer budget cannot be disabled with null or replaced with another consumer's budget. Used mappings and all proof premises form one unique closure; shared proofs and mappings cost once. Every member needs exactly one classification, including zero-cost entries. Totals use checked safe-integer arithmetic. Missing classification, overflow and total/lossy/inferred limit breaches refuse. With no declared budget, cost is not evaluated and remains null.

Path trees require authored paths on selected entities and the exact projection specification. Structural child keys and occupants remain intact during hydration; only path strings change. Missing required parameters, collisions, reserved keys and unsafe values refuse. Substituted values are literal data and are not recursively interpreted as parameters. Initial limits are depth 48, 200,000 nodes and a 16 MiB output. The Rust API `emit_typescript_path_tree` and CLI `path-tree --format typescript --export NAME` emit a standalone TypeScript tree/helper module from `CheckedPathTree`. Hydrated paths have string types, and occupants are cloned. Whole-segment substitution, optional/catch-all validation, native whitespace/Unicode and input/per-path/aggregate/serialized-tree bounds remain explicit. The helper returns tree data; the Rust hydration result additionally includes its bounded native template/parameter envelope. See [decision 0020](decisions/0020-checked-tree-typescript-emission.md).

## Capture, replay and comparison

A capture includes typed graph/packs/policy, explicit context/time, an optional projection specification, optional source receipts and the complete successful or rejected evaluation. It binds the exact pure-kernel source, workspace/crate dependency declarations, lockfile and toolchain specification. This is an executor source identity, not a claim of reproducible binary bytes or an external authorization. Replays require the same executor/profile, verify the capture and any supplied raw UTF-8 source bytes, then recompute the full result. Receipt-only sources are explicitly unavailable; replay never follows a locator or executes named code. Capture creation must fit its own strict-ingress envelope. Raw JSON syntax/decoding failures are refused before this typed capture stage.

Stable-ID comparison separately reports authored record changes, policy/context/pack differences, source receipt/byte differences, issue subjects, and declared graph impact paths. Source extraction is not rerun. Paths follow declared impact direction and remain inspection of graph dependencies, with no claim of unique causal responsibility. Unavailable projection/risk deltas stay null. Impact inspection is limited to 256 origins, depth 64, 10,000 visits and 2,000,000 operations; missing origins, undeclared directions and exhausted bounds remain incomplete.

The isolated reference harness retains all outputs and compares explicitly shared routing and semantic profiles. D001 accounts for changed draft envelopes/content addresses; proof subjects are compared by stable result identity. D004 normalizes only the empty-selector policy-format diagnostic; other semantic diagnostic codes and subject origins must agree exactly. Risk delta is available only when both projections have evaluated budgets; unavailable is null. The normative numeric control independently compares canonical bytes with ECMAScript. Neither these checks nor source identity establishes truth of asserted facts or a Rust performance benefit.

## Lifecycle acceptance requirements

The pure `patamaps-governance-draft-1` implementation is specified in [the governance decision](decisions/0005-governance-draft.md), with [actual verification](acceptance/2026-10-10-governance.md). It binds up to 16 consistent admitted captures and 32 requested native emissions to one complete recomputed byte inventory and computed action/fact delta. Projection specifications explicitly name the consumer through `consumer` or consistent semantic requirements. Declared source receipts must include verified raw bytes. Candidate identities never become output paths.

Approvals sign the complete JCS payload under `urn:patamaps:approval:draft:1`; grant IDs and canonical requirement strings sort by UTF-16. Exact canonical base64 SPKI keys and 64-byte signatures undergo strict Ed25519 verification. Current separately supplied trust/base/time govern revocation, scopes and complete approval intervals. Issue time is inclusive, expiry exclusive, in exact UTC millisecond form. Each grant covers an action and subject/fact jointly; only `*` is wildcard. Protected changes require an externally configured owner plus grants. Attribution and graph ownership confer none. Authentication, stale-base and byte failures cannot be waived.

`approval-payload` writes exact signing bytes without a newline. `attach-signature` accepts a JSON string containing the externally produced base64 signature and creates unapproved data. `verify-approval` recomputes complete prepared files and reports `authorized-under-supplied-context`. Production APIs accept no private signing key and perform no activation. Caller-controlled trust can appoint its own owner; R7 must establish actual host provenance and repeat checks at publication.

Capture, inference, uncertainty, risk, pure approval verification, bounded repair and workspace orchestration have focused draft verification. Scientific integration, shared-profile comparisons and separate consumer migrations are verified. Source/native packages and SDKs pass installation on ARM64 macOS and Linux. Browser observations are bounded to the identified inspector revision. The root-owned Linux/ext4 profile passes permissions, process-crash and complete governed lifecycle controls. These requirements apply throughout the build:

| Boundary                    | Required positive control                                                                                                             | Required refusal or unknown state                                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Capture/replay              | Success and rejection reproduce from exact captured inputs without discovery                                                          | Tampered/missing dependencies or another executor cannot become a verified replay; missing sources remain unavailable                                         |
| Explicit inference          | Bounded binary reverse/chain law gives inspectable premises, exact pack/context and conservative loss                                 | Role reversal, changed premise, forbidden chain, stale context, unsupported n-ary law and irreversible misuse reject; `closeMatch` is not transitive identity |
| Uncertainty                 | Each of identity, context, provenance, completeness, causal-relevance and conflicting-authority remains independently visible         | Unknown/contradicted premises persist; scalar confidence and direct support cannot erase unknown dependency state                                             |
| Risk                        | Complete unique used mapping/proof closure costs shared premises once                                                                 | Missing classification, stale evidence, integer overflow, budget opt-out and above-budget output reject; costs are ordinal, not probabilities                 |
| Governance                  | External owner-scoped, domain-separated Ed25519 approval binds exact artifacts, inputs, consumer, environment, base and current trust | Forged, weak-key, expired, revoked, stale-base, wrong-scope or self-granted approvals reject, without waiver                                                  |
| Repair/debugger             | Finite declared edits produce deterministic rankings and read-only inspection                                                         | No invented evidence or grants, automatic application, hidden incomplete search or unique-cause claims                                                        |
| Scientific interoperability | Pinned SSSOM preserves multiplicity, provenance, direction, prefix expansion and uninterpreted numeric metadata                       | No collapsing distinct assertions or upgrading close/broad/narrow/related into identity; stale receipts and inventory tampering reject                        |

## Resource profile

Ingress is limited to 16 MiB per file, depth 64 and 2,000,000 JSON values. A graph permits at most 200,000 entities, 100,000 mappings, 1,024 authorities, 1,000,000 mapping endpoints, 64 packs and 4,096 relation definitions; each authority has at most 128 facts. Trace depth is at most 64. Policies allow 100,000 declarations/evidence records, 10,000 constraints and 1,000 waivers. Selector expansion and projection scanning each have a 2,000,000-operation limit; projections permit 128 slots. Diagnostics are bounded and include an explicit truncation error. These limits reject the candidate rather than silently omit mandatory checks. Later integer counters and costs must use checked arithmetic in the interoperable safe-integer range (0 through 9,007,199,254,740,991).

These are implementation limits, not demonstrated workload capacity or speed claims. Benchmark records must bind workload, architecture, toolchain and exact build. A rewrite is justified only by working native distribution, preserved semantics and measured operational value; matching tests does not establish correctness and Rust alone does not establish an advantage over the existing TypeScript system.

## Linux host threat model

The implemented protected activator requires a separately installed root-owned executable and adjacent `trust.json` on a selected local Linux filesystem. A deployment binding in that trust record fixes the state directory and proposer roots. The proposer is an independent unprivileged UID and cannot choose the trust path, state root, host time, implementation binary or environment. Current host trust/grants/revocations and baseline are reread while holding a native lock through publication; root-owner `trust-update` uses that same lock and refuses implicit consumer/layout migrations. Descriptor-relative/no-follow file access and owner/type/link checks defend against substitutions. These mechanisms pass real Linux permission/crash acceptance at the [identified source snapshot](acceptance/linux-vm/native-tests.json); macOS refuses activation.

The portable Rust `MemoryHost` implements a separate `patamaps-memory-draft-1`
profile. Its externally selected provider returns current trust/time; incoming
requests use the same closed `activation-request` and exact signed prepared
artifacts. Memory trust has no Linux deployment binding. Consumer, environment
and trust identity are fixed at construction. Exclusive mutable borrowing
serializes transitions, and current authorization is repeated after preparation
before assigning one immutable state. Refusal, provider failure and caught
provider panic preserve the prior state. An exact retry checks current
authorization against its original proposal baseline; other changes and
rollback bind the actual current baseline.

`memory-activation-manifest` has its own memory source executor, profile and
`urn:patamaps:memory-activation:` address domain. Historical verification checks
the address, predecessor, accepted trust/time, signature and complete artifact
bytes. It does not establish current host authority or restore an active state.
`MemoryState` has private fields and cannot deserialize. This API provides no
filesystem persistence, independent-UID or crash guarantee; see
[decision 0014](decisions/0014-governed-memory-host.md).

## Inspection and workspace boundaries

`repair-request` supplies one verified capture, finite exact edits, permitted/protected scopes and safe integer work/time/output bounds. Repair emits candidate captures and patches; it never applies them. Approval actions are conservative proposed requirements, not grants. Cancellation and limit exhaustion report incomplete search; minimality is only within a completely explored declared finite space. See [decision 0007](decisions/0007-inspection-draft.md).

Inspection creates a private checked explanation from verified replay and uses it for both JSON and escaped offline HTML. Missing source bytes, unknown assessments, rejected evaluations and ambiguous records stay visible. Navigation bounds and truncation are explicit. It does not authenticate discovery assertions or report production activation.

`workspace-config` supplies explicit composition ID/namespace/revision, sources, packs, policy, projections/emissions, context and logical evaluation time. `generate` captures actual sources and returns a `workspace-baseline` and native bytes; it never silently rebinds policy. `check` recomputes sources and compares the bound baseline without accepting drift. Optional process adapters use versioned `adapter-request`/`adapter-response` envelopes, exact captured input receipts, configured absolute executables/argument vectors and checked integer limits. They cannot be named by replay captures. Processes run without an inherited environment; the protocol does not claim an OS sandbox or undisclosed dependency closure. See [decision 0008](decisions/0008-adapters-distribution-draft.md).

`verify_baseline` and the native `verify-workspace` command reconstruct the complete recorded workspace before returning a private `VerifiedWorkspace`. They bind ordered discovery, raw source/code inputs, invocation/request addresses, exact composed graph, captures and emitted bytes through the same pure assembly used by generation. Process records include their recorded executable digest; offline verification never executes it or reads its path. The composed graph's `workspaceLineageDigest` binds configuration, workspace executor and complete discovery metadata into evaluation, while retaining the authored revision. Source files may be absent for offline verification because the record contains their exact UTF-8 bytes. Missing captured content refuses workspace reconstruction explicitly; ordinary graph replay can still verify with missing source receipts. `check` verifies historical consistency before any current source reads. This does not establish source truth, authentication, current authorization or deployed state. See [decision 0015](decisions/0015-workspace-recorded-lineage.md).

The debugger authorizes only the fixed stylesheet through its exact SHA-256 CSP hash; it permits no arbitrary inline style content. The installed output check computes the hash independently from the rendered stylesheet. Static output verification does not imply interactive browser acceptance. See [decision 0016](decisions/0016-debugger-style-csp.md).

Complete addressed artifact sets and manifests are staged immutably, with file/directory syncing, before one active pointer is atomically replaced. Readers bind one whole addressed generation. Failures after possible publication are indeterminate and reconcile against protected state; a retry or rollback obtains fresh current authorization. Process SIGKILL tests do not prove power-loss durability. Root compromise, a malicious approved native handler, remote/network filesystems and production key custody are outside the initial guarantee. Portable macOS tests and in-memory mocks do not satisfy the independent-UID Linux gate.

## Migration and distribution

The reference engine is fixed at `399747a4ad05a37cd8db1cedd53048fad2175be4`. Original schemas, records, historical evaluation failures and hashes are preserved under `fixtures/reference`; successor envelopes never overwrite them. Conversion is a new evaluation, with an explicit migration report and new addresses. Old approvals never authorize the new compiler or artifacts. D001–D009 in the conformance manifest are intentional differences and have explicit controls or migration receipts. The matrix records reference executions and native profile destinations separately; it does not claim full old API parity.

Apache-2.0 LICENSE and NOTICE accompany copied reference material. Public branding, namespaces and release remain separate from this local draft. Portable compiler build/install commands use Cargo with a locked dependency graph; Node is optional reference/adapter tooling, and native Rust consumers require no graph compiler at runtime. Production installation, trust provisioning, public publishing and consumer activation require their own acceptance and adoption decisions.

## Scientific source and closed crate profile

The native SSSOM 1.0 entity TSV importer preserves raw UTF-8 source bytes, decoded
cells, effective fields, prefix expansion, origin records and duplicate assertions.
Its pinned MappingSet schema is checked without remote/file resolution. Source
IDs may be original opaque ASCII names or valid URIs; namespaces and anonymous
assertion identity rules remain explicit. Scalar confidence stays metadata and
imported loss stays unknown. Literal, negated, unmapped, malformed-prefix and
undefined extension records refuse. Default export preserves semantic fields;
explicit condensation reports changed origins and normalizations.

Scientific crates contain one exact captured source, complete verified receipts,
replayed graph/policy/proofs, native projections/bindings, export/loss reports and
the pinned RO-Crate 1.2 context. Verification regenerates every byte and all
metadata. Limits are 256 files, 16 MiB aggregate payload/transport bounds and
64 external source references. Missing captured bytes refuse; external producer
sources remain references. Neither crate verification nor independent SSSOM/RDF
checks establish scientific truth, approval or activation. See
[decision 0009](decisions/0009-scientific-draft.md).

Built-in topology totality, reachability and context-provider obligations use
active checked mappings, exact relation-scoped exclusions and the closest scope
with one unique provider. Two providers at the same scope depth refuse. Work is
bounded across all topology constraints at 2,000,000 visited/checked steps; each
evaluator permits at most 1,024 findings before an explicit diagnostic refusal.
Exhaustion never yields admission. Ownership/exclusion metadata remains a
declaration, not authenticated host authority.

## Explicit native constraint extensions

The Rust library exposes `ConstraintRegistry`, `ConstraintEvaluationContext` and
`admit_with_constraints`. Registered code borrows immutable inputs and returns
typed findings. Built-ins cannot be replaced; missing evaluators, failures,
unwind panics, invalid or over-limit findings and exhausted controls refuse.
Namespaced custom errors cannot impersonate ordinary waivable findings. Used
implementation bindings are included in the generation address in UTF-16 kind
order; unused registrations have no effect. This host attribution does not
authenticate the evaluator implementation.

In-process callbacks are trusted host code and use cooperative cancellation;
this API cannot preempt a callback that never returns. Default portable capture,
replay, artifact preparation and protected publication install no custom code.
Unknown-kind refusal can be captured and verified, but serialized custom results
cannot restore admission. This preserves MetaMap’s explicit built-in-only replay
boundary. See [decision 0012](decisions/0012-native-constraint-evaluators.md) and the
[current compiler checkpoint](acceptance/capabilities/compiler-2026-10-14T15-51-21.761649Z/receipt.json).
