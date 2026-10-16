# General project adoption build plan

Status: active. Owner authorization: create and pursue on Intel with regular commits and pushes.
Baseline: 591e313cc770ab256a045e4e101a6a2358262b1f. The completed cross-stack M0–M7/X01–X20 plan and receipts remain historical, unchanged.
Scope: usable, explicitly bounded Next.js/Rust project integration beyond the catalog fixture. Completion requires independent existing-project evidence, not another invented example.

## Authority and exclusions

Rust owns parsing, validation, admission, capture/replay and emission. Reuse existing workspace/process providers, graph laws, checked projections, candidate publication and package contracts. Owner profiles declare semantic correspondences and intent; discovery never invents business meaning. Do not replace the kernel, introduce a parallel graph framework or infer arbitrary macro/shell effects.
All heavy execution uses Intel's existing shared storage supervisor, its 4 GB growth / 500 MB reserve / 100 GB retention policy and retained outputs. Wait for another project's lease; do not interrupt it or use another runtime/VM. No deletions, production deployment, registry publication, secrets ingestion or trust activation. Keep regular verified commits and Rory pushes; no history rewrite.

## Milestones and observable acceptance

| Stage | Deliverable | Acceptance / negative controls |
| --- | --- | --- |
| G0 | Inventory, fixed baseline, qualification selection and this plan | Record real project provenance and constraints; read applicable instructions; distinguish working modifications from Git commit. Preserve prior accepted profile. |
| G1 | Native project onboarding profile and explicit nonsecret input capture | Arbitrary owner-relative layout; named components/contexts; explicit input allowlist; bounded native strict JSON; unknown keys/path escapes/symlinks/duplicate identities/secret-file selection refuse. Secret references remain unresolved labels and never read environment/files. Deterministic content receipt with stated non-admission status. Replay verifies exact inputs without source/tool access. Actual Wargame and independently structured Seeder input captures; no source mutations. |
| G2 | General HTTP contract profile and framework bridges | Extend native HTTP emitter with bounded nested objects, optional fields, arrays, booleans, numeric bounds, enums, supported methods and path/query/header parameters. Explicit versioned schema subset, no silent ignored keywords. Axum integration through real stateful async handler signatures/extractors; explicit operation discrimination, owner-declared envelopes and conditional proxies. Preserve domain command identities separately from transport operation identities when one request contains multiple domain commands. Rust/TS compile plus real HTTP positive and independently frozen invalid cases; retain old string-object profile. No arbitrary Serde/macro equivalence claim. |
| G3 | Configurable Next/Cargo observations | Owner-selected Next roots/config and workspace manifests/lockfiles/targets/features/platform. Support explicit isolated standalone package roots as well as reviewed Cargo globs/config subset with exact captured enumeration and ambiguity refusals. Route groups/dynamic routes plus explicit rewrites/proxy/environment/Server Action boundaries. Use real project cases, not filename evidence as runtime proof. Omitted inputs/config/feature/route mutation controls. |
| G4 | Portable retained development workflow | Reusable commands outside examples; explicit executable argv/cwd/environment references, readiness/HTTP checks, exact output selection and source/tool lineage. Preserve previous selection on failed/raced/cancelled build, foreground watch and parent death. Measure cold/warm edit latency, memory units and retained disk on actual project sizes. No-op reports verification not repeated; no invented cache hits or speed claim. |
| G5 | Deployment contexts and installed consumers | Owner-selected Dockerfile/context/stage/Cargo target/profile/platform with bounded static observations plus actual Linux builds, artifact/image/config/listener/HTTP/browser evidence. Wrong binary/config/arch/listener/stale generated contract refuse. Safe nonsecret config projections must be captured as independently declared inputs; raw secret-bearing files never enter capture. Fresh exact installed source/native package repeats usable workflow without example-script copying or graph compiler on request paths. |
| G6 | Independent qualification and release decision | Retained candidates from existing Wargame (Next + Axum + nested domain types) and a differently structured project (Seeder Next monorepo, plus independent Rust project if needed). Record source commit AND exact selected working bytes; no unrelated app changes. Real native builds, generated contracts, runtime calls and browser controls; existing app tests through their mandated guards. Independent expected failures, replay after source/tools unavailable, installed consumer and previous fixture regressions. Publish scoped support matrix with passed/failed/unavailable states. |

