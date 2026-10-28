# General project adoption build plan

Status: active Intel adoption goal, continuing separately from the completed
C01–C19 capability milestone. The [integration backlog](integration-enhancement-backlog.md)
records current priorities and distinguishes verified results from open gates.
The owner’s scope correction makes this broader adoption work an enhancement to
the parity milestone; it does not cancel the separately authorized adoption goal.
Baseline: 591e313cc770ab256a045e4e101a6a2358262b1f. The completed cross-stack M0–M7/X01–X20 plan and receipts remain historical, unchanged.
Scope: usable, explicitly bounded Next.js/Rust project integration beyond the catalog fixture. Completion requires independent existing-project evidence, not another invented example.

Current evidence: [scoped support matrix](../guides/project-support-matrix.md). Open rows remain unverified adoption requirements; they do not block native capability completion.

## Authority and exclusions

Rust owns parsing, validation, admission, capture/replay and emission. Reuse existing workspace/process providers, graph laws, checked projections, candidate publication and package contracts. Owner profiles declare semantic correspondences and intent; discovery never invents business meaning. Do not replace the kernel, introduce a parallel graph framework or infer arbitrary macro/shell effects.
All heavy execution uses Intel's shared storage supervisor, its 4 GB growth / 500 MB reserve / 100 GB retention policy and retained outputs. Follow fair resource admission: verified managed jobs may share only when enforced reservations and output ownership fit; native work, benchmarks and uncertain ownership remain exclusive. Wait when admission is blocked; do not interrupt another project or use another runtime/VM. No deletion without separate exact-list approval, production deployment, registry publication, secrets ingestion or trust activation. Keep regular verified commits and Rory pushes; no history rewrite.

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

## Release verification measurement checkpoint
The optimized CLI built successfully under the unchanged Intel guard. Full-context verification of the actual 195,911-entry snapshot passed with source unavailable and restored: release-first 60.419 seconds, debug 112.594 seconds, repeat-release 22.769 seconds. All runs reported the same digest. Cache state was uncontrolled and no caches were cleared, so these observations do not isolate compiler-profile speedup. The [measurement record](../acceptance/project-adoption/g4-context-walk-2026-10-16/release-verification.json) makes no native-build, practical-watch or readiness claim. The actual release native build/replay/no-op qualification is the next required measurement.

## Actual release native Next workflow checkpoint
The [release record](../acceptance/project-adoption/g4-native-next-2026-10-16/release.json) passes the real native Next context workflow with the optimized traversal: build/verification 310.901 seconds, source/snapshot-free replay 26.098 seconds, no-op 27.852 seconds. Actual Next build took 18.678 seconds, TypeScript 16.489 seconds and the fresh compiled-manifest witness 0.110 seconds. Selected source/tool bindings stayed unchanged; no-op preserved selection with verification not repeated and cacheHits zero. Original Git HEAD/status and all temporary path renames were preserved/restored. Cache state was uncontrolled; the earlier debug run used the prior traversal, so no isolated compiler-profile speedup is established. Practical edit/watch readiness remains unaccepted. The existing generated application-contract replacement described above is the next functional milestone; runtime/browser, installed/deployment and actual Rust requirements remain open.

## Original v1 projection bridge checkpoint
The [compatibility bridge](../guides/legacy-projections.md) now validates/parses original v1 specifications and records and compiles bound graph/generation projections in Rust through the existing legacy transport. It preserves original identities/addresses, ordering, parser identity, immutable results and signed numeric facts. Shared existing SDK projection types are reused. All 66 pinned-original differential cases and their frozen Rust regression pass; the 115-test core package, strict core/CLI Clippy and full strict public TypeScript consumer check pass. Expansion, repeated large target metadata and output depth have refusal tests. The [scoped receipt](../acceptance/project-adoption/g6-v1-projection-2026-10-16/receipt.json) retains resource/profile limits and distinguishes the legacy observation from native admission. Actual owner generation/replacement, native emitted-contract build integration, runtime/browser, installed/deployment, broader framework and real Rust requirements remain open.

## Actual owner generator equivalence checkpoint
The [owner generator receipt](../acceptance/project-adoption/g6-owner-generator-2026-10-16/receipt.json) proves that the unchanged existing route generator, redirected through the pinned native SDK bridge in an isolated private candidate, emits TypeScript and generation/projection records byte-for-byte equal to both the original compiler and captured originals. The native trace includes generation and projection compilation; all 12 calls succeeded. Original Git HEAD/status and the complete retained context remain unchanged. Dependencies were read through an explicit retained-tree link: this prototype does not establish a portable dependency closure, native build integration, actual consumer/runtime/browser verification or installed/deployment acceptance. The emitted contract still needs integration into the native workflow, including changed-graph consumption and failed-preparation selection preservation.

The user separately approved raising only the retained Rust application candidate's growth limit from 300 MB to 4 GB. The exact saved proposal was verified against the prior policy and applied; reserve and retention limits are unchanged. The original checkout policy was not written. Native evidence qualification is resuming under that candidate's own guard; no result is inferred from the policy approval.

## Actual retained Rust candidate native checkpoint
The separately approved candidate-only 4 GB policy was exercised through that application's own supervisor. Native evidence passed 98 declared tests and revalidated 41 evidence inputs against their original inventory. Three generated module-local Axum handler witnesses compiled against the captured actual candidate API. The original provider prefix is unchanged; the candidate-only include hook is explicitly recorded. The [scoped record](../acceptance/project-adoption/g6-rust-native-candidate-2026-10-16/receipt.json) reports actual compiler defaults, unchanged policy, retained outputs and no application acceptance. Negative handler/return binding controls are prepared but their first launch was refused before startup for another live shared lease. They and actual Rust/Next runtime, domain payload, installed and deployment qualification remain required.

## Next integration contract: owner preparation before immutable candidate capture

Inspection of project_build.rs shows the candidate capture is currently frozen before build commands. The existing owner generator must run before this capture, with explicit declared output paths, without permitting a build command to alter selected source invisibly. Reuse the current project command, closed-context, attempt receipt and atomic selection mechanisms; preserve existing ProjectBuildPlan and legacy callers.

The next bounded implementation must bind preparation command/tool bytes, selected graph/policy/spec/renderer inputs and each existing context output preimage into the input key. Stage a fresh private candidate; execute trusted preparation commands; admit only declared generated outputs and retain their exact digests before freezing the candidate capture. Revalidate selected source, tools and context membership, then use the existing build/verification/publication path. Selection replay must verify retained preparation/output records without consulting original sources. Watch/input-key observation must include the preparation contract.

Observable acceptance: an actual owner graph edit changes the existing consumed route contract through the same native build; unchanged input takes the existing no-op path; invalid/stale graph, failed generation, undeclared writes, output corruption and raced updates preserve the previous selected pointer. TypeScript, actual Next build and existing consumers must use the regenerated module. The prior producer byte equality and pre-generated observations do not satisfy this step. Private source remains private. Runtime, installed/deployment and broader framework qualification remain independently required.

## Projection ordering regression checkpoint
The [scoped regression receipt](../acceptance/project-adoption/g6-projection-ordering-2026-10-16/receipt.json) records 116 core tests, strict core/CLI Clippy and all 68 original differential cases passing. Two distinct Unicode target IDs that collate equally now preserve original encounter order, checked in both directions and repeated 32 times per case. Existing frozen66 expectations are unchanged. Two malformed initial controls were retained as failures, corrected rather than accepted. Application integration requirements above remain open.

## Owner preparation implementation in progress
The opt-in preparation contract now has a candidate implementation in the existing
native build driver, CLI input observation and foreground watch. Generated output
preimages and commands contribute to the input key. Preparation command records
and generated selected bytes are retained for source-free replay. Preparation has
no build writable-path allowance; final undeclared changes must refuse before
build commands. Existing plan types and old Rust entry points are preserved.
Controlled preparation and watch cases are wired into the existing Linux source
qualification. This checkpoint is UNVERIFIED: Intel compilation, strict Clippy,
native controlled runs, watch and actual owner qualification have not run for
these source changes. The live shared Intel job prevents heavy verification;
no lease or policy bypass is authorized. Do not count implementation as acceptance.

Native Intel rustfmt parsed/formatted the changed Rust files and its check
passed; Python AST parsing and diff whitespace checks also pass. A draft branch
is being published for independent existing Linux CI while the Intel shared
heavy lease is occupied. This is not native compilation or application acceptance;
the full native suite and Rust candidate controls remain pending.

