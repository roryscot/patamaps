# Rust-first MetaMap rebuild

Date: 2026-10-11. Project name: **Patamaps**, chosen by the owner. R0–R11 are implemented for the declared draft profiles on ARM64 macOS and Linux. Native routing, application topology, replay, checked laws/proofs, typed uncertainty, risk budgets, external approvals, protected activation, bounded inspection, workspaces and scientific integration are delivered. [Current naming and verification](docs/acceptance/2026-10-11-patamaps.md) identifies the renamed candidate; [earlier acceptance](docs/acceptance/2026-10-11-final.md) remains historical evidence. No public release or production activation has occurred.

**Recommendation: rebuild the compiler and protected activator in Rust, while retaining MetaMap's semantics, portable data, reference cases, and useful discovery adapters.** A line-by-line TypeScript translation would preserve implementation debt. Replacing every adapter and contract would discard working interoperability and increase migration risk. The useful boundary is a new Rust implementation of the existing correspondence compiler, introduced through a declared compatibility profile and a staged consumer migration.

Rust owns graph validation, scoped authority, admission, derivations, uncertainty, budgets, projection, replay, explanations, governance verification, and protected activation. Language-specific discovery can continue in TypeScript or Python and emit portable shards. Generated consumers execute ordinary native structures; they do not require the graph compiler at runtime.

This document makes the README's R0–R11 sequence actionable. The README controls product scope; this plan controls proposed implementation order and acceptance. MetaMap's pinned contracts define reference behavior for the explicitly shared profile. New contract decisions must record intentional differences. Test expectations and historical results are preserved evidence, not permission to deploy or proof that the new implementation is correct.

## 1. Inspected baseline and limits of the evidence

| Observation                                                 | Evidence and implication                                                                                                                                                                                       |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Patamaps currently contains a README and no Cargo workspace | Inspected clean `main` at `ab6efc333a3c90f7ce9235822b49098809d8b159`. This is a new implementation, not an existing Rust refactor.                                                                             |
| MetaMap is a substantial TypeScript implementation          | Local package version `0.7.1`: 64 production TypeScript files / 24,077 lines, 45 JSON schema files, 5 relation packs, and 53 test files. Counts describe scope, not estimated effort.                          |
| The reference engine is already implemented                 | Pin engine `399747a4ad05a37cd8db1cedd53048fad2175be4`; inspected checkout `6a6a9d2415df85504a83fce4fd7291d0391c0d17` differs only in its build record. Preserve both identities.                               |
| Current portable behavior has a useful local baseline       | `npm run typecheck` and 131 tests in 8 selected files passed during this planning task. This is focused coverage, not a rerun of every feature.                                                                |
| Protected activation has stronger recorded verification     | The reference build record reports 600 tests / 53 files in Linux CI, independent-UID permission checks, and five SIGKILL phases. Those Linux checks were not rerun here.                                       |
| Performance and reviewer-benefit claims remain limited      | The historical evaluation found equivalent admission decisions; replay/comparison was slower in its bounded warm comparison trial. Reviewer-effort studies remain deferred. Those results do not measure Rust. |