Dependencies: G1 before reusable capture/configuration; G2/G3 before G4 general runtime; G4 before G5 installed/release; G6 runs incrementally but acceptance requires all preceding required controls. Do not call G1 source capture complete workflow acceptance.

## Qualification intake (initial read-only observations)

- Wargame: /Volumes/dev_src_case_sensitive/projects/wargame, HEAD cf4e0de9dcd7c87ccf32f6f40adb662078e45d13. Existing working changes include README, VERIFICATION, build status, managed-browser harness, storage policy and independent Linux evidence. Preserve them. Rust root package wargame-workbench, Axum 0.8, Serde/schemars/sqlx/tokio; Next 16.4.1 under web, Node >=24 <25. Existing Metamap compiler must remain unchanged; generated contract aliases share one atomic bundle pointer. Its AGENTS mandates its own guarded npm verification and distinguishes synthetic from empirical acceptance.
- Seeder: /Volumes/dev_src_case_sensitive/projects/seeder, HEAD c61d51a57120abbbca65d4cb4a432c1cef9343bb. Next ^16.0.0 under packages/web and optional ad-platform-web, root npm workspace. Full instructions and current worktree must be reviewed before anything beyond read-only selected-input observation.
- Initial selection is a proposal based on existing implementation. Actual qualification must disclose missing prerequisites and may add a suitable independent Rust consumer. Do not weaken requirements to turn a capture into a runtime pass.

## Evidence and commit policy

Each stage records exact source/tool identities, commands, outcome, retained path and explicit unrun controls. Negative tests are frozen before repairing their target behavior. Do not rewrite historical failed receipts. Commit plan first, then small verified implementation milestones and their evidence; push after verifying origin, authenticated Rory identity and all new author/committer metadata. Full Linux/image/browser checks use required CI lanes when native prerequisites are absent. Record progress and handoff without declaring incomplete stages accepted.

## Implementation-driven qualification requirements

Read-only inspection of existing Wargame source adds concrete G2/G6 controls. Its Next web/src/app/api/evaluate/route.ts forwards a body containing expected_report to Rust /replay and other bodies to /evaluate, with a 1 MiB proxy limit. Rust api.rs uses stateful async handlers and DefaultBodyLimit::max(1024 * 1024). Existing domain Move/Hold/Resupply identities share /api/evaluate, and EvaluateRequest contains an array of potentially heterogeneous orders. Therefore domain commands are not interchangeable with whole HTTP transport operations. Owner declarations must retain both layers, explicit envelopes and proxy conditions. Preserve the existing command URNs and compiler; do not fabricate a separate single-command API or treat a duplicated route allowance as proof.

Required positive/negative qualification includes actual evaluation and replay through the same Next route, direct Rust and proxy body-limit boundaries, nested/discriminated order DTOs and wrong-proxy-branch controls. The initial finite JSON DTO emission in decision0032 retains the old synchronous POST/8 KiB dispatch boundary and is a partial G2 implementation, not completion of these application requirements.
## Scoped transport checkpoint

Source 1588a3c passed all four jobs in CI38843082846. The [47-control receipt](../acceptance/project-adoption/g2-http-transport-1588a3c/receipt.json) verifies the controlled async Axum consumer and Node proxy on Linux x86_64, including typed and wire refusals. This advances G2; it does not complete G2 or G6. Existing Wargame generated schemas additionally require explicit UUID, safe numeric interoperability for uint64, and its decimal quantity string pattern. Transport-specific parser support and frozen scalar controls passed all four CI38845561544 jobs at5880cbe. The [86-control receipt](../acceptance/project-adoption/g2-http-transport-5880cbe/receipt.json) retains exact scope, including 31 HTTP exchanges and 45 client controls. JSON-2 refusals remain unchanged. This does not yet establish existing-project compatibility. G1 native existing-project capture and standalone Cargo checks still await the shared Intel lease. G3–G6 remain active.

## Cargo member expansion checkpoint