## Native owner preparation control checkpoint
The [scoped native receipt](../acceptance/project-adoption/g6-native-preparation-2026-10-16/receipt.json)
records passed native workspace tests, strict workspace/CLI Clippy, CLI build and
all existing build/context plus new preparation controls. Regenerated controlled
contracts are consumed by build verification; owner edits, no-op, failure/stale
preimage/unsafe output/undeclared write controls and source/snapshot-free replay
passed. These results supersede the earlier UNVERIFIED implementation checkpoint
only for their recorded scope. Actual owner generator integration and Next
application build/edit/failure, native watch, runtime and installed/deployment
requirements remain open. Draft PR #1 keeps main unchanged while Linux CI runs.

## Actual Rust handler rejection checkpoint
The [four retained-candidate type controls](../acceptance/project-adoption/g6-rust-native-candidate-2026-10-16/type-controls.json)
passed under the candidate's own unchanged approved policy: valid witnesses
compile, wrong handler and return bindings fail with their expected Rust type
errors, and restoring the valid witness compiles. The three captured actual lab
handlers are checked; source, native evidence and policy remain unchanged.
This closes the compile-time negative binding controls only. Runtime HTTP,
actual Next boundary, managed application paths and installed/deployment
qualification remain open.

## Linux preparation-aware watch checkpoint
All four implementation CI jobs passed. The [verified diagnostics record](../acceptance/project-adoption/g6-native-preparation-2026-10-16/linux-watch.json)
binds the artifact's API size/SHA-256 and actual controller/control hashes.
Its receipts contain 24 preparation and 15 foreground watch controls, including
consumed regenerated output and preparation-key failure suppression/recovery.
This is controlled Linux CI qualification. Native Intel watch performance and
actual application generator/build/edit/failure/runtime qualification remain open.

## Real owner closed-tooling context checkpoint
[Staging and capture](../acceptance/project-adoption/g6-owner-native-preparation-2026-10-16/context.json)
passed for the existing Next owner context: 195,999 entries and 1,674,434,053 file
bytes now include the pinned native compiler, SDK, relative loader and shim.
This removes the prototype's external dependency-tree link from the planned
native preparation workflow. The owner generator is unchanged. It has not yet
run in this workflow; actual build/edit/failure/runtime qualification remains open.
The optimized-driver build was refused before startup by another live shared
lease; its refusal and the finished capture are retained.

## Real owner native preparation baseline checkpoint
The [actual owner baseline](../acceptance/project-adoption/g6-owner-native-preparation-2026-10-16/baseline.json)
passed: the unchanged generator used captured Patamaps tooling in native
preparation, all three emitted artifacts were byte-identical to the captured
originals, and actual Next build, TypeScript and fresh manifest witness commands
passed. Source/snapshot-unavailable replay and native no-op preserved selection;
original Git state and pinned tools remained unchanged.

The optimized driver is recorded separately from the captured generation
compiler. Full build took 500.397 seconds, including owner generation 2.807,
Next 18.609, TypeScript 17.325 and manifest witness 0.125 seconds. Offline replay
took 31.823 seconds and no-op 34.716 seconds. Practical edit/watch latency is
not accepted. The actual owner edit/failure controls are prepared but their first
launch was refused before startup by another live shared lease. Runtime/browser,
installed/deployment and broader framework requirements remain open.

## Watch inspection budget checkpoint

The foreground controller accepts --inspection-timeout-ms (1000..3600000),
preserving its 30000 default for each native observation and selection check.
Real-project replay measured about32s overall; this motivates configurability,
not a claim that the 30s native watch verifier has demonstrably timed out.
Intel controlled subprocess deadline/protocol checks passed9 cases and existing
process-exit controls passed5; see [scoped receipt](../acceptance/project-adoption/g4-watch-inspection-budget-20261016/receipt.json).
Both native inspections still run; larger budgets do not admit mismatched keys.
Full native watch/application/performance qualification remains open. Existing
Linux watch CI now runs these budget controls; current-source CI is pending.

## Real owner edit checkpoint (2026-10-17)

The actual retained Next monorepo owner edit passed under the Intel supervisor:
a declared navigation-label edit changed the native input key, ran the unchanged
owner generator, passed Next build, TypeScript and fresh manifest witness, and
appeared in two selected compiled client JavaScript files. Native selected bindings
verified. Original Git state and pinned driver were unchanged. See the
[scoped positive edit receipt](../acceptance/project-adoption/g6-owner-native-preparation-2026-10-16/positive-edit.json).
The build took651.051s and subsequent selected-binding verification48.579s;
practical edit/watch performance remains unaccepted. The separately supervised
generation-failure control was refused before launch because another project
acquired the lease; no failure recovery pass is claimed. Browser/runtime,
installed/deployment and remaining G2-G6 gates stay open. Watch budget commit
d104864 passed all four CI38947765476 jobs; this evidence commit CI is pending.

## Real owner generation-failure recovery checkpoint (2026-10-17)

The separate supervised negative control passed: invalid owner graph generation
refused with PROJECT_BUILD_PREPARATION_COMMAND before any build step, the exact
selected pointer was preserved, and restoring valid input produced a no-op
with verification not repeated plus successful native selected-binding replay.
Original Git state and pinned driver were unchanged. See the
[scoped failure receipt](../acceptance/project-adoption/g6-owner-native-preparation-2026-10-16/generation-failure.json).
The first attempt refused an externally migrated symlink state root; its evidence
was preserved and the retry used the existing canonical directory with unchanged
acceptance checks. Invalid-generation control258.443s, restored no-op76.199s,
selected verification82.319s: practical performance remains unaccepted.
Actual Rust transport controls remain unrun while another job owns the lease;
no runtime, browser, installed/deployment or whole-goal completion is claimed.

## Real Rust router transport checkpoint (2026-10-17)

Four scoped native transport tests passed on the retained Wargame candidate under
its own supervisor: exact quantity encoding, actual router JSON/MIME/body errors,
evaluation/replay preservation, and frozen logistics metrics/native limits.
Cargo took129.469s; test bodies reported0.02s. The runner verified41 retained
native-evidence input digests and checked49 selected source/evidence/policy/scenario
digests unchanged. The prior98-test receipt was checked, not rerun. See the
[scoped transport receipt](../acceptance/project-adoption/g6-wargame-router-transport-2026-10-17/receipt.json).
The initial helper preflight expected a numeric test count; its preserved retry
reads the existing98-name array with the same exact count and input checks.
These are in-process Axum HTTP checks with a controlled generation label, not
TCP/Next proxy/generated-client/browser/deployment or managed admission evidence.
The actual owner edit and generation-failure recovery now also pass; practical
watch performance and all remaining G2-G6 requirements stay open. No completion
or activation is claimed. This evidence was published through GitHub after
Intel SSH and the mounted share became unavailable; Intel must synchronize it
when access returns. CI for this documentation/evidence commit is pending.

## Owner proxy-error profile checkpoint (2026-10-18)

Captured existing Next proxy source returns 503, while the prior transport profile
omits it. A separate owner revision declares observed 415/503 errors, preserving
the original profile and application. Native client/witness emission, strict
TypeScript compilation of both clients and five controlled client cases passed;
legacy undeclared 503 and malformed error bodies still refuse. See the
[scoped receipt](../acceptance/project-adoption/g2-owner-proxy-errors-2026-10-18/receipt.json).
On recheck, all generated outputs and 16 remaining inputs match; the pinned
emitter is absent from its recorded path, so emission rerun readiness is unproven.
No actual Next/Rust TCP runtime or new Rust-witness compilation is established
by these controls. A separate guarded production-listener qualification with 13
frozen cases is prepared but unrun while another job holds the shared lease.
G2-G6 requirements and whole-goal scope remain unchanged and incomplete.

## Real production Next/Rust network checkpoint (2026-10-18)

The [scoped production-network receipt](../acceptance/project-adoption/g6-wargame-production-network-2026-10-18/receipt.json)
records 13 frozen cases and 22 loopback HTTP exchanges passing against the retained
existing Wargame candidate. Fresh offline root/web installs, unchanged owner
generation of 294 artifacts, and actual production build passed under the
candidate's own approved guard. Real Rust evaluation/replay and frozen logistics
metrics match the production Next proxy; malformed/MIME/oversized/streamed bodies,
stale/tampered replay and declared-versus-legacy upstream503 controls pass.
All 71 selected source/tool/evidence/policy inputs remained unchanged, and the
owned service wrappers/listeners stopped. Owner generation took227.881s, build
182.838s, HTTP controls0.473s; these are functional observations, not accepted
performance measurements. This closes the prepared TCP/proxy control set only.
Browser, managed application paths, installed/deployment qualification, practical
watch performance and remaining G2-G6 scope stay open; the goal is incomplete.

