# Scientific and native consumer checkpoint

Date: 2026-10-10; latest verification extends into 2026-10-11 UTC. This is an
uncommitted, unpublished implementation. The R0–R11 goal remains active because
Linux runtime, Linux package installation and the governed consumer lifecycle
have not passed. Neither a production installation nor a production activation
has occurred.

The nine Rust crates implement strict contracts, immutable indexed graphs,
scoped ownership, contextual and application-topology admission, checked laws
and proofs, typed uncertainty, unique risk closure, static native projections,
path trees, capture/replay, exact external approval verification, a fixed Linux
activator, finite repair, captured explanations, workspace discovery/checking,
and bounded SSSOM/RO-Crate interoperability. Separate routing and scientific
Rust consumers compile and execute the generated artifacts. The optional
discovery bridge reuses pinned MetaMap adapters.

The final compiler source identity is
`sha256:07f74356f72db6236458375321a18f36240642e695f5e1fbc1a37b9c74fe775f`.
Governance: `sha256:c486ea479e3d0371bec3f5a6fa7f0350b304610280f3ee2253e71539892b031a`.
Workspace: `sha256:2f2f535c8086b66daec416d4577a78e1acd5797874ddcad7007d28c6dc842403`.
Scientific: `sha256:78032b00a319c0fa6d3df5f6c303409643922f330df6bcf2f01bcf15c4ed66ad`.
These identities bind embedded source and dependency declarations, not
reproducible binary bytes, independent approval or scientific truth.

## Actual macOS verification

Host: aarch64 macOS, Rust 1.99.0, Node 22.16.0 for reference tests and optional
adapters, default Cargo features. Builds used
`CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0`.
Fresh linked builds additionally selected the existing
`SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk`: the default
SDK 27.0 exposed an unsupported `arm64e.x1` target to the installed Apple linker.
No system SDK setting was changed.