Decision0034 implements explicit workspaceMembers: bounded-directory-globs while retaining literal-paths as default. One complete star directory segment is supported with exact captured manifest enumeration, pre/post metadata comparison and actual Cargo member confirmation. The existing source discovery driver now includes frozen default/missing-input/syntax/symlink/mutation refusals and replays a glob-backed workspace with source/tools unavailable. CI38847576022 at63abaed passed all four jobs; its explicit discovery phase retained 31 controls/80 commands, including nine G3 cases and glob-backed source/tool-unavailable replay. The [scoped Cargo receipt](../acceptance/project-adoption/g3-cargo-members-63abaed/receipt.json) excludes fixture compilation and real-project acceptance. Cargo exclusions and broader glob grammar, other config contexts and real-project qualification remain open.

## Retained staging checkpoint

Decision0035 adds native project-stage from the existing verified ProjectCapture into a fresh descriptor-relative directory. It reconstructs only selected UTF-8 bytes with non-executable private files; it does not restore metadata, dependencies or establish a complete build context. Capture/record/prefix validation precedes destination creation, existing destinations refuse, and partial outputs are preserved. Three filesystem controls cover source-unavailable recapture, no-overwrite/symlink handling, and tamper/prefix refusals. Existing-project input qualification and private Wargame preparation now exercise the native staging API. The [scoped staging receipt](../acceptance/project-adoption/g4-project-stage-61d8c11/receipt.json) records all-four-job success at61d8c11, with three CLI controls and workspace tests; real-project staging is still queued. The stdout-only CLI refinement atd11a78c passed its dedicated phase, with full workflow still pending at observation. G4 orchestration/readiness/watch/cancellation/performance and G5–G6 remain open.

## Literal Cargo exclusion checkpoint

The native Cargo provider implements a separate workspaceExclusions: literal-paths opt-in alongside bounded-directory-globs. It retains default refusal, records exact excluded matches, rechecks their inventory, rejects ambiguous overlaps/symlinks and still requires captured manifests for selected path dependencies. New frozen controls cover an uncaptured malformed excluded manifest, included/excluded dependency closure, unsupported declarations and post-metadata exclusion membership mutation. Native formatting/Python AST checks passed; compilation and runtime verification remain pending. The accepted63abaed receipt predates this extension.

## Workspace framework emission checkpoint

Decision0036 extends the existing WorkspaceConfig language enum with http-client and axum-witness, using checked projections and the same output/baseline reconstruction path as existing formats. HTTP bindingSlot overrides refuse. The controlled transport consumer now compiles and runs workspace-derived bytes; new controls cover direct composed-graph consistency, source-free baseline replay and rehashed output tampering. Formatting/syntax checks are available before CI; current-source runtime acceptance is pending. This does not replace real-project qualification or the remaining G4–G6 orchestration/deployment work.

## Actual schema qualification findings

The first native Intel run completed with a refused aggregate because workspace-emission source files changed during execution; preserve that run and rerun from a fixed source. Individual Wargame/Seeder selected-input capture/stage/recapture and standalone Wargame Cargo metadata commands passed. Wargame logistics client emission refused the schema profile. Static inspection estimates 813 root visitor calls versus2242 after redundant definition revalidation. The parser now skips only independent revalidation of definitions already fully checked, retaining the2048 visitor/depth bounds, all root expansion and unused-definition checks. Boundary controls preserve22 repeated subobjects at exactly2048 visits and reject23. Actual native acceptance remains pending. The actual Quantity schema also has maxLength20 and documents a native u64 domain cap; generic large decimal-string conformance is not proof of arbitrary-size Wargame quantities.

## Fixed-source Intel and CI checkpoint (2026-10-16)

Source383d0c5 completed all11 native commands with unchanged tracked bytes and HEAD: formatting, locked offline CLI build, engine identity, schema/discovery unit tests, actual Wargame and Seeder capture/stage/replay controls, Wargame transport preparation, standalone Cargo observation,49 discovery controls,90 controlled transport controls and focused all-target Clippy. The [native receipt](../acceptance/project-adoption/native-fixed-383d0c5/receipt.json) supersedes the pending native statements above; the earlier refused aggregate remains retained. Actual Wargame logistics emission now succeeds, but emitted client/witness preparation is not application compilation or Serde equivalence.