## Installed source documentation checkpoint (2026-10-18)

Source packaging now includes the five development guides that were previously
omitted from exact source installations. The [archive receipt](../acceptance/project-adoption/g5-source-package-guides-2026-10-18/receipt.json)
records two byte-identical source/native archive pairs, verified inventory
identity and all five guide byte digests matching current source. The identified
release driver matches current native engine identities; this is not evidence
of independent binary reproducibility or a registry publication. Actual installed
existing-project workflow, browser/deployment and remaining G2-G6 gates stay open.

## Actual owner standalone browser checkpoint (2026-10-19)

The [scoped public-browser receipt](../acceptance/project-adoption/g6-owner-public-browser-2026-10-19/receipt.json)
records six real desktop/narrow public-route checks passing against the actual
retained Next16.1.6 standalone owner output. Native bindings verified before and
after; selection stayed unchanged, the bot-User-Agent403 remained enforced, and
no owned listener survived shutdown. Existing native Chrome155 and Playwright1.64
used fresh retained profiles. Source and generation compiler were absent from the
owned runtime tree, but OS-level source access denial was not tested.

Three earlier harness failures remain retained: next-start readiness on a
standalone build, the app's intentional Python-User-Agent403, and an incorrect
visible-navigation expectation at the narrow breakpoint. No app guard or source
was changed. The generated label remains hidden without authenticated permissions
and is explicitly not accepted by these public-route checks. Managed/backend,
installed workflow, Linux deployment and practical watch/performance gates remain.

## Exact existing-project context recovery checkpoint (2026-10-19)

The [scoped recovery receipt](../acceptance/project-adoption/g4-exact-context-recovery-2026-10-19/receipt.json)
records correct refusal of an old owner snapshot missing 107 data members, followed
by recovery into a new copy using only matching retained bytes. The installed
native CLI verified the unchanged original 195,999-entry context digest. No file
was deleted and the incomplete original stayed untouched. An initial permission
hypothesis was disproved: private blob modes are part of the snapshot format.
The installed workflow retry depends on this verified copy and still needs its
own staging, capture, actual build and replay evidence. Whole-goal scope is open.

## Additive Cargo segment-glob candidate (2026-10-19)

Decision0042 adds an opt-in bounded-segment-globs mode for an independently
observed upstream workspace: tokio-rs/axum at
fc78d5bcdb276bd6fb53cf2db55e91757eabb469 uses members=["axum","axum-*"].
The old whole-star mode and default literal refusals remain frozen. Existing
enumeration, captured-manifest, exclusion and pre/post-metadata contracts are
reused. Four new unit controls and five full-provider controls are defined.
This is UNVERIFIED implementation: no new Rust compilation, CLI execution or
actual upstream metadata pass is claimed. Native tests must wait for the shared
reservation; existing Linux CI may verify the draft independently. The queued
installed-owner workflow still uses its exact previously identified archive pair.

## Cargo segment provider verification checkpoint (2026-10-19)

The repaired candidate passed all four CI39264678054 jobs. Its tested PR merge
38107df7b3b8d8f1ed0eeaa25ddd438a67bbb006 has byte-identical native discovery,
unit-test and provider-control files to the current implementation. The API-digest
verified small diagnostics archive records all five new full-provider controls,
including old-mode refusal, exact expansion, missing capture, unsupported grammar
and post-metadata mutation refusal. See the [scoped receipt](../acceptance/project-adoption/g3-cargo-segment-cli-2026-10-19/receipt.json).
Independent pinned Axum source intake passed; actual metadata/refusal qualification
is queued. No upstream, target compilation or whole-goal pass follows from these
controlled results. The existing package's installed-owner build is independently
running and does not contain this newer discovery change.

## Actual installed-owner workflow checkpoint (2026-10-19)

The [exact installed-owner receipt](../acceptance/project-adoption/g5-installed-owner-2026-10-19/receipt.json)
records native generation by the unchanged real owner generator, actual Next
production build, TypeScript and fresh compiled-manifest checks. All14329 installed
source members and native/SDK bytes match the identified package; the selected
label reached compiled clientJavaScript. Build473.131s, offline selected replay32.169s,
no-op32.972s. Owner source, opaque snapshot and configured external native provider
were unavailable during replay and restored afterward. No-op preserved selection
and trace and reported verification not repeated/cacheHits0.

The first two staging failures remain retained. The successful fresh attempt used
exact recovered context bytes and all960 selected text inputs reconstructed by
native project-stage from the retained source-capture, including the missing lock.
The exact package predates Cargo segment-glob implementation; it is not installed
acceptance of the latest branch head. Authenticated/browser/Linux deployment,
runtime source/tool isolation and practical watch/performance gates remain open.

## Current package documentation closure checkpoint (2026-10-19)

The support guide exposed an omitted package dependency: docs/plans was absent.
The packager now includes those Markdown plans. The [current-package receipt](../acceptance/project-adoption/g5-current-package-links-2026-10-19/receipt.json)
records a fresh native release build240.588s and two byte-identical source/native
archive pairs. Six guides and the active plan match exact source bytes; their
local Markdown links resolve inside the source inventory. This package includes
the segment-glob implementation and its current workspace engine identity. The
previous release binary is retained. No deletion or policy change occurred.

The package is identified by its precise inventory/native/archive digests and
the recorded source revision plus packager working change. Fresh installed
application qualification for this exact package remains required; the older
installed-owner pass does not automatically transfer. Binary rebuild
reproducibility and whole-project deployment/performance acceptance remain open.

## Independent actual Cargo declared-workspace checkpoint (2026-10-19)

[Actual Axum partial evidence](../acceptance/project-adoption/g3-actual-axum-declared-2026-10-19/receipt.json)
binds exact upstreamfc78d5bcdb276bd6fb53cf2db55e91757eabb469, six unchanged
manifest/lock inputs, four real packages and six declared targets. The isolated
copy passed explicit expansion, legacy-mode/missing-member/missing-lock/wrong-tool
refusals, Clippy and CLI compilation. Darwin/Linux declared-local requests yielded
identical metadata; neither target compilation nor platform-filter behavior is
proved. Resolved default/disabled/axum-ws views were unavailable offline; the
overall run exited1 and remains incomplete. Direct Cargo diagnosis and conditional
locked dependency preparation are queued, followed by unchanged native controls.

The enclosing-workspace ambient-config refusal is preserved. It was addressed
by relocating only the retained copy outside Patamaps' toolchain ancestry, under
the same supervisor's monitored temporary prefix. The provider was not relaxed.
Fresh installed qualification for the current exact package has passed inventory,
context stage and capture; its actual build/replay/no-op phase remains queued.

## Current installed owner and resolved Cargo checkpoints (2026-10-19)

The [fresh current installed-owner receipt](../acceptance/project-adoption/g5-installed-current-owner-2026-10-19/receipt.json)
passed with nativec202611f: all14338 installedsource members verified; all447
packaged program inputs4216053bytes match the current checkout. Build475.080s,
selected offline replay50.512s, no-op34.602s. Actual owner generation/Next/TSC/
manifest witness, compiled marker, native compile/projection trace, unavailable
configured source/snapshot/provider replay and pointer/trace preservation passed.
The frozen archive predates later qualification docs, not the checked program
inputs. Linux/runtime isolation/authenticated browser and practical performance
remain required.

The [real Axum resolved receipt](../acceptance/project-adoption/g3-actual-axum-resolved-2026-10-19/receipt.json)
passed allnine scoped native controls after direct Cargo confirmed offlinecache
absence and lockedregistryfetch restored offline resolution. All source inputs/
lock/status unchanged. Native feature sets independently match raw Cargo nodes;
explicitaxum/ws addsws. No-default retains the same workspace feature set, so no
minimal-feature build is claimed. ResolvedLinux, actual mutation and baseline
replay controls remain open, as do compilation/runtime gates. Previous failed
and partial receipts stay historical.

## Actual Cargo Linux metadata, mutation and baseline replay (2026-10-19)

[Actual Axum follow-up](../acceptance/project-adoption/g3-actual-axum-replay-2026-10-19/receipt.json)
passed with installednativec202611f: resolvedLinux metadata, captured-manifest
mutation refusal, post-metadata member race refusal, a checked four-package JSON
inventory, baseline replay with configured provider/Cargo/rustc/source paths
unavailable and externalPATH empty, and rehashed-adapter-lineage refusal.
All moves restored; selected originalmanifest/lock hashes and Gitstatus unchanged.