The controlling reference materials inspected were `VISION.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, the completed `BUILD_PLAN.md`, package/CI configuration, evaluation records, and representative implementation and tests. Relevant pinned sources:

- [Architecture](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/ARCHITECTURE.md) and [contract decisions](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/CONTRACTS.md).
- [Reference source modules](https://github.com/roryscot/metamap/tree/399747a4ad05a37cd8db1cedd53048fad2175be4/src) and [functional evaluation corpus](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/evaluation/capability-corpus.json).
- [Historical evaluation and its negative results](https://github.com/roryscot/metamap/blob/399747a4ad05a37cd8db1cedd53048fad2175be4/evaluation/README.md) and [closing build record](https://github.com/roryscot/metamap/blob/6a6a9d2415df85504a83fce4fd7291d0391c0d17/BUILD_PLAN.md).

**Strongest objection:** the TypeScript system already works, and a rewrite can consume months while losing safeguards. Rust does not establish semantic correctness or a performance advantage. Continue toward replacement only when the native distribution, checked API boundaries, and measured operating characteristics justify the migration. If reference behavior is insufficiently specified, finish that specification before translating its implementation.

## 2. What to reuse, rebuild, optimize, or discard

“Reuse” means preserve the stated artifact or behavior. TypeScript tests become language-independent cases with Rust runners; they are not mechanically converted and then treated as independent evidence. “Discard” means omit machinery from the successor runtime, while retaining the original repository and historical records.

| Area / reference files                                                                                                           | Decision                                         | Concrete treatment                                                                                                                                                                                          |
| -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Identity, locators, n-ary mappings; `model.ts`, `references.ts`                                                                  | Reuse semantics; rebuild types                   | Preserve stable IDs, open entity kinds, directional endpoint groups, cardinality, lossiness, and independently owned sources. Rust internal indexes never replace external IDs.                             |
| Graph queries and validation; `graph.ts`, `validator.ts`                                                                         | Rebuild and optimize                             | Use one immutable indexed hypergraph and checked constructors. Retain existing identity/adjacency indexes; do not claim indexing as a new capability. Remove public validation bypasses for checked states. |
| Shard merging; `composer.ts`                                                                                                     | Reuse rules; rebuild merge engine                | Equal declarations can deduplicate; conflicting definitions and incompatible pack references reject. Keep shard merging distinct from inference. Preserve source-order lineage where order is meaningful.   |
| Fact ownership and delegation; `graph.ts`, `validator.ts`                                                                        | Reuse behavior; rebuild                          | Canonical/candidate/delegated status, narrowing scopes, root/leaf resolution, cycles, and branch conflicts retain explicit checks. File location cannot confer authority.                                   |
| Workspace discovery and drift; `workspace.ts`, `config.ts`, `correspondence.ts`, `diff.ts`                                       | Rebuild orchestration; retain contracts          | Source-local fingerprints, explicit overlays, baseline checks, and stable-ID diffs remain. `check` cannot accept drift or replace a baseline.                                                               |
| Relation vocabularies and declarations; `relation-packs/`, `relations.ts`, `relation-pack.ts`                                    | Reuse content with explicit version handling     | Keep software, routing, topology, research, and scientific distinctions. Preserve original pack bytes in fixtures; changing their envelope or digest convention creates a new profile/version.              |
| Viability, contexts, selectors, constraints; `viability.ts`, `context.ts`, `constraints.ts`                                      | Reuse rules; rebuild one engine                  | Require complete coverage, explicit time/context, evidence, exact waivers, and consumer constraints. Preserve empty/overlapping selector rejection and topology totality.                                   |
| Derivations; `derivation.ts`, `semantic.ts`                                                                                      | Rebuild around checked proof records             | Retain bounded explicit reverse/chain laws, premise/context/pack bindings, conservative loss, and refusal cases. N-ary graph storage survives; generalized n-ary inference is not an initial requirement.   |
| Typed uncertainty and budgets; `uncertainty.ts`, `risk.ts`                                                                       | Reuse policy semantics; optimize closure work    | Preserve six dimensions, evidence attribution, unknown/contradicted states, unique dependency costs, complete classification, and checked integer arithmetic.                                               |
| JSON/TypeScript projections; `projection.ts`, `semantic-projection.ts`                                                           | Reuse output requirements; rebuild emitters      | Keep cardinality/kind/loss checks and exact input binding. Add native Rust IDs and typed bindings without maintaining a second handwritten registry.                                                        |
| Path trees and hydration; `path-tree.ts`, `semantic-path-tree.ts`                                                                | Reuse abstraction; rebuild shared implementation | Keep structural templates separate from occupants/parameters. Hydration cannot alter mappings, add capabilities, or admit a new structure.                                                                  |
| Replay, source capture, comparison, impact; `replay.ts`, `semantic-replay.ts`, `provenance.ts`, `counterfactual.ts`, `impact.ts` | Reuse evidence model; rebuild                    | Capture success and rejection, source/candidate differences, changed origins, and declared dependency paths. Preserve unknown deltas and missing-source limits.                                             |
| Proposals and approvals; `governance.ts`, `governance-model.ts`                                                                  | Reuse trust rules; rebuild verification          | Exact external approval, consumer/environment/base/artifact bindings, fact/action scopes, expiry, revocation, and protected actions remain mandatory. Existing approvals do not migrate.                    |
| Protected persistence; `protected-activation.ts`, `activation.ts`                                                                | Rebuild in native Rust                           | Replace the `/usr/bin/flock` + shell/cat helper with a native held lock. Retain Linux permission boundaries, immutable staging, precommit rechecks, atomic pointer publication, and indeterminate outcomes. |
| Bounded repair; `repair.ts`                                                                                                      | Reuse finite edit model; rebuild                 | Keep exact candidate patches, protected edit refusal, deterministic ranking, incomplete-search reporting, and approval requirements. Improve cancellation checkpoints without weakening evaluation.         |
| Explanations/debugger; `explanation.ts`, `debugger.ts`                                                                           | Reuse report semantics and useful view design    | Generate the view from the same verified Rust report. Keep escaped content, offline assets, visible unknowns, and read-only interaction. A new frontend framework is unnecessary.                           |
| TypeScript/Zod and Next.js discovery; `adapters/typescript-zod.ts`, `adapters/nextjs-app-router.ts`                              | Reuse as optional adapter tools first            | Keep their framework/compiler knowledge behind a versioned process/shard boundary. Rewriting TypeScript AST discovery in Rust has no demonstrated initial benefit.                                          |
| Prisma, JSON collection, and legacy source adapters; `adapters/`                                                                 | Retain initially; port selectively               | Keep the working exporters. Portable-shard ingestion is the first native adapter; JSON ingestion and simple source readers can follow demonstrated consumer demand.                                         |
| SSSOM import/export and RO-Crate; `sssom.ts`, `adapters/sssom-tsv.ts`, `scientific-crate.ts`, `standards/`                       | Reuse sources/profile; rebuild transforms        | Preserve raw licensed sources, multiplicity, direction, provenance, metadata, unknown loss, and independent checker limitations.                                                                            |
| Schemas, examples, corpus, failure cases, licenses                                                                               | Reuse as compatibility evidence                  | Preserve original bytes, provenance, LICENSE/NOTICE and fixture licenses. New wire identities get new schemas. Published reference schemas are never edited to fit Rust.                                    |
| `semantic-*` wrappers and v2-as-v1 internal views                                                                                | Discard internal duplication                     | Build one checked semantic pipeline. Legacy readers/converters live at ingress; they do not cause two production policy engines.                                                                            |
| Legacy `stableJson` hashing; `stable.ts`                                                                                         | Discard for newly addressed successor records    | All new records use the declared canonical profile. Keep original legacy digests and captures as evidence; conversion never relabels them as new canonical values.                                          |
| Node, npm `dist/`, Ajv, and TypeScript compiler inside the kernel                                                                | Discard runtime dependence                       | Use native parsing/validation and Cargo distribution. Node remains an optional adapter/reference-test dependency. YAML remains a source-format adapter concern.                                             |
| Automatic activation fallback, ambient trust/time, unchecked restored state                                                      | Exclude from the new API                         | Revalidate persisted inputs; require current host authorization at publication. A checked Rust value cannot make a stale approval current.                                                                  |
| Immediate database, daemon, RPC platform, FFI, WASM, arbitrary executable packs                                                  | Defer                                            | Repository-scale in-memory compilation and files satisfy the initial product. Add another execution/storage boundary only for a measured consumer need.                                                     |

Reuse Apache-2.0 for the successor as the default recommendation and carry the required notices for copied material. Keep scientific fixture licenses alongside their sources. Final branding and publishing namespaces remain decisions before public contracts are released.

## 3. Proposed Rust structure

The workspace now contains nine production crates, named `patamaps-*` after the owner's project-name decision.

```text
crates/
  patamaps-contracts/   wire records, strict decoding, canonical bytes, digests
  patamaps-core/        graph, authority, admission, proofs, uncertainty and risk
  patamaps-projection/  checked slots, native emitters, path trees, capture/replay
  patamaps-cli/         explicit files/processes, commands, human-readable output
  patamaps-governance/  R6: pure external grant/signature/change verification
  patamaps-activator/   R7: small Linux host binary and protected transaction
  patamaps-inspect/     R8: finite repairs and shared captured JSON/HTML reports
  patamaps-workspace/   R9: portable/process discovery, generate/check and cache
  patamaps-scientific/  R10: pinned SSSOM import/export and closed RO-Crate profile