All four jobs passed CI38853067005 at2a9a22f and CI38853947079 at383d0c5. API artifact digests were verified before inspecting receipts. The [literal-exclusion receipt](../acceptance/project-adoption/g3-literal-exclusions-2a9a22f/receipt.json) records49 discovery controls including15 new exclusion cases; the initial failing test fixture and subsequent correction remain in history. The [workspace HTTP receipt](../acceptance/project-adoption/g4-workspace-http-383d0c5/receipt.json) records90 controlled consumer cases including four workspace emission/replay/tamper controls. Earlier pending CI statements above are historical.

Remaining acceptance is unchanged: broader Next/Cargo configuration and actual route behavior, generic execution/readiness/selection/watch and failure controls, measured actual-project performance, deployment/installed consumers, and real application qualification. Intel Node24 is available. Wargame currently retains its own300MB run-growth policy; do not substitute Patamaps4GB policy or another project temporary limit. Full Wargame qualification must preserve its original compiler, use retained candidates and mandated guards, and regenerate changed native engine evidence. G2–G6 remain incomplete.

## Retained output and actual candidate checkpoint (2026-10-16)

Decision0037 adds native workspace-stage from a verified baseline into a fresh directory. It reuses the descriptor-relative project writer, refuses conflicting paths before creation, and never executes tools or publishes a selection. Full native workspace regressions and93 controlled transport cases passed, including source-free CLI staging, existing-destination refusal and rehashed-output refusal; the compiled runtime consumer uses staged bytes. See [staging receipt](../acceptance/project-adoption/g4-workspace-output-staging-20261016/receipt.json). Generic execution/readiness/selection/watch and actual performance remain open.

A retained actual Wargame candidate preserves13,217 ordinary files (2,517,774,073 logical bytes) and three internal symlinks using verified native clones. Only the candidate API receives the generated witness include. The original source is unchanged by this work. The first attempted build exposed enclosing Cargo workspace inheritance; relocating the candidate outside Patamaps fixed that without editing Cargo.toml. Locked target-specific fetch then resolved the missing native dependency cache without lockfile changes. Native evidence compilation subsequently stopped at the application's unchanged300MB growth limit. Candidate-only4GB proposal awaits owner approval; the original application's policy remains unchanged. The [candidate receipt](../acceptance/project-adoption/wargame-retained-candidate-20261016/receipt.json) preserves failures and explicit unrun application/Next acceptance. No full application pass is claimed.

The generated actual-schema Wargame client subsequently passed strict standalone TypeScript checking with the existing application compiler under its unchanged300MB guard. The [typed-client receipt](../acceptance/project-adoption/wargame-retained-candidate-20261016/typescript-receipt.json) binds compiler/runtime/client bytes. This is neither Next application compilation nor runtime/Serde qualification.

## Existing Next source observation checkpoint (2026-10-16)

The reusable scripts/project_next_qualification.py driver accepts explicit owner input profiles, arbitrary App Router roots, tool paths and optional exact observed endpoint requirements. Rust captures/stages explicit nonsecret bytes and verifies composition/replay; the existing pinned Next AST adapter supplies structural facts. The [guide](../guides/selected-next-observations.md) defines the bounded workflow.

The [two-project receipt](../acceptance/project-adoption/next-existing-projects-20261016/receipt.json) records stable original HEAD/status and selected bytes in Wargame7058bbb4 and Seederc61d51a5. Wargame selected14 inputs/12 special files and observed8 endpoints, with exact POST /api/evaluate and POST /api/logistics expectations. Seeder selected53 inputs/50 special files from packages/web/src/app and observed7 endpoints,40 pages and3 dynamic segments. Both refused a missing declared selected input and replayed after configured staged source/tool paths were renamed, with external PATH empty. The prior Wargame attempt refused its aggregate because another process committed the original repository during qualification; preserve that failure rather than weaken the stable-HEAD requirement. Private source and schema payloads remain on Intel.

This advances source observations in G3. It does not qualify Next configuration interpretation, rewrites, Server Actions, proxy/runtime behavior, complete imports or application builds. Actual route groups were not exercised by these captures. G3–G6 remain incomplete. Separately, all four CI38857902614 jobs passed at3de6175; its verified67403-byte diagnostics archive contains93 controlled transport cases, including native output staging.

## Explicit native development command checkpoint (2026-10-16)