The failed first profile omitted a required projection and remains failed. The
corrected profile selects only actualCargo package entities with zero relation
slots and empty business policy; it adds no unrelated fixture shard and does not
infer business viability or operational admission. Artifact bytes are published
for inspection. Metadata/replay is not target compilation, runtime or hermetic
source/dependency closure. Existing-project Linux deployment, framework/runtime
boundaries, managed application tests and practical watch/performance remain open.

## Pinned actual Rust Linux compilation gate (2026-10-19; pending execution)

The existing cross-stack source CI lane now additionally invokes
scripts/qualify_axum_linux.py against the actual MIT-licensed tokio-rs/axum
workspace at fc78d5bcdb276bd6fb53cf2db55e91757eabb469. This is a separate
qualification driver: the native metadata provider remains offline and never
claims compilation. The driver records full tracked-source inventories, exact
tool digests and host triple, prepares locked Linux registry dependencies, then
observes resolved metadata with axum/ws, builds all four observed workspace
libraries offline and runs their existing library tests offline. Artifact
digests, command outcomes and source stability are retained even on failure.
The new gate is unrun at this checkpoint; syntax checks are not acceptance.
It does not establish application HTTP deployment, a Linux Next build, complete
dependency hermeticity, image/browser acceptance or a release decision.

The [actual Linux build follow-up](../acceptance/project-adoption/g3-actual-axum-linux-build-2026-10-19/receipt.json)
passed in CI39296124316 at4f31b73 (tested merge847b0e7, identical tracked tree):
all four pinned Axum workspace libraries compiled, and459 upstream library tests
passed with zero failures/ignored tests. All505 tracked source hashes remained
unchanged. The metadata provider continued to report compilation false; separate
Cargo commands established this build/test result. Registry/cache closure,
retained-project-build orchestration, independently inspected binary architecture,
HTTP deployment, Next Linux/application/browser qualification and performance
acceptance remain open. Timings are observations, not a cold-build benchmark.

A follow-up CI refinement makes the Linux build/test target explicit, checks the
actual proc-macro shared library's ELF64/little-endian/x86_64 header and refuses
tampered architecture/truncated header controls. It also retains an exact
compiler/engine/library payload with member-by-member digest verification.
Execution of this refinement is pending; the459-test receipt predates it.
Rust archive object architectures are not independently inspected by that header
check. Artifact retention does not establish installation, HTTP deployment or
production release authorization.

The [retained Linux payload follow-up](../acceptance/project-adoption/g5-linux-tool-payload-2026-10-19/receipt.json)
passed all four CI39301564209 jobs at2cf2eb9 (tested mergebf16fee, identical
tracked tree). All459 upstream tests passed with the explicit Linux target.
Independent bounded inspection verified the uploaded archive SHA-256, all ten
payload members, and compiler/proc-macro ELF64/x86_64 headers. The retained
payload is52,937,102 logical bytes (17,629,458 compressed bytes). Rust archive
object architecture and Intel/application runtime acceptance remain separate.
No library payload was installed or executed by this independent inspection.

## Actual Linux runtime and retained Rust workflow checkpoint (2026-10-19)

The [actual Next Linux runtime receipt](../acceptance/project-adoption/g5-actual-next-linux-runtime-2026-10-19/receipt.json) records selected standalone output running under pinned Linux Node with source/compiler paths unavailable, public HTTP controls and confirmed listener shutdown. The output was compiled on Darwin; Linux compilation and browser/authentication remain open.

The [Intel follow-up receipt](../acceptance/project-adoption/intel-reservations-followup-2026-10-19/receipt.json) records actual retained Axum build, 459 passing library tests, configured-source/tool-unavailable replay and unchanged no-op selection on Darwin. External Cargo cache/linker closure and Linux retained orchestration remain separate. It also records stage-two scheduler qualification and a storage-accounting correction: the canonical retained-state directory is now explicitly counted by native and managed guards. No policy limit increased; old functional passes are not retroactive storage-enforcement attestations. The initial Rust attempt was cancelled and recovered only after reviewed process/container stop evidence; its records remain.

## Rust archive platform-inspection follow-up (pending CI)

The existing actual-Axum Linux qualifier now separately inspects every compiled object member of each retained rlib using recorded GNU ar bytes/version. Thin archives, duplicate/unsupported membership, missing Rust metadata, non-object members, wrong ELF class/order/machine and non-relocatable objects refuse. Each object digest is retained; archive digests must stay unchanged. This checks object headers, not full ELF/link validity or external dependency closure. Runtime execution is pending; prior receipts establish only shared-library/compiler headers. The GNU ar operation semantics are documented at https://sourceware.org/binutils/docs/binutils/ar-cmdline.html. No source compilation or platform pass is inferred from syntax checks.

## Exact managed Linux tool-runtime checkpoint (2026-10-19)

The [managed tool-runtime receipt](../acceptance/project-adoption/g5-linux-tool-runtime-2026-10-19/receipt.json) passed exact retained compiler engine execution with pinned Linux Node24.11.1, matched kernel CPU/memory/swap/PID limits, real source/rustc read refusals, and confirmed container/process shutdown. This is not provider execution, full source/native installation, or application acceptance. Six locked Linux dependency archives passed independent integrity/member rechecks; actual Next Linux build staging is running. Full goal requirements remain open.

The first archive-inspection CI39314603229 failed before tests at an unknown member; all three other jobs passed. Independent inspection of the prior exact retained libraries identified lib.rmeta-link. The pinned rustc source documents this late metadata at https://github.com/rust-lang/rust/blob/b940084d7eb6a299eb4bfeb8e34901bc051e7ac4/compiler/rustc_codegen_ssa/src/back/rmeta_link.rs. Both lib.rmeta and lib.rmeta-link are actual ELF64/x86_64 relocatable objects in the observed archives. The corrected candidate checks both headers as strictly as code objects, requires exactly one of each, and retains their hashes. It does not exempt metadata from architecture checks. Eight full-inspector negative controls now include late-metadata wrong architecture and unknown membership; all prior refusals remain. Execution of the correction is pending.

## Actual Linux build refusal and conservative scheduler fallback (2026-10-19)

The [failed build receipt](../acceptance/project-adoption/g5-next-linux-build-refusal-2026-10-19/receipt.json) records verified staging of180135 actual selected files and six locked Linux dependency packages, followed by genuine Next16.1.6 Turbopack failure at network-required Google Fonts. No TypeScript or manifest-witness pass follows. Missing remote assets must be addressed explicitly; removing fonts or inventing placeholder bytes would change the requirement.

The managed executor retained needs-review after its newer cohort marker appeared in an earlier legacy guard archive. The mismatched archived token and timestamps are retained evidence of a handoff defect, not proof of the exact initiating interleaving. Canonical recovery stopped the owned container but refused absent-cohort release. Separate operator review verified dead owner/group, sealed stopped container, persistent workspace and exact archive digest, then finished only this request. Parallel admission is disabled pending repair and requalification; exclusive fallback remains. Earlier stage-two activation evidence stays historical. All failed outputs and configuration preimages remain; no foreign workload was stopped and nothing was deleted.

## Independently inspected actual Rust archive checkpoint (2026-10-19)

The [archive member receipt](../acceptance/project-adoption/g5-linux-archive-members-2026-10-19/receipt.json) binds all-four-job CI39317528021 at982eac3 and tested merge64a7a3d (identical tracked tree). Independent in-memory inspection verified API artifact17879943 bytes/SHA256, exact payload members, 11 code and six metadata object headers/digests across three real rlibs, and the compiler/shared-library headers. Both metadata members remain subject to ELF64/little/x86_64/relocatable checks. Eight corrupted-archive controls and459 upstream library tests passed. No artifact code was executed during independent inspection. Full ELF/link validity, external dependency closure, installed/provider/application acceptance remain separate. The earlier failed39314603229 receipt remains failed and is not rewritten. Global parallel scheduling stays disabled independently of this pass, pending the native handoff repair.

## Reservation handoff requalification (2026-10-20)

The [isolated Intel requalification receipt](../acceptance/project-adoption/g5-reservation-handoff-2026-10-20/receipt.json) records 57 passing unit/compatibility tests and 22 real-backend controls. These include native-owner finalization, two-job overlap, fixed writable-output quota exhaustion, system metadata write refusal, cancellation, surviving-container crash recovery, output/instance exclusion and fair queuing. All 19 owned containers were independently rechecked stopped after qualification. Candidate source hashes match both test records. Production repair installation and parallel activation remain pending; this does not establish application Linux build or deployment acceptance.

