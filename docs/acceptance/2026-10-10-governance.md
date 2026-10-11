# Native governance draft verification

Verified 2026-10-10 on macOS arm64 with Rust 1.99.0 and Node 22.16.0. This extends the [semantic checkpoint](2026-10-10-semantic.md) with pure external approval verification. The complete R0–R11 goal remains active. Protected installation, activation, full conformance and public release are not established.

[governance-source-inventory.json](governance-source-inventory.json) identifies the actual uncommitted source and release binary, based on Git `ab6efc333a3c90f7ce9235822b49098809d8b159`. [governance-kernel.tar.gz](source-snapshots/governance-kernel.tar.gz) preserves source, tests, schemas, local fixtures and verification scripts. Source/binary identity does not establish reproducible builds or trusted installation.

Actual commands from the repository root:

| Command | Result |
| --- | --- |
| `/Users/admin/.cargo/bin/cargo fmt --all --check` | Passed |
| `/Users/admin/.cargo/bin/cargo clippy --workspace --all-targets --locked --offline -- -D warnings` | Passed |
| `/Users/admin/.cargo/bin/cargo test --workspace --locked --offline` | Passed: 70 integration tests and 8 compile-fail documentation tests |
| `/Users/admin/.cargo/bin/cargo build --release --locked --offline` | Passed |
| `/Users/admin/.nvm/versions/node/v22.16.0/bin/node scripts/test_governance.mjs target/release/bindloom /Users/admin/dev/SEEDZ/metamap docs/acceptance/governance-native.json` | Passed: independent WebCrypto signature over exact CLI file; agent, appended-newline and swapped-file refusals; approved Rust/TypeScript bindings execute; actual records validate against local schemas |
| `python3 scripts/reference/compare.py /Users/admin/dev/SEEDZ/metamap --cli target/release/bindloom --node /Users/admin/.nvm/versions/node/v22.16.0/bin/node --output docs/acceptance/reference-routing-governance.json` | Passed: 18 shared routing cases |
| `python3 scripts/reference/semantic.py /Users/admin/dev/SEEDZ/metamap --cli target/release/bindloom --node /Users/admin/.nvm/versions/node/v22.16.0/bin/node --output docs/acceptance/reference-semantic-governance.json` | Passed: 40 shared semantic cases |
| `python3 scripts/reference/differences.py /Users/admin/dev/SEEDZ/metamap --node /Users/admin/.nvm/versions/node/v22.16.0/bin/node --cli target/release/bindloom --output docs/acceptance/reference-differences.json` | Passed: two explicitly different expected outcomes, D005 and D006 |
| `python3 scripts/test_native.py --cli target/release/bindloom --tsc /Users/admin/dev/SEEDZ/metamap/node_modules/typescript/lib/tsc.js --node /Users/admin/.nvm/versions/node/v22.16.0/bin/node` | Passed: independently owned consumers across an actual module move, with meaningful type/semantic/output refusals |
| `/Users/admin/.nvm/versions/node/v22.16.0/bin/node scripts/test_schemas.mjs /Users/admin/dev/SEEDZ/metamap target/release/bindloom` | Passed: all local schemas compile; law fixtures and actual derivation validate |
| `/usr/local/bin/docker info --format '{{.OSType}} {{.ServerVersion}}'` | Failed: daemon unavailable; no Linux permission/crash acceptance performed |

Twelve governance tests cover exact inventories, readdressed reduced deltas, invalid/weak crypto, identity separation, joint action/fact scopes, explicit agent rebinding permission, owner-only changes, current time and full intervals, revocation, stale trust/base/environment, changed inputs/signatures, missing source bytes, multiple consistent projections and recursive untrusted outputs. Grant order uses UTF-16, including supplementary characters. Checked proposals and authorization capabilities cannot be deserialized. Production APIs accept no signing keys; the independent test uses ephemeral in-memory keys and records only public trust and signatures.

[governance-native.json](governance-native.json) retains the independent proposal, public trust binding, approval and inventory. The native CLI and Rust consumer ran with Node absent from `PATH`. Reference reports preserve all inputs and full engine results. [reference-differences.json](reference-differences.json) keeps both outcomes: literal parameter insertion in Rust and refusal of weak identity-point keys. The first hydration probe did not distinguish the engines; the corrected control accounts for the reference's longer-token-first replacement. These disagreements are not counted as shared equivalence.

An independent provenance audit passed: 82 preserved files match pinned Git bytes/hashes, all 53 suite hashes match, all 22 original case destinations remain, and the reference checkout is clean. Full successor coverage remains pending. No benchmark advantage, independent security review or protected host provenance is claimed. The verifier reports `authorized-under-supplied-context`; R7 must establish the actual root-owned trust/base/clock boundary and recheck at publication.