Decision0038 introduces typed project-exec over the existing ProjectCapture and Invocation contracts. Rust validates selected source bytes, captured helper declarations, cwd and environment references; executes through the existing private process supervisor; then recaptures selected inputs and rehashes the executable target. It preserves configured executable paths/argv[0] for aliases, including Rust tool shims. Normal nonzero exit, input mutation or executable mutation produces a refusal report with actual completion diagnostics. Source/program changes remain retained.

The [native command receipt](../acceptance/project-adoption/g4-native-project-command-20261016/receipt.json) records full workspace tests and13 supervised CLI cases: captured-only environment, nonzero diagnostics, source/tool changes, directory/environment/helper refusals, timeout/output bounds, binary diagnostics, executable alias/Cargo dispatch, and ordinary descendant stopping after CLI SIGKILL. Discovery retains its60-second ceiling; project commands have a separate explicit24-hour ceiling. The unchanged shared executor implementation also passed49 discovery/93 transport regressions before the isolated alias refinement. CI is pending after push.

This is a G4 execution primitive, not the complete development workflow. It does not establish readiness, HTTP checks, coherent exact output selection, previous-selection protection across a full failed/raced/cancelled build, no-op/watch orchestration, complete dependency/context closure or actual-project performance. Timeout/pipe-bound aborts do not yet establish complete partial program log retention. Required application/storage guards still apply. Secret/ambient environment forwarding is not implemented. The independent Wargame candidate policy request remains pending and was not applied.

## Native retained build workflow checkpoint (2026-10-16)

Decision0039 and the [guide](../guides/retained-project-builds.md) add project-build/project-build-verify outside the example driver. An explicit owner plan composes existing input capture, viable workspace admission/emission, native build/verification commands and exact declared file/tree artifact snapshots. State is isolated from source/enclosing Cargo workspaces. Fresh attempts retain all inputs/records; atomic selection keeps the previous pointer history. No-op reports command verification not repeated and zero cache hits.

The [native workflow receipt](../acceptance/project-adoption/g4-retained-project-build-20261016/receipt.json) records21 workspace integration tests and12 supervised workflow controls: selection/no-op, command failure, rejected admission before commands, artifact mutation, live lock contention, SIGINT/SIGTERM/SIGKILL with ordinary child stopping and previous-pointer preservation, mode-bit tampering, source-unavailable binding verification and state relocation. Rust tests also cover source/tool races, forced rebuild history and rehashed contradictory command evidence. Initial four binding failures were caused by numeric representation comparisons after strict JCS parsing; canonical/numeric comparison fixed them without weakening checksum or binding requirements. The unchanged implementation passed13 command,49 discovery and93 transport regressions and Clippy.

The previous command primitive fe8bbb3 also passed all four CI38862268958 jobs; its small diagnostics artifact was API-digest verified and its13 command controls inspected. New retained-build CI is pending after push.

G4 still requires foreground watch, qualified readiness/HTTP semantics, complete applicable input/context/dependency treatment, actual-project performance and installed workflow. The text-capture/symlink/output metadata limits are explicit; controlled artifact checks are not real application acceptance. G3 Next configuration/rewrites/Server Actions and G5–G6 deployment/real qualification remain open. The separate Wargame candidate growth-limit proposal remains unapproved and unapplied.

## Foreground watch implementation sequence

Reuse the native retained build driver. First expose a read-only observation of its
exact input key, sharing capture/plan/tool/engine binding code with actual builds.
Then add a foreground controller outside examples that debounces declared changes
and acquires the existing storage supervisor only for each attempted update. Idle
polling must not hold the shared build lease. A failed key must not spin or silently
bypass a capacity refusal. Existing selected artifacts remain available on failure.

Acceptance requires actual supervised Intel controls for edits, unchanged polls,
rapid edits, failed-key suppression, source/tool changes, concurrent contenders,
SIGINT/SIGTERM/SIGKILL and parent death with ordinary descendants stopped. Preserve
all attempts and diagnostics. Stub runners may test routing but do not establish
Intel supervisor acceptance. Read-only observation is not admission or an atomic
filesystem snapshot; the native build rechecks lineage before publication. The
observation primitive alone does not complete G4 foreground watch.