## Retention repair and evidence audit (2026-10-20)

The [audit](../acceptance/project-adoption/retention-audit-20261020/AUDIT.md) separates compact evidence, selected/private context, archive-identical extractions and rebuildable compiler outputs. Exact deletion proposals require separate approval; no automatic purge is authorized. The [retention guide](../guides/retention-and-evidence.md) defines a native per-state attempt ceiling and supervisor full-run growth reservation. Source and tests are prepared; CI and supervisor installation are recorded separately. The earlier 57-unit/22-runtime reservation repair remains qualified but uninstalled because its installer was refused by the unchanged 100 GB guard.

Retention follow-up (2026-10-20): exact approved cleanup completed, supervisor admission installed, rebuilt Intel native retention tests passed 27/27, and source-package evidence selection is bounded. See the [retention audit](../acceptance/project-adoption/retention-audit-20261020/AUDIT.md) for distinct local and CI gates. Broader project adoption and parallel-execution activation remain open.

## Actual guard compatibility activation blocker (2026-10-20)

The [frozen regression](../acceptance/project-adoption/g5-reservation-handoff-2026-10-20/actual-compatibility-regression.json) tests exact retained current Wargame guard/scheduler bytes rather than the earlier qualified compatibility fixture. Its synchronous atomic finalizer archives the lease, but the record omits leaseReleaseCompleted. The new managed scheduler therefore treats the finished request as pending while its owner remains alive. A long-lived owner can queue a follow-up behind managed work that is waiting for that owner to exit. The frozen predicate test fails with the original bytes and passes after an isolated one-line completion-field addition. This establishes the compatibility gap, not a complete queued deadlock/runtime recovery test.

Both actual Wargame files contain existing uncommitted work and remain unchanged by this qualification. The previously source-bound 57-unit/22-runtime candidate remains intact, but its fixture coverage does not attest this actual compatibility path. Production parallel admission stays disabled until actual entry-point rollout, follow-up fairness, installed status/watch and shutdown/recovery controls pass.

Bounded-packaging follow-up: [all five committed-head capability CI gates](../acceptance/project-adoption/retention-audit-20261020/bounded-package-ci.json) passed for a1ea81c in run39480865700. Actual-project Linux compilation and the actual-guard compatibility rollout remain independent unfinished requirements.

## Actual Linux Next compilation (2026-10-20)

The [managed actual-project receipt](../acceptance/project-adoption/g5-actual-next-linux-build-2026-10-20/receipt.json) passes the actual selected existing Next monorepo production build on Linux x86_64 / Node24.11.1 / Next16.1.6, TypeScript checking and generated-manifest witness. Native staging verified180135selected files and six exact locked Linux dependency packages. The original selected app and pointer remain unchanged; all14compiled font digests match captured real font inputs.

This uses the explicitly version-pinned Next CSS-response qualification hook, changing only captured font transport URLs to isolated loopback. It establishes this declared build scope, not automatic offline support for arbitrary Next versions. The earlier network-font build refusal remains failed. The run used exclusive fallback with2CPU/3GiB memory, swap equal to memory, read-only root and a fixed writable quota. Whole-container peak memory was2561671168bytes; production build elapsed91544ms. These are functional observations, not cold/warm acceptance benchmarks. The font listener and owned container were independently confirmed stopped.

The owner generation was previously qualified and was not rerun by this build. Runtime/browser/authentication using this Linux-built output, full dependency closure, framework mutation controls, practical edit measurements, installed-current-package adoption and actual scheduler compatibility rollout remain open. No private application source or raw app logs were published.

## Actual-owner follow-up queue controls (2026-10-20)

The [five frozen state-machine controls](../acceptance/project-adoption/g5-reservation-handoff-2026-10-20/actual-followup-controls.json) extend the earlier predicate-only regression. Exact actual scheduler/guard bytes fail the managed queue-progress case while their native owner remains alive and queues another job. The isolated one-line completion-field fix passes all five: managed progress before native follow-up, fair queuing, failed-finalizer retention, uncertain-stop retention and missing-callback fallback. The executor backend is explicitly synthetic; no workload/container is launched by these tests. Production entry points remain unchanged and parallel admission stays disabled pending actual source-bound rollout and real installed recovery/status verification.

## Linux-produced standalone HTTP runtime (2026-10-20)

The [Linux-built-output runtime receipt](../acceptance/project-adoption/g5-linux-built-next-runtime-2026-10-20/receipt.json) passed all six scoped controls against the exact Linux production build ID and receipt lineage. Staging matched2480runtime files and preserved the original selected-build pointer. Pinned Linux Node served public home/login and existing client-protected-route HTML, rejected a scripted user agent, and failed three real host/source/compiler file reads with ENOENT. The container had no source mount, a read-only root and no external network; reads at the configured compiler and source paths returned ENOENT. The server, listener and owned container were independently confirmed stopped.

This closes the earlier distinction between Darwin-built artifacts merely running on Linux and this Linux-produced output's HTTP runtime. It does not establish authenticated client navigation, permission boundaries, wrong binary/config/listener or stale-contract refusals, full dependency closure or practical edit-performance acceptance. No private source or raw application logs were published. Production parallel mode remains disabled independently of this result.

## Actual Linux-built public browser controls (2026-10-20)

The [Linux browser receipt](../acceptance/project-adoption/g6-linux-built-public-browser-2026-10-20/receipt.json) passes the six existing desktop/narrow public homepage, login-link and unauthenticated-redirect controls against the exact Linux-built Next output. Chromium141.0.7390.37 and Playwright1.56.1 were observed, with browser executable digest, package/input digests, build ID and prior build receipt bound. The official matching image was pulled by immutable digest; an initial missing Docker credential-helper PATH failure was preserved and repaired without changing credential configuration.

The run used CPU2/memory2GiB/fixed writable512MiB, a read-only root, no source mount or external network, three real configured-source/compiler read denials, and existing HTTP/bot-refusal controls. Original selected pointer was unchanged; server/listener/container shutdown was independently confirmed. Desktop and narrow home screenshots were visually reviewed. Private app source, logs, screenshots and traces remain on Intel; two small hash-verified review PNG copies are also retained locally.

This closes scoped public-browser coverage for this Linux-produced output. Authenticated backend/permissions, changed generated-label visibility, wrong binary/config/architecture/listener and stale-contract refusals, full dependency closure, actual edit/watch performance, latest-package application adoption and production scheduler rollout remain open. The synthetic follow-up controls do not authorize production parallel activation.

## Intel reservation repair installed and activated (2026-10-20)

The [source-bound rollout](../acceptance/project-adoption/g5-reservation-rollout-2026-10-20/receipt.json) passed69unit/compatibility tests and23real-backend controls, including the actual guard's live-owner completion/follow-up case. The frozen old activation probe retained four expected failures before repair. Protocol3 validates every declared dependency and requires the actual-guard runtime control; old protocol2 activation code cannot enable protocol3 concurrency.

Exact installed preimages were preserved. The scheduler, executor and canonical native guard were updated, and the actual compatibility scheduler received only its completion-marker assignment, preserving existing working changes. The unchanged CLI was identity-checked. A fresh-process installed executor then proved fixed writable ENOSPC, read-only system metadata and stopped-workload release before activation. Actual installed status/watch passed two snapshots; independent inspection confirmed all22owned containers stopped/nonpaused/nonrestarting/PID0, including the global CLI cancellation probe and installed smoke.

Parallel reservation admission is now active for verified managed jobs on Intel. Capacity/output conflicts, native jobs, benchmarks and unknown ownership retain conservative exclusive behavior. Existing4GBgrowth/100GBretention/500MBreserve limits were not raised; no files, containers or backing images were deleted. This closes the previously pending scheduler rollout, independently of the unfinished framework/application/performance/release requirements. Actual compatibility working-tree changes were not committed into the private application repository by this rollout; complete before/after bytes and backups remain on Intel.

## Actual Next deployment refusal checkpoint (2026-10-20)

The [existing-project refusal receipt](../acceptance/project-adoption/g5-next-deployment-refusals-2026-10-20/receipt.json) records five actual Linux-produced standalone runtime cases: healthy public HTML before and after a non-server executable, missing build-directory configuration and wrong-listener negatives. The executable exited0 without readiness; missing configuration exited1 with a production-build diagnostic; the wrong port served real HTML while the required port refused. All2480 original runtime files and the selected pointer remained unchanged, and owned children/listeners/container were stopped. CPU2/memory1.5GiB/fixed512MiB writable limits used the installed executor without a source mount or external network.