fixtures/
  reference/           pinned MetaMap sources, outputs, and compatibility pins
  independent/         normative vectors and separately stated expectations
scripts/reference/     optional pinned TypeScript comparison/export harness
docs/
  SPEC.md              semantics, wire rules, migration and threat-model sections
  decisions/           consequential compatibility and implementation decisions
  acceptance/          revision-bound verification records, created after runs
```

Nine crates, draft schemas/packs, specification and reference harness now exist. Governance, Linux activation, inspection, workspace orchestration and scientific integration are implemented and verified. Linux runtime acceptance passes on the recorded root-owned ARM64/ext4 profile; the portable SDKs use the same evaluator. The conformance harness remains outside the production dependency path.

### Type and state boundaries

Use wire structs for untrusted input and private-field types for `CheckedGraph`, `CheckedDerivation`, `AdmittedGeneration`, `CheckedProjection`, and `AuthorizedChange`. Public deserialization returns wire values only. Checked constructors return structured errors; there is no public deserializer or unchecked constructor for a checked state.

Use newtypes for semantic IDs, relation IDs, digests, and indexes. Entity kinds and external vocabularies remain open strings; lifecycle statuses and the allowed governance actions use closed Rust enums. Store mappings as explicit source/target groups rather than reducing the model to binary edges. A normal indexed representation is sufficient initially; a generic graph library is not an architectural requirement.

An immutable evaluation session owns the graph, exact packs, policy/evidence, context, logical evaluation time, and resource profile. Reuse validation and proof results only within that bound session. When a generation is restored from disk, recompute the required checks. When an approval is used, the activator obtains current trust, time, and baseline independently.

The pure kernel forbids project-authored unsafe code and has no filesystem/network/process/ambient-clock access. Explicit limits yield rejection or an incomplete operational result; cancellation is not admission. Native host operations are isolated in the activator. Rust's memory guarantees do not replace policy or transaction checks.

### Dependency policy

Use the standard library first. Proposed supporting dependencies are `serde`/`serde_json` for wire decoding, `clap` for the CLI, a structured error crate such as `thiserror`, SHA-256 support, `ed25519-dalek` for approval verification, and safe OS wrappers such as `rustix` for the Linux boundary. Property tests, compile-fail checks, and a benchmark harness belong in development dependencies. Select exact versions, features, licenses, and a pinned stable toolchain in R0; commit `Cargo.lock` for the workspace and binaries.

Ordinary JSON serialization is not the canonical encoder. Duplicate decoded keys must be rejected before object construction loses them. Choose a JCS encoder only after normative vectors pass; SHA-256 addresses the resulting UTF-8 bytes. RFC 8785 requires UTF-16 key ordering and ECMAScript-compatible numeric serialization. [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) and the [serde_json API](https://docs.rs/serde_json/latest/serde_json/) are separate contracts.

Use `verify_strict` and independent signature vectors when adopting `ed25519-dalek`; its documentation explicitly discusses weak-key rejection. Native `rustix::fs::flock` supplies an advisory lock, whose effectiveness still depends on protected ownership and every writer obeying the transaction protocol. [Ed25519 verification](https://docs.rs/ed25519-dalek/latest/ed25519_dalek/struct.VerifyingKey.html), [native flock API](https://docs.rs/rustix/latest/rustix/fs/fn.flock.html).

Do not add an async runtime or parallel graph engine by default. The CLI can manage bounded child adapters; the deterministic CPU kernel remains synchronous with explicit cooperative cancellation checkpoints. Add concurrency when benchmarks identify useful independent work.

## 4. Compatibility and migration decisions

Default shared profile: **the current tested MetaMap 0.7.1 graph/admission/projection semantics at the pinned engine**, including the later derivation, uncertainty, governance, and source-bound capabilities as their milestones become executable. R0 enumerates supported operations and cases; a broad profile name is not evidence of full compatibility.

1. **Keep semantic identities and decisions.** Compare owner resolution, admitted/rejected mappings, proof dependencies, uncertainty states, unique risk closure, slot resolution, and diagnostic subjects/origins. Human message wording can differ; unexplained decision differences block the affected gate.
2. **Give the successor explicit wire identities.** Use a coherent new envelope family and JCS for newly addressed values. Preserve missing/null distinctions, ordered arrays, Unicode without normalization, finite numbers, safe integer costs, and extension policy. Do not change published MetaMap contracts in place.
3. **Treat legacy ingestion as conversion.** A pinned external legacy exporter can verify old digests using the original executor and emit canonical portable inputs plus a migration report. Keep original records/bytes and old-to-new bindings. The initial native core need not recreate JavaScript locale collation. Native direct readers can follow only with demonstrated legacy digest conformance.
4. **Keep historical replay honest.** Run an old replay only with its recorded compatible executor. Rust evaluation of converted inputs is a new capture with a new executor identity. Captured code paths never select or execute code automatically.
5. **Require fresh authorization.** Old signatures, active pointers, artifact hashes, and baselines cannot authorize the new compiler's output. Shadow compilation and native consumer testing precede a separately reviewed installation and approval against the new baseline.
6. **Classify differences explicitly.** Engine receipts, protocol envelopes, Rust artifacts, and new approval domains differ deliberately. Store complete original results and a narrow, versioned comparison projection. Never strip arbitrary provenance or update golden expectations just to make the diff pass.

This is semantic compatibility plus explicit data migration, not a promise of byte-for-byte replacement of every legacy API. Adapters can remain operational through conversion without forcing the native runtime to depend on Node. If a consumer requires direct old-wire drop-in compatibility, size and decide that additional work before promising it.

## 5. Optimization priorities and measurements

Rust is a delivery and implementation choice. Performance improvements below are hypotheses until measured against the pinned reference on identical inputs and feature profiles.

| Priority      | Evidence / opportunity                                                                                                                 | Planned optimization                                                                                   | Guardrail                                                                                                                                |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| First         | Graph construction and validation occur at several boundaries; `MetamapGraph.from` validates before a constructor that validates again | Validate once when creating an immutable checked session; reuse its indexes and resolved pack registry | Revalidation remains mandatory for untrusted/restored records. No cache can create authority.                                            |
| First         | `compileSemanticProjection` can recompile policy/evidence-bound admission before compiling each projection                             | Compile shared admission once and project several specs from the same checked session                  | Persisted generations are rechecked; session keys bind all semantic inputs, limits, context, and logical time.                           |
| First         | Current code materializes cloned values, sorted objects, and encoded strings for repeated digesting                                    | Decode once, use typed immutable records, and hash canonical output through a shared encoder           | Exact canonical byte tests pass before allocating less memory. Object ordering is not Rust `Ord` ordering by assumption.                 |
| First         | Protected locking currently needs an external helper process                                                                           | Hold the lock through a native descriptor/RAII guard for the complete transaction                      | The same real UID, race, stale-base, and crash acceptance remains required. RAII does not handle SIGKILL by running cleanup.             |
| Next          | Proof, uncertainty, and consumer budgets traverse overlapping dependencies                                                             | Cache closure and checked premise summaries inside the bound session; deduplicate by mapping/proof ID  | Unknowns, conflicts, all contributing evidence, and complete unique costs remain visible.                                                |
| Next          | String IDs are repeatedly carried through indexes and worklists                                                                        | Introduce dense typed indexes behind stable-ID lookup; use bounded iterative traversal                 | Stable identities and deterministic outputs remain unchanged. Keep existing adjacency indexing benefits.                                 |
| Measured only | Unchanged independent sources can reuse discovery results                                                                              | Content-addressed adapter results; parallel discovery only if useful                                   | Keys bind adapter identity/configuration/source/profile. Revalidate hits; preserve declared ordering/lineage.                            |
| Measured only | Repair checks deadlines between candidates while individual checked steps can run longer                                               | Add bounded work and cancellation checkpoints in long traversals; reuse candidate-invariant work       | Exhaustion stays incomplete. Do not skip semantic checks, invent a global-minimum claim, or change policy bounds.                        |
| Deferred      | Large graph storage or widespread parallelism                                                                                          | Incremental admission, persistence, alternative hashers, thread pools, binary formats                  | Introduce only after profiling. Incremental output must match full recomputation, including deletions and changed laws/trust boundaries. |

### Benchmark design

Create fixed-seed valid and rejecting graphs at 1k, 10k, and 100k mappings; include deep delegation, branching proofs, many projection specs, topology removals, and overlapping consumer dependency closures. Record exact bytes, seeds, compiler identities, host/toolchain, and supported resource limits. If a size exceeds the declared limit, measure its controlled refusal separately from successful compilation.

Measure cold process startup, decode/canonical hashing, graph check, admission, projection batches, replay, and bounded repair separately. Measure warm core work separately from CLI I/O and source discovery. Capture elapsed time, peak memory, artifact/binary size, and dependency/runtime installation footprint. Use repeated trials, retain raw samples, and report distributions rather than a best run.

Performance acceptance has two parts: all semantic controls still pass, and each claimed optimization improves its declared workload beyond observed run-to-run variation. Record regressions too. A native release can be justified by installation and API boundaries without claiming speed; unexplained material regressions require a recorded disposition. Human-review benefit and broad comparative reliability remain outside this build's acceptance claims.

Measurement coverage now passes the predeclared controls: seven trials for valid/rejecting 1k/10k inputs and 100k byte-limit refusal, deep delegation, branching proofs with overlapping cost closure, projection batches, topology removal and finite repair. Fresh CLI startup/compilation, warm SDK phases and explicit provider discovery are separate; per-child peak RSS, artifact/binary sizes and dependency footprint are retained in the [phase receipt](docs/acceptance/benchmarks/phase-benchmark.json) and [method](docs/acceptance/benchmarks/METHOD.md). The 100k result is controlled refusal, not successful capacity. No matched TypeScript baseline, Rust performance advantage or Linux host measurement is claimed.

## 6. Build backlog and acceptance gates

Checkboxes record delivered work; milestone gates and the reference manifest separately record verification coverage. R0–R11 pass their declared draft controls, including macOS and Linux package installation, the protected Linux boundary and the complete governed lifecycle. All 53 reference files have run; the matrix records their native profile destinations without claiming one-for-one old API parity. All 22 original binding scenarios pass. Do not infer full MetaMap API parity or production readiness from these results. R0–R3 provide a developer preview; R4–R7 provide the semantic and protected-host boundaries; R8–R11 complete the README's scope.

| Milestone                          | Depends on                       | Result needed before proceeding                                                             |
| ---------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------- |
| R0 Specification and corpus        | Reference intake                 | Public-byte, identity, compatibility, and threat-model decisions are explicit               |
| R1 Pure checked kernel             | R0                               | Valid independent shards and fact ownership work; invalid input cannot become checked state |
| R2 Native binding slice            | R1                               | Rust and TypeScript consumers execute across a real implementation move                     |
| R3 Replay and conformance          | R1, R2                           | Success/refusal captures reproduce; differential disagreements are classified               |
| R4 Declared relation laws          | R1, R3                           | Only checked bounded derivations can enter admitted output                                  |
| R5 Uncertainty and budgets         | R2, R4                           | Consumer-specific evidence and complete unique costs govern projection                      |
| R6 External approvals              | R3, R5                           | Exact scoped signatures authorize only the stated candidate/base/artifacts                  |
| R7 Protected Linux activation      | R6                               | Real permissions, serialized publication, races, and crash recovery pass                    |
| R8 Repair and debugger             | R3–R6                            | Bounded read-only proposals and the shared explanation view preserve limits                 |
| R9 Adapters and distribution       | R2, R3; R6/R7 for governed calls | Clean native installations and optional language tools use one kernel                       |
| R10 Scientific profile             | R3–R5, R9                        | SSSOM/RO-Crate controls preserve source distinctions and provenance                         |
| R11 Consumer migration and release | R0–R10                           | Packaged revision passes lifecycle, migration, and supported-target gates                   |

### R0 — Freeze the executable contract

- [x] Create a concise `docs/SPEC.md` covering charter, lifecycle, semantic rules, canonical bytes, versioning, migration, resource limits, and the Linux threat model. Assign one owner document to each decision rather than copying policy across files.
- [x] Create a conformance manifest mapping every applicable reference capability/test to a Rust case, legacy-only migration case, Linux-host case, intentional difference, or independent normative control. Include the 22 native-binding corpus cases and preserve the original negative evaluations.
- [x] State expectations for JCS numbers/Unicode/duplicate keys, graph conflicts, ownership narrowing, selector coverage, invalid inference, unknown evidence, budget edges, stale approvals, tampered artifacts, and replay of rejection.
- [x] Scaffold the first four crates, pin toolchain/dependencies, retain notices, and establish format/lint/test/package commands. Set precise supported limits and API/wire compatibility before downstream code depends on them.

**Gate:** no unresolved choice changes IDs, signed bytes, admissibility, or trust boundaries for a published profile. The matrix covers every README vision element. The manifest contains positive controls; rejecting everything cannot pass.

### R1 — Build contracts, indexes, and ownership

- [x] Implement strict JSON ingress, bounded decoding, explicit extension handling, canonical encoding/digests, and version dispatch. Load only supplied/embedded schemas and packs; no implicit remote references.
- [x] Implement entities/mappings/authority, shard merge, locator/reference checks, relation endpoint/cardinality/cycle checks, fact-scoped resolution, and structured diagnostics.
- [x] Build immutable identity/adjacency/authority indexes and basic `validate`, `trace`, and `authority` operations. Keep inspection of rejected candidates separate from checked graph construction.

**Gate:** normative parser vectors pass; equivalent unordered declarations behave deterministically; duplicate/conflicting declarations, dangling references, widened/cyclic delegation, and invalid relation use reject. Public compile-fail cases show that checked states cannot be forged through safe unchecked APIs. Core tests use explicit inputs without I/O or ambient time.

### R2 — Prove the central abstraction in native consumers

- [x] Implement explicit policy/context admission for the first routing profile, then checked projection selection, slot cardinalities, target kinds, and loss constraints.
- [x] Emit JSON, typed TypeScript bindings, and native Rust IDs plus a static table or `match` dispatch. Generated Rust imports must compile against actual consumer modules; identifiers/strings/paths are escaped and validated. No reflective symbol loader is required.
- [x] Recreate the independently owned operation/schema and service/handler example. Move an actual handler file/module while preserving its semantic ID, rebuild, and execute both consumers. Check refused changes preserve previously accepted outputs.

**Gate:** real requests execute before and after the move; missing/ambiguous/wrong-kind/lossy links fail with the expected origins. Portable inputs compile with the native CLI on a host without Node. The TypeScript consumer's own build still uses its normal tools. Generated runtime dispatch does not traverse the correspondence graph.

### R3 — Capture results and establish the reference harness

- [x] Capture graph, packs, policy/evidence, context/time, source receipts, projections, executor/profile identity, and successful or rejected results. Keep raw-source availability distinct from a digest receipt.
- [x] Implement offline replay, stable-ID diff, explicit before/after comparison, impact origins, and structured explanations using captured inputs. Never rediscover or run bundle-named code during replay.
- [x] Run the isolated pinned TypeScript reference against the shared corpus. Store complete outputs plus normalized comparison results and documented differences. Add independent controls for bugs both implementations could share.

**Gate:** successful and rejected captures reproduce; missing/tampered dependencies and mismatched executors reject explicitly. Input changes, issue subjects, and paths remain separate. No unavailable projection/risk delta becomes zero. Every unexplained shared-profile disagreement blocks the relevant milestone.

### R4 — Add checked composition without inventing semantics

- [x] Implement the reference finite reverse/chain vocabulary with exact imports, endpoint roles, context conditions, conservative loss/reversibility, and disjointness checks.
- [x] Check proofs against exact premises, revisions, pack values, evidence dependencies, and depth/count limits; record inspectable applications and dependency closure.
- [x] Extend projection, path-tree, replay, and comparison through that same evaluator. Keep general n-ary correspondence storage; explicitly refuse unsupported law operations.

**Gate:** permitted controls pass; reversed roles, stale proofs/context, forbidden chains, incomplete inputs, and irreversible premise misuse fail. `closeMatch` cannot become transitive identity. Derivations never transfer ownership or signing authority. Resource exhaustion is explicitly incomplete.

### R5 — Preserve uncertainty and account for risk once

- [x] Implement identity, context, provenance, completeness, causal-relevance, and conflicting-authority dimensions with supported/contradicted/unknown/reasoned-not-applicable states.
- [x] Bind assessments to exact evidence, subjects/revisions, assessors, and measurement models; propagate conservatively across checked premises. Preserve original scalar confidence as metadata.
- [x] Evaluate consumer requirements and unique used mapping/proof closure, complete risk classifications, integer totals, and lossy/inferred limits. Reuse closures within an immutable session.

**Gate:** a tolerant consumer and a stricter consumer reach their predeclared different outcomes. Below/at/above-budget cases behave correctly; shared premises cost once; missing classification, overflow, stale evidence, and budget opt-out fail. Direct support cannot erase an unknown premise. Ordinal costs are never presented as probabilities.

### R6 — Verify externally authorized changes

- [x] Implement complete artifact byte inventories and exact proposals with change classification, requested actions/scopes, consumer/environment, engine/profile, trust revision, and expected base.
- [x] Verify externally signed domain-separated Ed25519 payloads against host-provided keys/grants/revocations/time. Keep private signing keys outside the compiler and requests.
- [x] Preserve explicit owner requirements for bootstrap, rollback, authority/law changes, waivers, budget increases, and policy changes. Agent attribution and graph ownership do not establish signing grants.

**Gate:** legitimate scoped controls verify; forged/weak-key/expired/revoked/wrong-scope approvals, changed bytes/inputs/trust, and stale bases fail. A viable agent-proposed protected change remains unapproved. No legacy waiver or API can suppress authentication failures.

### R7 — Replace the lock helper and prove the Linux boundary

- [x] Build a separately installed fixed activator with protected host configuration and state. Requests cannot choose trust paths, state roots, clock, binary, or execution environment.
- [x] Hold a native lock through base/trust reads, staging, authorization recheck, and publication. Serialize trust administration through the same protocol. Use descriptor-relative/no-follow operations plus owner/type/link checks.
- [x] Stage immutable artifact sets, sync files/directories, and replace one addressed active pointer atomically on the selected local filesystem. Readers bind one complete generation; committed-state failures report indeterminate and reconcile with protected state.

**Gate:** a real separate proposer UID cannot change trust/runtime/lock/manifests/pointer/active bytes; concurrent stale-base proposals cannot both publish. Native readers see complete old or new state. SIGKILL tests cover locked, artifacts-ready, manifest-ready, precommit, and committed phases. Retry rechecks current authorization; rollback needs a fresh current-base approval.

This gate passed in a disposable ARM64 Linux guest on a private ext4 disk: independent UID denial, concurrency/stale bases, all five SIGKILL phases, current trust/revocation and actual native consumption after an approved move and fresh rollback. The [Linux receipt](docs/acceptance/linux-vm/native-tests.json) retains 110 native and 13 compile-fail passes, exact source-archive binding and raw output. Docker was not restarted; a separate guest used verified upstream boot/toolchain artifacts and no network device. The profile covers the root-owned Linux/local-filesystem model only. SIGKILL verification establishes process-crash behavior, not power-loss durability. Production installation and activation remain later adoption actions.

### R8 — Keep repair and debugging on the inspection side

- [x] Implement exact finite edit spaces, deterministic candidate compilation/ranking, counts of examined/unexamined combinations, budget/cancellation outcomes, and required approval actions.
- [x] Use the shared captured report for CLI inspection and an offline debugger. Reuse the existing useful view structure; validate escaping, keyboard/navigation, no external resources, and visible rejected/unknown states.
- [x] Poll cancellation inside expensive bounded work and preserve complete versus incomplete status. Minimality claims apply only to a fully explored declared space.

**Gate:** repair/debugger change neither sources nor active state; repairs cannot invent evidence or grants. Protected edits reject under the shared profile. Viable proposals still require approval. Reported changes refer to actual inputs and dependencies, without claiming unique causal responsibility.

The shared JSON/HTML report, escaping and native CLI flows pass automated checks. Mouse and keyboard navigation passed on synthetic rejected/viable reports via a fixed loopback fixture. The direct file URL was refused; a later browser reconnect was unavailable. The receipt identifies the tested engine and limits; no screen-reader or full accessibility certification is claimed. See decision 0007 for the single-projection repair profile and cooperative cancellation bounds.

### R9 — Package adapters and native distribution

- [x] Implement a versioned adapter process protocol covering configured invocation, inputs, fingerprints, shard output, diagnostics, byte/work limits, and exit/error behavior. Use explicit executable/arguments rather than shell command interpolation.
- [x] Ship portable-shard ingestion first; wrap existing TypeScript/framework exporters and revalidate converted results. Implement workspace `generate`/`check`, baseline preservation, complete cache keys, and cached/uncached equivalence.
- [x] Package the Rust SDK workspace and macOS native CLI, with thin TypeScript/Python wrappers and artifact readers. Keep governed activation Linux-only and optional discovery dependencies explicit.
- [x] Verify the Linux native distribution and independently installed consumers on Linux.

**Gate:** disposable consumers outside the checkout install the package, compile/read actual outputs, execute native behavior, and observe the expected errors. Portable compilation and the activator require no Node runtime; a selected TypeScript adapter may. All SDK semantic decisions come from the same Rust kernel. A Rust source scanner, FFI, WASM, or daemon is optional future work, not a prerequisite.

The nine-crate source workspace and release binaries pass disposable installation on ARM64 macOS and Linux, all SDKs, actual generated consumers, the 22-case binding migration, scientific lookup and all five pinned discovery adapters: four viable fixtures and the legacy-source refusal for undeclared loss. Each installation receipt identifies its actual archives; the final distributions share one exact source inventory. The Linux bundle includes the separately tested release activator without installing or activating it. Process caching is deliberately disabled because arbitrary providers cannot prove their complete dependency closure; portable cache hits are revalidated against current bytes and provide no measured performance claim.

### R10 — Port one faithful scientific profile

- [x] Import the pinned SSSOM 1.0 profile, retain licensed source bytes and assertion-level provenance, and preserve prefix expansion, direction, metadata, and repeated assertions.
- [x] Keep exact/close/broad/narrow/related distinctions, unknown lossiness, uninterpreted confidence, and the irreversible-premise guard. Consumer exploratory tolerances are separate declarations.
- [x] Export the bounded RO-Crate 1.2 profile with source captures, receipts, proofs, and inventory; run pinned independent SSSOM and RDF/RO-Crate checks in a separate test environment.

**Gate:** declared round trips preserve assertions and metadata; malformed prefixes, duplicate IDs, stale receipts, and inventory tampering reject. A useful native lookup passes positive controls, while unsupported evidence policies reject. Preserve the known reference checker defect and any failing mode honestly. Format conformance does not establish scientific truth or calibrated confidence.

### R11 — Migrate a consumer and close the lifecycle

- [x] Execute the complete lifecycle from independent sources through admission, budgets, artifacts, external approval, protected activation, consumption, implementation move, and freshly approved rollback.
- [x] Choose one existing consumer and migrate in a separate change: shadow compile, classify differences, run its native tests, install the tested outputs, and retain its authored correspondences/ownership/policies.
- [x] Verify the exact packaged candidate on every advertised target, record toolchain/features/commands/results, and document supported profiles and limits. Public release and consumer activation remain explicit subsequent decisions.

The [portable shared lifecycle](docs/acceptance/lifecycle-pure.json) passes composed source ownership, checked derivation, explicit unknown-identity tolerance, complete cost-three closure, capture/replay, native dispatch and read-only inspection/repair. Stricter uncertainty and budget controls refuse. The same fixture passes the [Linux host run](docs/acceptance/linux-vm/native-tests.json) and [release-executable run](docs/acceptance/linux-vm/release-host.json): external approval, protected activation, independent-UID consumption, stable implementation move and freshly approved rollback. The [final acceptance record](docs/acceptance/2026-10-11-final.md) links the exact installed packages and unchanged-source attestation.

**Gate:** all applicable R0–R10 cases pass at the packaged revision; positive controls remain useful; no unexplained semantic drift or missing Linux acceptance exists. Record implemented, verified, reviewed, released, and activated states separately. A portable compiler preview cannot advertise unfinished protected-host guarantees.

## 7. Verification and planning-task record

The original planning baseline below now passes; current acceptance records the actual offline commands and host environments. The planning-task observations following it remain historical:

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
cargo test --workspace --doc --locked
cargo build --release --workspace --locked
```