The first watch prerequisite is implemented as native project-build-input-key.
It shares exact source/plan/tool/engine binding construction with project-build,
creates no build state and executes no configured commands. Native verification
passed22 workspace integration tests, CLI compilation, focused all-target Clippy,
and13 supervised build workflow controls. The new control checks read-only
observation, equality with the selected build key and changed selected bytes.
See [scoped receipt](../acceptance/project-adoption/g4-build-input-observation-20261016/receipt.json).
CI for this addition is pending after push. The foreground controller remains open.

## Foreground watch checkpoint (2026-10-16)

Decision0040 and scripts/project_watch.py add a generic foreground controller over
the native key/build/selection verifier. Idle polling owns no allocating lease;
each update uses the explicit policy runner. Failed keys, including exit75, are
suppressed until a declared change or explicit restart. A zero runner exit alone
cannot claim success: native selected bindings and the current declared key must
match. No-op still does not repeat runtime verification.

The [scoped native receipt](../acceptance/project-adoption/g4-foreground-watch-20261016/receipt.json)
records10 final controls with fixed controller/CLI bytes: initial selection,
debounced edits/idle, failure suppression, native no-op recovery, live policy
contention, SIGINT/SIGTERM/SIGKILL, actual watcher-parent death, abrupt runner death
and refusal of a runner that skipped the build. Ordinary descendants stopped and
the previous selection survived cancellation/failure. Separate actual Intel
supervisor recovery after runner SIGKILL passed with a new selected generation.
Preflight controls refuse inherited heavy leases and Intel invocation of the
isolated CI fixture. Initial parser and cleanup-observation failures are retained.

The existing isolated Linux source lane now runs the same lifecycle controls with
a clearly identified kernel-lock runner fixture and retained diagnostic records.
That does not replace actual Intel policy qualification. New CI remains pending
after push. All four prior CI jobs passed at46633a3 (38869068173) and a84219c
(38870247865); both small diagnostics archives were API-size/digest verified and
their 12/13 build controls inspected.

G4 remains incomplete: actual-project watch/tool-edit qualification,
readiness/HTTP semantics, complete applicable contexts/dependencies, measured
cold/warm memory/disk behavior and installed workflow. G3 configuration and
G5–G6 actual application/deployment acceptance remain open. The Wargame
candidate-only growth proposal remains unanswered/unapplied.

## Existing application command checkpoint (2026-10-16)

All four CI 38872872081 jobs passed at f2bdeb8. Its 103465-byte source diagnostics
artifact 12034098698 was API-size/SHA256 verified; the actual 10 watch, 13 retained
build, 13 command and 93 controlled transport receipts were inspected. The native
Intel policy evidence remains separate from CI's controlled runner fixture.

A retained existing Avaelus/Seeder c61d51a5 context now preserves 176267 ordinary
files and 172 internal links, 1604205946 logical bytes, using verified native clones.
Raw environment files/private-key suffixes and the exact unavailable root .meta
development-tools link are excluded; the original link and checkout remain.
All selected source/destination hashes, modes, link targets and source membership
passed. Source HEAD/status remained unchanged.

The unchanged default Next 16.1.6 Turbopack build passed on the retained candidate
through Seeder's actual Intel launcher. Its configuration skips type validation,
so a separate TypeScript 5.9.3 --noEmit check was run and passed. The subsequent
native project-capture/project-exec qualification bound 878 text inputs and
captured nonsecret environment references, with a captured owner helper checking
framework entrypoint hashes. Actual Next build and TypeScript commands passed;
input capture verification also passed with candidate source/configured program
paths unavailable and external PATH empty. Next-generated next-env.d.ts and the
added helper are identified separately from original source. The initial wrong
component-kind profile refusal remains retained; the profile was corrected to
existing next-app/configuration without changing the native parser.

The [scoped real-project record](../acceptance/project-adoption/seeder-actual-next-commands-20261016/receipt.json)
does not qualify a Patamaps generated-contract replacement, full dependency
closure, native retained-build reconstruction/selection, actual app watch,
HTTP/browser behavior or deployment. Installed dependencies remain separately
retained, outside native UTF8 capture. Whole baseline Next output is retained
before the native command builds a fresh output. Timing/RSS observations are
scoped measurements, not a paired cold/warm benchmark or performance advantage.