The original aggregation failed after successful workload exit because its expected redundant receipt field was absent. That record remains failed. Independent read-only verification bound the saved behavioral receipt to the prior successful Linux build, checked the exact original bytes/pointer and stopped container, and succeeded without rerunning the workload or weakening controls. Private source/variant/logs remain on Intel; only scoped metadata is published.

Wrong-architecture runtime and stale-contract refusals, authenticated backend/permissions, broader framework boundaries, actual edit/watch performance, latest-package adoption and final release acceptance remain open. The pinned Node ELF header pass does not close architecture runtime refusal.

## Linux retained Rust orchestration gate (prepared, execution pending)

The existing pinned-Axum Linux qualifier now composes the native context/project-build APIs rather than inferring retained orchestration from separate Cargo commands. It declares 335 actual source paths / 333 selected text inputs, five closed symlinks, explicit Linux target/features/configuration and provider/Cargo/rustc bindings. Acceptance requires four selected compiled libraries, generated four-package inventory, 459 upstream library tests, retained ELF/archive-member inspection, selected-output corruption refusal, source/snapshot/configured-tool-unavailable replay and unchanged-key no-op with zero cache hits.

A separate 128 MiB / 8,192-member archive retains only the native tool, license, replay metadata, immutable candidate and selected outputs. Unselected writable compiler-cache files are excluded. Every member must match its recorded bytes/link, and fresh restoration must pass native replay while configured inputs/tools remain unavailable. This bounds retained evidence without deleting any original CI data or claiming hermetic cache/linker/toolchain closure.

The implementation and syntax checks are prepared; Linux execution is pending. A pass must be independently inspected before updating the support matrix. Deployment, authenticated behavior, practical performance and other G3–G6 requirements remain open.

The first run39518072769 atff2aae4 failed before native retained execution: source preparation hashed the lexically earlier README symlink before copying its selected target. All four sibling jobs passed. The correction copies the complete unchanged335-path selection first, then verifies every resolved digest and exact link target. The failed run/log remains evidence; retained Linux acceptance is still pending a corrected execution.

The [real-source copy regression](../acceptance/project-adoption/g5-linux-retained-preparation-2026-10-21/source-copy-regression.json) now passes under Intel's canonical supervisor for all335 paths/five links, with original source unchanged. The [failed first run](../acceptance/project-adoption/g5-linux-retained-preparation-2026-10-21/failed-first-run.json) remains preserved. Corrected9325f1d is in active full acceptance run39527650024; Linux retained execution is still unaccepted at this checkpoint.

## Actual retained Linux Rust orchestration verified (2026-10-21)

The [independently inspected receipt](../acceptance/project-adoption/g5-actual-axum-linux-retained-2026-10-21/receipt.json) binds all-five-job success in 39527650024 at 9325f1d. The pinned actual workspace now passes native context/build selection, 459 upstream tests, selected-output corruption refusal, source/snapshot/configured-tool-unavailable replay and selection-preserving no-op. The 16.14 MB / 812-member archive excludes unselected compiler caches; every member hash/link matched and a fresh Linux restoration replay passed. Original upstream source was unchanged. The first failure remains failed. This closes the specifically pending retained Linux library orchestration gate; external Cargo cache/linker/toolchain closure and application/deployment/performance acceptance remain open.

## Additional real Next framework candidate intake (not executed)

Existing selected primary Seeder source has no reviewed real route-group/ServerAction/rewrite cases. Its optional ad-platform-web has route-group paths outside that context and a possible duplicate dashboard route; baseline must be tested unchanged, without omitting paths or editing unrelated application behavior to manufacture a pass.