| Check                                                                      | Observed result and limits                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cargo test --workspace --locked --offline`                                | 100 tests and 13 compile-fail documentation tests passed in a fresh complete run. Linux-only tests do not execute on macOS.                                                                                                                              |
| `cargo clippy --workspace --all-targets --locked --offline -- -D warnings` | Passed.                                                                                                                                                                                                                                                  |
| Same Clippy command with `--target aarch64-unknown-linux-gnu`              | Passed type/compile checks, including Linux test bodies; no Linux runtime result.                                                                                                                                                                        |
| `cargo build --release --workspace --locked --offline`                     | Passed with SDK 26.5. All nine crates and the release CLI built.                                                                                                                                                                                         |
| Shared routing/semantic differentials                                      | 18 routing and 40 law, uncertainty and budget cases agree on their declared comparison contracts.                                                                                                                                                        |
| Application-topology differential                                          | 17 cases agree on admission, active mapping IDs and finding codes/subjects, including nearest-provider ambiguity, removals and exclusions. Six native tests also exercise bounded work/refusal.                                                          |
| Scientific differential                                                    | Nine pinned-reference cases agree on source interpretation and full entity/mapping data after explicit D001 envelope normalization and propagation ordering.                                                                                             |
| Native binding matrix                                                      | All 22 unchanged original expectations pass. Nine JSON runtime-input shadows agree with the existing TypeScript consumer. D002 declares the initial function signature; D008 names two diagnostic differences.                                           |
| Legacy example migration                                                   | Five freshly evaluated examples agree on decisions and findings. Original graph/policy/generation bytes remain separate, with explicit new pack/digest bindings. Historical approvals and execution are not migrated.                                    |
| Optional adapter bridge                                                    | All five adapters exercised. Four viable fixtures pass; legacy catalogs preserve unknown loss and refuse with `UNDECLARED_LOSSINESS`, matching the original kernel. Exact provided-file receipts are checked; repeated checks leave baselines unchanged. |
| Schemas, canonical numbers, governance and inspection                      | Native schema/unknown-field controls, independent ECMAScript canonical controls, independent WebCrypto signing controls and captured JSON/HTML inspection checks passed.                                                                                 |

Disposable macOS installation passed for the release binary and a CLI freshly
built from the extracted source workspace. It verified both archive hashes,
the complete source inventory, binary digest and matching engine identities.
The packaged release CLI and source-installed CLI produced identical portable
artifacts with Node absent from PATH. Rust SDK, installed Python/TypeScript
wrappers, actual generated Rust/TypeScript consumers, read-only drift refusal,
all 22 migrated binding cases, scientific lookup and all five optional adapter
controls passed. The [installation receipt](native-installation.json) identifies
the latest actually tested archives; earlier candidate and R9 archives remain
historical evidence under `distributions/`. This is separate from Linux
installation, which remains pending.

The current source/native draft bundles are retained under
`docs/acceptance/distributions/macOS-lifecycle-bench/`; the earlier
`macOS-final/` bundles and their installation receipt remain historical evidence.
The installation receipt is outside
the archives it verifies. The source SDK includes the complete workspace,
consumer templates and acceptance evidence; it is not an individual crates.io
publication or a protected activator installer.

Detailed evidence: [routing](reference-routing-final.json),
[semantics](reference-semantic-final.json), [topology](reference-topology.json),
[scientific comparison](scientific-differential/acceptance.json),
[native bindings](native-binding-matrix.json),
[legacy migrations](legacy-migration/acceptance.json),
[adapter bridge](adapter-bridge.json), and
[native scientific results](scientific-native/acceptance.json).
The [final native check receipt](native-final-checks.json) records actual command
outputs; the [full Cargo test log](native-final-cargo-test.log) preserves the
completed 100-test and 13-documentation-test run. The earlier
[99-test log](native-test-before-lifecycle.log) and
[check receipt](native-checks-before-lifecycle.json) remain preserved. The
[source integrity receipt](source-integrity.json) checks original bytes and
expectations separately from native-profile coverage.

## Original corpus and explicit differences

The reference is pinned at `399747a4ad05a37cd8db1cedd53048fad2175be4`; its local
checkout remains at `6a6a9d2415df85504a83fce4fd7291d0391c0d17` and remains clean.
All 82 original conformance files and nine additional scientific source pins
were checked against their original Git bytes. Original expectations were not
edited. Every one of the 53 original suites has an explicit native destination
and scope in [the conformance manifest](../../fixtures/conformance.json).
That matrix is profile coverage, not a claim of old API parity or a one-for-one
port of 584 assertions.

The isolated original 53-suite run passed **584 tests, with 17 macOS skips**.
The initial parallel run's five timeout failures remain in its raw record.
A first serial harness exceeded its aggregate timeout; the successful run used
one worker and a larger harness deadline, preserving individual test timeouts
and original source. A subsequent receipt-only path-alias repair reused the
identified successful report without rerunning its 584 tests. Scientific
comparison cases were freshly rerun. See [full reference receipt](full-reference/acceptance.json),
[successful raw report](full-reference/reference-vitest.json), and
[initial parallel failures](full-reference/reference-vitest.initial-parallel.json).

D001–D009 remain explicit successor-profile differences. They cover new strict
envelopes/content addresses, initial static function signatures, finding-only
waivers, empty-selector diagnostics, literal nonrecursive hydration, strict
Ed25519 weak-point rejection, narrower resource bounds, two native diagnostic
names, and complete captured-source scientific packaging. The
[D005/D006 controls](reference-differences-final.json) and
[D007/D009 controls](profile-differences.json) retain actual original/native
results. A 16 MiB + 1 well-formed SSSOM source is accepted by the original source
reader and refused by Rust's declared limit. A viable receipt-only capture can
replay successfully but cannot become a complete scientific crate.

## Scientific and debugger limits

The licensed seven-assertion MGI subset retains its raw source, prefix mappings,
direction, confidence metadata and distinct repeated assertions. A separately
built native lookup agrees with the existing TypeScript lookup and returns all
five declared SKOS relation categories. Authored exploratory tolerance allows
seven explicitly lossy, irreversible imports at ordinal cost 18; stricter
budget, reversible, stale-premise and unsupported-evidence controls refuse.
Confidence is neither calibrated probability nor an admission shortcut.

Independent SSSOM-py 0.4.17, sssom-schema 1.0.0 and RDFLib 7.1.4 checks run in
a pinned Python environment with network forbidden during checking. All three
SSSOM validation categories pass for the source, default export and condensed
export. The checker's known `strict=True` metadata-parser defect remains a
recorded failure, with no patched dependency or disabled validation category.
Offline RDF expansion checks the pinned official RO-Crate context, 121 triples
and all 16 payload files, hashes, sizes and media types. Native verification
replays admission, reimports original sources and regenerates inventory bytes;
tamper/missing/extra/source-substitution controls refuse. This establishes the
bounded format/profile checks, not universal RO-Crate conformance or scientific
truth. See [independent checks](scientific-independent.json) and the
[checker dependency lock](scientific-checker-requirements.txt).

Mouse and keyboard inspection passed for synthetic rejected/viable HTML at
compiler source identity `58e035b0e2b4869ab6455c4f89484af548950e10bfbf64da596058df09d97db7`.
The renderer source is unchanged; current CLI JSON/HTML checks passed at the
final identity. Direct file navigation was refused, so browser checks used a
fixed loopback-only server holding two synthetic pages in memory. Later browser
reconnection returned no available browser. The [browser receipt](debugger-browser.json)
preserves the DOM and keyboard observations and distinguishes deterministic
fixture reconstruction from bytes independently hashed at visit time. No
screen-reader, contrast, complete WCAG audit or current-identity browser run is
claimed.

The [phase measurement record](benchmarks/phase-benchmark.json) now retains seven
trials for fresh CLI startup/compilation and separate warm SDK decode, canonical
hashing, graph checks, admission, 32 projection specifications, emission,
capture/replay and bounded repair. Controls cover valid/rejecting 1k/10k graphs,
the 100k byte-limit refusal, 64-level delegation, eight branching proofs with
overlapping cost-17 closure and original topology removals. All predeclared
decisions passed. Explicit Zod discovery is measured separately. Raw inputs,
per-child peak RSS, artifact/binary sizes and dependency footprint are retained;
see [method and limits](benchmarks/METHOD.md). The 100k graph exceeds 16 MiB and
is not a successful capacity measurement. Earlier
[release](native-benchmark-release.json) and
[development](native-benchmark.json) routing runs remain historical. There is no
matched TypeScript timing baseline, per-phase live-memory attribution, Rust
speed advantage or Linux performance claim.

The [portable lifecycle receipt](lifecycle-pure.json) executes the same shared
fixture used by the Linux test: two independently authored source shards,
scoped delegation, a checked chain derivation, explicit tolerance of unknown
identity and a complete cost-three mapping closure. Supported-only identity
and cost-two controls refuse in the native test. Actual CLI capture/replay,
read-only inspection/repair and generated Rust dispatch pass. A repair is an
unapplied proposal requiring approval. This portable check does not execute
external approval or protected activation.

## Remaining Linux gate

Ten Linux test functions compile, covering the protected installed executable,
owner trust administration, UID 65534 refusals, source/manifest substitution,
concurrency and stale bases, five SIGKILL phases, current authorization
rechecks, indeterminate outcomes, actual generated-consumer consumption,
implementation move and fresh-approved rollback. The consumer lifecycle composes
two independent graph shards, captures both shard files and the implementation
source, checks a chain derivation, applies an explicit unknown-identity policy
and evaluates a complete cost-three risk budget. A zero-budget control refuses
before publication. Actual CLI inspection and repair must leave the protected
manifest unchanged. **None of these host tests has executed on Linux.**
The official Rust 1.99 bookworm image was selected, but Docker's image store
reported I/O failures after disk exhaustion and still cannot list containers.
Only task-owned build cache was reclaimed. Restart approval remains pending
because restarting Docker Desktop can interrupt unrelated containers.

`scripts/test_linux.sh` performs disposable offline build, all-target Clippy and
serial tests against the actual production activator binary. After a healthy
runtime is available, it must run, followed by Linux source/native installation
and consumer checks. SIGKILL tests would establish process-crash behavior;
power-loss durability and arbitrary network filesystems remain separate claims.
Until these gates pass, R7 and R11 remain incomplete and the goal stays active.