Add milestone-specific conformance, generated-consumer, fuzz/property, Linux permission/crash, scientific interoperability, package-installation, and benchmark checks. Run required host/feature profiles explicitly; do not replace real permission acceptance with a broad unit-test count. `--locked` preserves dependency resolution, not a claim of identical binary bytes across builds. [Cargo test documentation](https://doc.rust-lang.org/cargo/commands/cargo-test.html).

Keep the conformance manifest stable and store each run separately under `docs/acceptance/` with revision, environment, exact commands, passes/failures/skips, raw report references, and unresolved differences. Do not grow this plan into a test transcript or rewrite preserved reference failures.

Actual checks performed for this planning task, in the local MetaMap checkout:

```sh
npm run typecheck
npm test -- src/__tests__/canonical.test.ts src/__tests__/graph.test.ts src/__tests__/composer.test.ts src/__tests__/derivation.test.ts src/__tests__/uncertainty.test.ts src/__tests__/risk.test.ts src/__tests__/semantic-projection.test.ts src/__tests__/consumer-bindings.test.ts
```

Documentation QA also passed: `git diff --check`, Prettier checking of `BUILD_PLAN.md`, and a structural/reference check covering local links, pinned source paths, R0–R11 headings, and all 37 unchecked work items.

Both source checks exited 0; **131 tests / 8 files passed**. Repository intake and `git status --short` confirmed both repositories were initially clean; the reference remained clean after those checks. The engine-to-record diff confirmed only `BUILD_PLAN.md` changed between the pinned reference revisions. Full reference CI, package/release checks, scientific interoperability, protected Linux acceptance, and every future Rust command above were **not run** as part of this planning task.

## 8. Delivered implementation and adoption decisions

The first package delivered **R0 plus the smallest complete R1/R2 path**, with initial R3 capture, replay, stable-ID/source comparison and declared impact paths. Subsequent packages completed R4–R11. Verification records bind the uncommitted candidate to source inventories and Rust executor source identities; the initial Git HEAD does not identify the new implementation.

The declared profiles now pass native implementation, two separately staged Rust consumer migrations, Linux permission/crash/lifecycle acceptance and source/native installation on both advertised targets. Interactive debugger observations are recorded at their historical tested source identity; the renderer bytes remain unchanged. Naming/public contract adoption, public publication and production trust/bootstrap/activation remain user decisions. Additional platforms and broader scientific formats require their own acceptance; this completion does not expand the declared draft profiles.

Portable inputs compile without Node, both native consumers execute correctly, and malformed/ambiguous/unauthorized-ownership controls reject. The protected host is separately verified under R6/R7. The draft bundles contain no unattended privileged installer.

Defaults chosen by this plan are an indexed in-memory Rust kernel, portable JSON/JCS inputs, static native outputs, optional external adapters, semantic compatibility with explicit legacy conversion, and the root-owned Linux activator profile. Patamaps is the chosen name; the shared-profile manifest, limits, pinned dependency/toolchain versions and host trust-administration protocol are implemented. Public contract adoption and publication remain separate actions.