A further pinned MIT project candidate is [Fumadocs 2919bf9](https://github.com/fuma-nama/fumadocs/tree/2919bf9a9a84a7a594d42460878548d0677d7bb3). Its [docs package](https://github.com/fuma-nama/fumadocs/blob/2919bf9a9a84a7a594d42460878548d0677d7bb3/apps/docs/package.json) declares Next 16.4.2; the [root package](https://github.com/fuma-nama/fumadocs/blob/2919bf9a9a84a7a594d42460878548d0677d7bb3/package.json) requires Node >=24.14.0 and pnpm 12.14.0. The previously captured Linux Node 24.11.1 does not satisfy that requirement. Read the installed Turbo documentation required by its AGENTS.md before choosing scoped build commands. Full selected source/lock/tool/context capture and capacity admission are required before execution.

The candidate has real route-group source pages and [two inline Server Actions](https://github.com/fuma-nama/fumadocs/blob/2919bf9a9a84a7a594d42460878548d0677d7bb3/apps/docs/lib/github.ts). Those actions ultimately post GitHub Discussions; external posting is outside this goal's authorization. Initial scope is public routes and credential-free schema/origin/body/missing-configuration boundaries with no external network or real credentials. Observe public runtime action references rather than reading secret-bearing action manifests. The directly reviewed config has no rewrites; three wrappers' effects remain uninspected. This is intake, not a build/runtime pass, and does not replace any Wargame/Seeder acceptance requirement.

## Pinned Next preparation gate (implementation prepared, execution pending)

The dedicated next-preparation mode in the existing native-capabilities workflow prepares Fumadocs 2919bf9 without running application build scripts. Normal all-mode capability acceptance retains its existing five gates. This preparation mode is not a substitute for those gates or G3–G6 application acceptance.

Frozen preparation requirements: exact official Linux Node 24.21.0 archive and pnpm 12.14.0 native package integrity/version; blob-filtered pinned source with reserved dotenv/npmrc paths omitted before materialization, unique excluded blobs absent and exact selected Git-blob/content bindings; native nonsecret source-context capture, verify and reconstruction; root/docs workspace dependency closure selected through pnpm's documented filters with frozen lock and lifecycle scripts disabled; installed Next 16.4.2 and owner-required installed Turbo documentation; original selected source unchanged. The CI preparation phase keeps a 4 GB growth ceiling and 500 MB free-space reserve; Intel policy is unchanged. No caches or failures are purged.

Three retained real-Git controls pass on Intel: excluded files and their unique blobs stay absent, an allowed empty file sharing an excluded file's blob remains usable, actual special Next filenames/closed links materialize, and a link into an excluded path refuses. The first control attempt exposed Git promisor negotiation behavior; that failure remains retained, and explicit no-negotiation blob backfill passes without weakening exclusions.

The [Git partial-clone contract](https://git-scm.com/docs/partial-clone) supplies filtered metadata and selected backfill; [checkout-index](https://git-scm.com/docs/git-checkout-index) respects explicitly marked skip-worktree entries in a fresh destination. No deprecated non-cone pattern selection is used. pnpm's [filter contract](https://pnpm.io/filtering) selects the docs workspace/dependencies and root tooling. The real repository's tracked apps/docs/.env is never a selected source input.

Preparation deliberately leaves Next compilation/manifests, independently declared nonsecret configuration, actual public HTTP/browser/Server Action boundaries, dependency hermeticity, retained application build, installed consumers and performance unaccepted. The owner registry pre-build, GitHub feedback posting and Orama index update are unrun. GitHub posting and Orama updates remain outside initial mutation scope, with their credential references unresolved; follow-up compilation must inspect all actual owner build effects and required generated/remote assets before execution.

The first Next preparation run39533833003 atfe88deb passed all three Git controls, verified exact Node/pnpm tools, fetched only selected source, and completed native source capture/verification/reconstruction. It then failed at dependency installation because pnpm12 rejects the legacy --fetch-retries option. Its exact466050-byte artifact SHA11764ab33947beca0786854f1f63afb8ed938192e2f804de864d8b959715026d and failed receipt/logs remain preserved on Intel. The correction removes only that unsupported nonsemantic retry override; frozen lock, disabled lifecycle scripts, selected closure, source/privacy checks, 1200-second command deadline and4GB preparation-growth budget remain. Full preparation, build and runtime remain pending.

## Existing private standalone Cargo package checkpoint (2026-10-21)

The configurable standalone qualifier now accepts explicit manifest, lockfile, package-name and toolchain-file arguments, plus an opt-in lockless mode; its existing Wargame defaults remain intact. Streaming SHA-256 and compiler-path resolution also make the driver work with the Intel Mac's system Python and when the compiler is invoked from the private project directory.

The [sanitized receipt](../acceptance/project-adoption/g3-standalone-cargo-lockless-2026-10-21/receipt.json) records a real Intel observation against one existing private standalone Rust package with no Cargo.lock. Default root selection refused as expected; explicit `standalone-package` plus `declared-local` observed one package and three targets. Only the nonsecret Cargo manifest was captured. The manifest and tracked project state stayed unchanged, and no lockfile was created. The successful run held the exclusive shared lease with a declared 256 MiB disk allowance and used about 12.7 MB.

The raw request, capture and unredacted receipt remain on Intel because they contain private project identifiers and source-derived data; they are not committed. This gate does not establish dependency resolution, project compilation, build-script execution, runtime behavior, deployment, or full adoption. Those gates remain open and require a retained candidate for any operation that would modify the private project.


## Existing Next.js route-shape observation checkpoint (2026-10-22)

The [sanitized receipt](../acceptance/project-adoption/g3-existing-next-route-observation-20261022/receipt.json) records a real Intel source observation against an existing Next.js 14.2.14 App Router project whose identity and source remain private. The declared 66 nonsecret inputs yielded 54 page entities, 53 page source paths under route groups, 21 dynamic pages, one route-group segment, 16 dynamic segments, one optional catch-all, 70 total segments, and 21 routing schemas. A missing selected input was refused, source/tool-unavailable record replay passed, and independent post-run checks confirmed the original checkout stayed clean and unchanged.

The first default 4 GB admission was refused by the existing retained-output limit. The observation then ran exclusively under the installed Intel supervisor with an in-memory 256 MiB per-run ceiling; it consumed 36,823,040 bytes by the supervisor's free-space measure, stopped cleanly, and did not alter persistent policy. Raw capture and route details remain privately on Intel. This is source-shape evidence only: no owner build, HTTP/browser test, configuration interpretation, rewrites, Server Actions, dependency closure, or deployment was run. Those G3 and G6 requirements remain open.


## Required Next.js route-shape controls checkpoint (2026-10-22)

The reusable Next qualifier now accepts repeatable --require-route-shape controls for route groups, dynamic segments, and optional catch-all segments. Its receipt reports normalized route-shape counts; two focused tests cover positive classification and avoid false positives from lookalike text in unrelated fields. Python syntax checks and git diff --check passed.

The [second sanitized real-project receipt](../acceptance/project-adoption/g3-next-route-shape-controls-20261022/receipt.json) binds the updated driver to a repeat observation of the same private Next.js 14 project. All three required shapes passed: one route-group segment, 16 dynamic segments, and one optional catch-all. The existing missing-input refusal, source/tool-unavailable replay, source immutability, and Intel exclusive reservation controls also passed. This turns the observed route-shape case into a reusable acceptance gate, while actual application compilation, config/rewrite semantics, HTTP/browser runtime, and Server Actions remain unverified.


## Existing standalone Cargo compile attempt (2026-10-22)

The [sanitized receipt](../acceptance/project-adoption/g3-standalone-cargo-build-20261022/receipt.json) records the next real-project gate after the lockless metadata observation. Patamaps captured and staged six explicit nonsecret package inputs. The first candidate location accidentally inherited Patamaps' Cargo workspace; moving the candidate outside that workspace fixed the isolation error. An offline-only retry then revealed that the local Cargo cache lacked tauri. Fetching the public dependency graph into an isolated credential-free Cargo home resolved a candidate-only lockfile with 407 package entries.

The subsequent locked offline Cargo check reached the actual Tauri application, then failed during generate_context! expansion because its default icons/icon.png asset is absent. No tracked or non-generated image/icon asset exists in the source project; no placeholder was introduced. The original project stayed clean and without a Cargo.lock. Its configured npm run build hook and test suite were not run. A genuine application icon or an owner change to the configuration is needed before a truthful complete Rust app compile can pass; G3/G6 acceptance remains open.


## Next.js 14.2 build-manifest adapter (library, CLI, and actual-project manifest-parser replay verified)

Commit `88b55ec` adds a narrowly reviewed Next 14.2 version-3 manifest path alongside the existing Next 16 shape. A read-only inspection of the installed `next@14.2.23` source at `dist/build/index.js:638-667` confirmed the writer emits version 3, omits `appType` and `rewriteHeaders`, and serializes rewrites as either a flat after-files array or a phase object. The adapter maps the flat array to `afterFiles` and records `skipMiddlewareUrlNormalize` as opaque metadata. i18n and unreviewed framework versions remain explicit refusals. Focused Rust tests cover accepted flat/phased rewrites and unsupported variants. The first CI run exposed an outdated unconditional `rewriteHeaders` check; commit `49dbe67` corrected it and added regression coverage. The [verification receipt](../acceptance/project-adoption/g3-next14-manifest-tests-20261022/receipt.json) records all 44 `patamaps-workspace` library tests plus a locked build of the `patamaps` CLI passing in Linux CI run 39718879830. At that earlier check, the Intel supervisor reported 2.81 GB available, below its 4 GiB reserve, so the Intel CLI rebuild had not run.

At the time of the [read-only inventory](../acceptance/project-adoption/g3-next14-manifest-review-20261022/receipt.json), an existing Next 14.2.14 version-3 routes manifest had the expected flat-rewrite shape and a companion app-paths manifest. The generated outputs had no source identifier, so generation from the recorded source commit was not established. Intel capacity was then below the interactive reserve and the parser had not processed those inputs.

The later [actual-manifest replay](../acceptance/project-adoption/g3-next14-actual-manifest-replay-20261022/receipt.json) closes that parser-replay subgate: Patamaps ingested the three retained manifests, observed 55 routes (34 static, 21 dynamic), 55 app-path mappings and one redirect rule, then verified record bindings with selected inputs unavailable. The exact manifest hashes, source revision, Patamaps CLI identity and guarded command results are in the receipt. This was an exclusive native run under a temporary in-memory 256 MiB growth reservation; persistent policy was unchanged and no files were deleted. The outputs remain unbound to the source revision. The configuration projection was agent-authored static/default data, not an executed Next config or build receipt. Owner build, effective configuration, HTTP/browser behavior, Server Actions, dependency closure and deployment remain open.


## Second existing Next 14 source snapshot (2026-10-22)

The [sanitized receipt](../acceptance/project-adoption/g3-next-current-source-shape-20261022/receipt.json) records a second, later source revision of the same private Next.js 14 App Router project. On Intel, 59 explicitly selected nonsecret files, including all 58 special route files and the frontend package manifest, produced 52 observed pages, 17 dynamic segments, one route group, and one optional catch-all. Required-shape assertions, missing-input refusal, source/tool-unavailable binding replay, exact source recapture, source immutability, and supervisor stop proof passed. No environment files were selected or read; Next configuration was not interpreted. This is source-shape evidence, not a second independent project, an application build, or runtime acceptance.

The shared supervisor currently refuses its default 4 GB preflight for insufficient retained-output headroom; this observation fit a stricter in-memory 256 MiB reservation without changing persistent policy. The earlier generated-output deletion inventory no longer matches current file identities, so its approval was not exercised and no files were deleted.


## Fresh existing Next 14.2.23 build checkpoint (2026-10-22)

The [source-bound preparation and interrupted-build receipt](../acceptance/project-adoption/g3-next14-source-bound-build-20261022/receipt.json) records native capture/verification/staging of all 923 selected frontend files and a standalone TypeScript pass with the owner-required Node 22.9.0. Original source, tools and configured dependencies stayed unchanged. The first build exposed ARM64-only installed SWC; an exact integrity-verified Intel optional dependency, supplied only through an isolated NODE_PATH, resolved that preparation defect. Original source/dependencies were protected by a sandbox that independently refused outside writes and network connections. Seven captured real font files supported the unchanged source through Next14's explicit font-response adapter.

The follow-up reached Next's type-validation phase, then the supervisor stopped it after aggregate disk growth exceeded its declared 1.5 GB cap. This remains an interrupted application build, not a pass of the built-in typecheck, static generation or runtime. The aggregate free-space delta is not isolated write attribution. The sealed native process group was confirmed stopped; an unchanged pre-existing database container had no Docker exec sessions or non-PostgreSQL processes. Original failed records remain preserved and the native lease is released after that independent review. No global scheduler policy or parallel activation changed.

The targeted [cleanup inventory](../acceptance/project-adoption/next14-cache-cleanup-review-20261022/inventory.json) identifies six generated Webpack packs totaling 1,074,593,792 allocated bytes. Source/snapshots, non-cache output, diagnostics and tools are excluded. No backup or exact restoration of these caches is verified, and no files were deleted. Obtain approval for this exact list before removal, then select a growth reservation that fits both the unchanged 4 GB per-run maximum and current retained-output headroom. Do not repeat the unchanged 1.5 GB attempt. Full source-bound Next build/manifest replay, broader framework boundaries and G3–G6 acceptance remain open.


## Fresh Next manifest replay and actual configuration refusal (2026-10-22)

The owner approved the six-file Webpack cache inventory. SHA-256, complete recorded identities and absence of active work were rechecked before removing only those six files under the scheduler mutex. All directories, source/snapshots, non-cache output, tooling and diagnostics remain. The [deletion result](../acceptance/project-adoption/next14-cache-cleanup-review-20261022/deletion-result.json) records the disposition; no cache backup or byte-exact restoration was claimed.

The [fresh-source follow-up](../acceptance/project-adoption/g3-next14-fresh-source-replay-20261022/receipt.json) verifies a candidate-only cache:false/one-worker overlay, one Rayon thread and a 1 GiB Node heap. Delegation checks preserved owner webpack branches except caching, other configuration except worker count, and all 20 header rules. An earlier cache-disabled attempt still hit aggregate disk-growth accounting despite only 4.2 MB of candidate output; that failure is preserved and system-wide growth attribution remains unestablished. The final profile completed compilation and built-in typechecking, then failed prerendering because the reviewed API client requires NEXT_PUBLIC_BASE_API_URL. No raw environment file, real credentials or external application network were used. This is an application prerequisite, not a demonstrated Patamaps defect; full application build/runtime remain unaccepted.

The failed producer receipt binds all three fresh manifests to the 923-file source inventory and resource overlay. Native parsing passed with 53 routes, 20 header rules, one redirect and 53 module/route aliases. Independent inspection matched every route regex/key, rule condition/value/index and module/route mapping. Byte-digest and missing-projection controls refused; replay passed with configured inputs/provider unavailable and PATH empty. This closes the fresh-source parser-replay subgate, not successful application build, effective configuration/authentication, runtime header matching or G3–G6 completion. The producer receipt is orchestration evidence and its buildReceiptDigest remains opaque declared metadata to the adapter, not Next/admission attestation.

The candidate has 28,250,112 allocated output bytes and zero persistent Webpack packs. Sampled group RSS and aggregate free-space changes do not establish paired performance, exact write attribution or a kernel memory quota. Both completed native reservations released normally. Continue the application case with a reviewed nonsecret API URL/projection or explicitly scoped isolated lab value; further prerequisites may emerge. Do not ingest raw dotenv/secret files to obtain a pass.


## Digest-bound ELF target-header preflight (2026-10-22)

The scoped [receipt](../acceptance/project-adoption/g5-elf-target-preflight-20261022/receipt.json)
records 50 passing workspace tests, a native CLI build and 11 artifact checks.
The opt-in Rust/CLI preflight checks the declared digest plus ELF64 little-endian
machine for linux/amd64 or linux/arm64; both real official Node 24.11.1 binaries
matched their own target and refused the other. Digest mismatch, malformed
header, symlink, FIFO, directory and oversized file refused. No artifact ran.
The exclusive 1 GiB guarded run finished and released normally; no files were
deleted and parallel activation remains disabled.

This extends an existing owner's verificationSteps without changing the build
or command model. See the [usage contract](../guides/elf-target-preflight.md).
It is a development-tree enhancement, not part of the published alpha CLI.
A matching header is not loader/library/CPU/OS/runtime acceptance, and the
separate check does not prevent replacement before a later launch. G5 actual
wrong-architecture runtime and stale generated-artifact refusal remain open.
The source-bound Next case still awaits reviewed nonsecret API configuration.


## Captured configuration and owner-directed Next deferral (2026-10-22)

The [independently verified case](../acceptance/project-adoption/g3-next14-captured-lab-config-20261022/receipt.json)
passes captured-only native command environment, unresolved-reference refusal,
three-input offline configuration replay and log/child-status bindings. The
qualifier first exceeded the existing stderr bound; that failure remains.
The corrected run preserves the 64 KiB native stderr limit through a captured,
bounded-log launcher. Guard/collector exited0; the actual Next child exited1.

Next reached typechecking, page-data collection and static-page generation,
then failed prerendering with Missing Nango public key. Linting was skipped by
unchanged owner configuration. All three compiled manifest semantic maps match
the prior producer; two serialized key orders changed. No redundant replay was
run. The owner selected deferral: no invented key, raw dotenv or unchanged retry.
G3/G6 application acceptance stays open; continue other adoption requirements.

[Full applicable CI](../acceptance/project-adoption/g5-elf-target-preflight-20261022/ci-39847645841.json)
passed six jobs for PR head d6433e2 on merge checkout 7a5e30b. Fumadocs was skipped.
This does not establish installed ELF-check or external app deployment acceptance.


## Native architecture selection and Linux execution (2026-10-22)

The [independently checked self-hosting case](../acceptance/project-adoption/g5-native-architecture-selection-20261022/receipt.json)
uses the same actual Rust component from successful x86_64/aarch64 CI. Native
context/build selection accepted x86_64. ARM64, with its correct digest but
declared linux/amd64 target, failed ELF_ARCHITECTURE verification before
selection. The prior pointer stayed byte-identical. Replay passed with
configured source and snapshot paths unavailable.

The selected x86_64 component then started in managed Linux and returned its
defined no-argument usage refusal (program exit1; probe/control exit0). No trust
or activation was used. CPU1/memory256MiB/fixed64MiB quota, read-only root,
absent source/network mounts and input hashes were checked before launch.
Container stopped and all reservations cleared. This is not kernel rejection of
ARM or external application deployment.

Preserve the initial state-path failure and interrupted larger quota preparation.
The latter exhausted the lowered native aggregate growth budget; kill EPERM
left ownership for review. Stop proof/original records were preserved before
scoped recovery. The smaller preparation-only retry succeeded without repeating
passed build controls. No files deleted. Stale contracts, external deployment
and G4 actual edit-performance requirements remain open.


## Fresh installed Next command checkpoint (2026-10-24)

I1 passes [independent review](../acceptance/project-adoption/g5-installed-next-20261024/accepted-40061124534/independent-verification.json)
at13faaa4: both fresh source/native installations completed the real pinned
Chatbot build/native checks,28 auth/rewrite groups and four upstream tests each,
with checkout compiler/qualifier unavailable. Exact packages,1,164 shipped source
members,455 program files against Git, unchanged/restored source inventory and
before-marker refusal passed. All owned runtimes stopped; actual TCP-only test
database settings were verified. Earlier failed runs remain recorded.

Private output observations showed zero changes across1,081 entries, including
one un-followed symlink, per owner. No full runtime tree was selected and no
dependency closure or performance was established. Continue
[I2 retained Next bundle](2026-10-24-installed-next.md#i1-acceptance-and-next-i2-increment),
applicable dependency/test-context treatment, remaining deployment controls and
exclusive actual-project latency/memory/disk measurements. G4–G6 stay open.


## Complete pinned retained Next installed checkpoint (2026-10-24)

I2 now passes [exact package/runtime review](../acceptance/project-adoption/g5-installed-retained-next-20261024/accepted-40071420581/independent-verification.json)
at80ae616/engine2fc8a201. Both fresh source/native installations built the real
pinned Next standalone owner and passed28 groups/four unchanged upstream tests
each, native retained selection/admission/postcheck and three tamper refusals,
actual image/kernel/read-only/cache enforcement, producer absence, unchanged
output inventories, restoration and owned-runtime cleanup. All1,180 packaged
source members matched Git/inventory and both archive/engine identities passed.
Locked/offline fresh source compilation reused declared dependency artifacts;
it did not borrow the checkout compiler. Sampled peak growth3.987GB stayed under
4GB with narrow margin. [I2 scope and limits](2026-10-24-installed-next.md#i2-fresh-installed-retained-workflow-accepted).

This closes the selected pinned full-Next-bundle/installed subgate. G4 actual-
project exclusive cold/warm/edit measurements and remaining scoped owner/deploy
requirements stay open; no blanket hermeticity, performance, arbitrary Next
compatibility or production activation is inferred.


## Original Next architecture increment (2026-10-28)

[The independent increment](2026-10-28-original-next-architecture.md) now passes
genuine x64 Node selection, correct-digest ARM64 refusal, offline Node-producer
binding replay and exact staging of2,480 existing actual-owner runtime files.
Its initial managed namespace-size inspection failed before application launch;
owned resources stopped and the reservation released. The actual host quota
bound remains verified. The bounded physical-versus-namespace inspector repair
is statically implemented, but retention admission refused before execution.
A precise472-file compiler cleanup proposal is pending approval. Architecture
application startup/refusal acceptance remains unachieved; this does not close
stale-contract, authenticated/browser, watch, performance or full G5/G6 gates.