Next independent implementation should use these actual compiled Next manifests
to resolve G3 configuration/route observations, and integrate generated contracts
and real runtime checks. Keep G4 context/artifact/readiness/performance and G5–G6
acceptance intact; do not substitute successful original app commands for those
remaining requirements. Wargame's separate policy proposal remains unapplied.

## Compiled Next observation checkpoint (2026-10-16)

Decision0041 adds native next-build discovery over exactly three reviewed nonsecret
captured inputs: App Router routes-manifest version 3, compiled module aliases and a separate
typed configuration projection. It preserves route/rule conditions and array
indexes, public environment declarations, unresolved secret labels and opaque
RSC protocol metadata. Cross-document digests/basePath must agree. Config, regex,
HTTP and secret references are never executed/resolved. Receipt/version metadata
remains declared data, not authenticated build evidence.

The [scoped record](../acceptance/project-adoption/g3-next-compiled-20261016/receipt.json)
records three native unit tests with 16 frozen malformed cases, six CLI controls,
final package tests/Clippy, existing discovery regressions and an earlier full
Rust workspace pass before an equivalent Clippy style correction. Final Rust
implementation hashes match package tests and all subsequent controls.

Actual retained Avaelus/Seeder artifacts matched 43 static routes, 3 dynamic routes,
46 module aliases and the compiled redirect, including reviewed public config.
Missing projection input refused. Baseline replay passed after copied source and
configured provider paths were renamed unavailable, with PATH empty. Raw
required-server configuration and server-reference encryption material were not
captured. The original source HEAD/status remains unchanged.

All four prior CI 38877500148 jobs passed at 4128ea9; its 103578-byte diagnostics
artifact 12036093112 was API-size/SHA256 verified. Actual 10 watch/13 build/13 command/
93 transport receipts were inspected. New feature CI is pending after push.

G3 remains incomplete for broader configuration/versions, actual nonempty rewrite/
proxy behavior and Server Action handlers. The actual case has empty rewrite
lists; controlled rule records do not establish HTTP semantics. G4 context/
artifact/readiness/watch/performance and G5–G6 actual generated-contract/runtime/
installed/deployment requirements remain required. Wargame policy remains unchanged.

## Retained context primitive checkpoint
The opt-in [retained context API](../guides/retained-contexts.md) captures binary bytes, permission bits, explicit directories and closed relative links without weakening the old text profile. Native package tests, Clippy and five CLI controls pass. The actual selected Next project context captured 1,604,201,589 bytes across 195,911 entries in 538.121 seconds; the [scoped receipt](../acceptance/project-adoption/g4-retained-context-2026-10-16/receipt.json) deliberately leaves large offline reconstruction, application build and native project-build integration pending. These primitives advance G4 but do not complete portable workflow or G6 qualification.

## Actual context reconstruction and build checkpoint
The [real-project receipt](../acceptance/project-adoption/g4-retained-context-2026-10-16/real-next-reconstruction.json) records source-unavailable verification/reconstruction and independent full tree checks: 176,266 files, 19,473 directories and 172 links, totaling 1,604,201,589 file bytes. Next build and separate TypeScript checking passed on the reconstructed candidate while the previous candidate path was unavailable. All captured inputs remained unchanged and new paths stayed within the declared Next output and TypeScript cache locations. Original source Git HEAD/status stayed unchanged. The first wrapper-cleanup failure and its output are retained; it is not reclassified as success.

Next G4 work must connect these existing context contracts to the existing native build driver: bind the declared snapshot digest into input keys, materialize a fresh candidate, explicitly bind any source/generated overlays and allowed writes, retain context metadata for source-free selected-build verification, and carry the binding through watch. Corruption, changed dependency bytes, unsafe overlays, raced updates and failed commands must preserve the previous selection. Then qualify the actual Next project through that native command, followed by generated-contract/runtime and installed-consumer controls. Do not substitute the successful qualification driver or a new parallel build framework for this integration.

