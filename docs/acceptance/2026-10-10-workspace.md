# Native workspace and inspection checkpoint

Date: 2026-10-10. This is an uncommitted implementation checkpoint, not a public
release or production activation. The full R0–R11 goal remains active.

R7 implements the fixed Linux host, native lock, protected descriptor-relative
storage, complete immutable publication, current authorization rechecks, retry,
fresh rollback and root-owner trust administration. Linux tests compile under
the official `aarch64-unknown-linux-gnu` Rust target. No Linux runtime test has
passed: Docker image preparation failed with image-store I/O errors after disk
exhaustion. Only project-created incremental build cache was reclaimed. Docker
still cannot list containers, and restart approval is pending because other
containers could be interrupted. Permission, crash and power-loss acceptance
must not be inferred from macOS tests or cross-target compilation.

R8 adds finite explicit repair, conservative proposed approval requirements,
scope protection, work/time/output limits and cancellation. Its checked captured
explanation drives both JSON and escaped offline HTML. Actual CLI checks preserve
rejected and viable records and leave inputs unchanged. The browser provider
refused direct `file:` navigation; interactive keyboard/navigation QA remains
pending. See [rejected export](inspection-rejected.html), [viable export](inspection-viable.html)
and [native report](inspection-native.json). These are synthetic test data.

R9 adds portable shards, explicit bounded process invocation, exact receipts,
retained discovery shards/configuration, generate/check, untrusted portable cache
verification, source SDK bundles and thin Python/TypeScript transports. The
optional bridge reuses pinned MetaMap discovery code, with actual TypeScript/Zod
discovery tested. External processes rerun; no complete arbitrary dependency
closure, sandbox or cache speedup is claimed. Other bridge adapters remain to be
covered by the full conformance matrix.

Actual successful commands on macOS aarch64, Rust 1.99.0, default features, using
`CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0`:

```sh
cargo fmt --all
cargo test --workspace --locked --offline
cargo clippy --workspace --all-targets --locked --offline -- -D warnings
cargo clippy --workspace --all-targets --locked --offline --target aarch64-unknown-linux-gnu -- -D warnings
cargo build --workspace --locked --offline
python3 scripts/test_inspection.py target/debug/bindloom docs/acceptance
node scripts/test_schemas.mjs /Users/admin/dev/SEEDZ/metamap target/debug/bindloom
node scripts/test_governance.mjs target/debug/bindloom /Users/admin/dev/SEEDZ/metamap
python3 scripts/package.py --binary target/debug/bindloom --output .tools/distribution-r9-final
python3 scripts/test_distribution.py .tools/distribution-r9-final --node /Users/admin/.nvm/versions/node/v22.16.0/bin/node --tsc /Users/admin/dev/SEEDZ/metamap/node_modules/typescript/lib/tsc.js --reference /Users/admin/dev/SEEDZ/metamap
```

The full macOS run passed **85 tests and 10 compile-fail documentation tests**.
After retaining raw discovery shards and adding aggregate workspace bounds, the
six workspace tests and workspace build were rerun successfully. Schema and
independent WebCrypto controls passed at this checkpoint. The final disposable
installation verified source inventory and packaged binary hash, rebuilt the
native CLI from the extracted source bundle, compiled an independent Rust SDK
consumer, executed actual generated Rust and TypeScript bindings, imported both
installed wrappers, refused read-only drift without replacing the baseline, and
ran a portable flow with Node absent from PATH. This also caught and repaired an
ordinary-integer wire decoding error; the original failed run is not a pass.

Compiler source identity: `sha256:df19c48400080f74ccf4367c3ee823bebd15f962ae32f15f81f44315d2cb4357`.
Workspace source identity: `sha256:6361a1aa51aa81453706feb2de1524a27ca1ced7f4391278cf18e656da6cb5ec`.
Native binary digest: `sha256:a095c06970c6a1fbae8bfb149a5073b2608a90f71e43cf800aeadcac8280fdaf`.
[Distribution receipt](workspace-distribution.json) records the exact unpublished
archives and toolchain; [source inventory](workspace-source-inventory.json) binds
their contents. Later source changes invalidate these source identities for new
captures. Prior acceptance archives remain historical evidence.

R10, R11, complete 53-suite/22-binding reference acceptance, Linux runtime/package
acceptance, debugger interactive QA and exact final candidate packaging remain
required. No independent review, performance advantage, public release or
production activation is claimed.