## Native context binding implementation checkpoint
Native project-build now has an opt-in explicit sealed context binding while preserving the existing plan type and legacy Rust entry points. Context metadata, preimage-bound selected/generated overlays, declared new write roots and selected immutable context verification reuse the existing materializer and build publication path. Input-key observation binds the declared reference and does not claim fresh snapshot-byte verification. Dependency changes require a new captured context reference. Native package tests, 10 CLI controls and the 13-control context-backed foreground watch suite passed; see the [scoped receipt](../acceptance/project-adoption/g4-native-context-binding-2026-10-16/receipt.json). Actual large-project native builds, practical edit latency, generated contracts, runtime and installed qualification remain required. See the [binding guide](../guides/retained-contexts.md).

## Actual native Next workflow checkpoint
The [native real-project receipt](../acceptance/project-adoption/g4-native-next-2026-10-16/receipt.json) proves the d0bee34 native context workflow on the retained existing Next project: Next build, separate TypeScript check, fresh exact compiled-manifest witness, immutable source/tool bindings, selected artifacts, source/snapshot-free replay and no-op pointer preservation. Original checkout and all temporary source/snapshot renames were preserved/restored. The debug native build took 1,111.787 seconds while Next itself took 17.297 seconds; practical development-loop performance is not accepted. Release measurements and safe traversal work remain required before actual watch/readiness qualification. The selected generated observation model does not establish replacement of an existing application contract. G2/G3 remaining cases and G5/G6 runtime/deployment/installed/Rust requirements remain open.

## Closed context traversal checkpoint
Descriptor-relative closed-tree verification and copying retain complete hashes, permission and link checks, exact membership and visible inode/metadata checks while reducing repeated ancestor opens. The maximum-depth test passed under a 256-descriptor limit; 83 package tests, strict Clippy, five context CLI controls and ten native context-build controls passed. The [scoped receipt](../acceptance/project-adoption/g4-context-walk-2026-10-16/receipt.json) records independent verification/reconstruction of the actual 195,911-entry context with source unavailable and restored. The 614.495-second debug driver total includes independent Python checks and establishes no speed claim. Release/native watch latency and real generated-contract replacement remain required. Inspection of the actual owner generator identified legacy compileProjection as a compatibility gap to resolve using existing projection contracts.

## Next bounded G6 implementation: existing generated route contract

The retained existing owner generator imports the original v1 projection parser/compiler and consumes its selected subjects, endpoint and optional authorization slots to emit an existing TypeScript contract. Existing navigation consumers already import that contract. Inspection found legacy viability/semantic helpers and the native admitted-generation projection engine, but no exposed original v1 compileProjection equivalent in the current SDK. This is an identified integration gap, not evidence that native projection is absent.

1. Qualify release context verification and the same native Next build/replay/no-op workflow before accepting development-loop performance. Keep debug and release binaries pinned separately; report uncontrolled cache state and actual command times.
2. Add the smallest generic original-v1 projection compatibility bridge using existing legacy JSON, registry, validation, generation-address checking and deterministic ordering contracts. Preserve graph, mapping and subject identities and original v1 content addressing; do not pass a legacy observation off as native admission. Keep unsupported semantic/executable profiles explicitly refused until their real requirements are implemented.
3. Verify against the pinned original compiler with public controlled inputs: incoming/outgoing links, intersected subject selection, duplicate/missing slots, inactive/unknown mappings, stale generation, lossy edges, kind filtering, empty selections, deterministic ordering and digest mismatches. Exercise malformed schema and resource bounds through the existing transport. Add thin SDK parsing/compiler exports with the existing envelope, without embedding projection computation in JavaScript.
4. In an isolated private owner candidate, use Patamaps for graph compilation/projection and reuse the existing owner rendering and implementation-coverage logic. Preserve the original generator and checkout. Compare the existing generated API and consumer behavior; any semantic differences require explicit analysis rather than silently updating expectations.
5. Remove the old generated file from selected source inputs and declare its captured preimage as an explicit generated overlay. Run native project-build, actual Next build, TypeScript and existing consumer tests with the replacement. Corrupt or incompatible replacement and failed commands must preserve the previous selection. Then run the actual application/browser contract and installed-consumer workflow. Publish only scoped evidence, never private owner source or graph data.

Acceptance requires the real consumer using the replacement. A selected observation JSON, a dummy route API, a formatter-only equality check or an unconsumed emitted file is insufficient. G2/G3 broader cases and G5/deployment/real Rust qualification remain open independently.
