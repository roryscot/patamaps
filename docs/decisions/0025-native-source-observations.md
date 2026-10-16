# Native Cargo and TOML observations

The native provider extends the existing workspace process request/response envelope. It adds no source variant, admission shortcut or background service. Select the Patamaps executable with arguments [discover-native] in an ordinary process source. The workspace binds its executable bytes, invocation, inputs, response and source lineage. The adapter version is patamaps-native-observations-1; the workspace executor identity includes its implementation and pinned dependency context.

## Explicit nonsecret input contract

Both providers require nonsecretInputs=true. Supply only complete files the application owner explicitly declares nonsecret. A workspace capture retains the raw supplied bytes. Field selection limits emitted observations; it is not redaction of the raw capture. Do not supply a secret-bearing file merely because it parses. Missing or excluded required data remains unavailable.

For TOML, configuration is an object with provider=toml, nonsecretInputs=true, and files. Each file contains path and fields; fields is a nonempty list of key-prefix arrays. An explicit empty prefix selects the complete nonsecret document. Missing selected prefixes refuse. Keys use component arrays, so a quoted dotted key and nested dotted keys remain different. Array indexes occupy numeric components.

The pinned toml_edit 0.23.7 parser supplies raw UTF-8 key/value byte spans, typed strings and booleans, decimal-string integers, IEEE-754-bit float tags and datetime tags. Unsafe JSON integers, infinities and NaNs are never silently coerced into the native JSON number domain. Scalar lexemes and all raw input bytes remain available; container lexemes are not redundantly copied. Unavailable implicit spans are null. The tested value profile is TOML 1.0; the exact parser/transitive versions are identified by Cargo.lock, without a claim that every later lexical extension has been independently tested.

Limits include the existing 16 MiB combined workspace input bound, at most 1,024 provider inputs, 10,000 TOML observation nodes, depth 64 and an aggregate 8 MiB encoded TOML observation budget. Existing graph, metadata and output bounds also apply. Over-limit inputs refuse; observations are not silently truncated. Long repeated key paths have a separate amplification refusal test.

## Cargo observation contract

Cargo configuration requires manifest, workspaceManifest, lockfile, explicit absolute cargo/rustc paths and expected byte digests, an existing explicit cargoHome, platform, features, defaultFeatures and view. The views are declared-local and resolved. The declared workspace manifest must contain an explicit [workspace] table; implicit ancestor workspace selection is unsupported in this profile.

The provider invokes Cargo metadata with --format-version 1, --locked, --offline, the explicit manifest and platform filter, and declared feature flags. Declared-local additionally uses --no-deps and never claims resolved dependency features. Resolved retains Cargo's resolution output. Package IDs in Cargo metadata remain opaque; observed graph identities use namespace and normalized owner-relative locations. Raw tool output and exact physical receipts remain attributable when a checkout moves.

Manifests, lockfile and every applicable configuration/toolchain input inside the owner root must be supplied. Literal workspace members, inherited package/dependency declarations, renamed dependencies, conditional dependency declarations and multiple targets are covered. Glob members refuse. Local path dependencies outside the owner root or required uncaptured manifests refuse. Applicable Cargo configuration outside the root refuses without reading/copying its values. Cargo configuration accumulates along ancestors; only the nearest Rust toolchain file applies. An explicit channel must match the selected rustc release. Ambiguous or unpinned/mismatched toolchains refuse.

The initial Cargo configuration subset is matching build.target and net.offline=true. Other required configuration, including executable overrides, refuses. Each selected executable must be a regular file of at most 256 MiB and match its streamed digest. Tools run with a cleared environment and explicit Cargo home, rustc, PATH and offline setting through the existing timed process-group/pipe-bounded runner. Metadata stdout is capped at 4 MiB, stderr at 64 KiB and each tool stage at 30 seconds; the enclosing workspace invocation adds its own overall deadline. Missing offline inputs or failed tool resolution is unavailable, not an empty successful dependency inventory. Selected source bytes and tool digests are rechecked around observation. Process caching remains disabled.

Output distinguishes cargo-package, cargo-target and toml-key observations. Build scripts and procedural macros across resolved dependencies are inventoried as possible executable inputs, with explicit flags for workspace membership, captured source contents and observed execution. Declared-local does not claim a complete dependency executable inventory. Metadata does not establish their effects, successful compilation, selected Linux artifacts, packaging, runtime listeners or deployment. Explicit native tools are trusted local programs; this transport is not an OS sandbox. No complete executable/dependency closure or reproducible binary is inferred from a lockfile.

## Offline evidence and verification

The generic workspace generate/verify-workspace path is reused. Offline verification reconstructs captured record bindings and performs no source rediscovery, provider invocation or current authorization. Its success state is verified-record-bindings, with authentication, current authorization and activation explicitly not evaluated. Native Cargo discovery is tested through a real workspace capture and then replayed after moving the configured provider, Cargo/rustc aliases and required manifest to retained names, with external programs absent from PATH. A rehashed discovery-version substitution must fail composition binding.

Run the retained driver on Intel through the documented supervisor:

    python3 -B scripts/test_cross_stack.py --phase discovery

It executes native TOML/unit/process/workspace regression tests and independent real-Cargo controls. All fixtures, raw requests, commands, outputs, failures and deliberate offline-retention moves remain under .tools/cross-stack. M0's real application build/HTTP checks remain separate. M1 is not acceptance of generated registration, Docker, coherent publication, MetaMap interoperability or the complete cross-stack release.

The external contracts are [Cargo metadata](https://doc.rust-lang.org/cargo/commands/cargo-metadata.html) and the pinned [toml-rs parser source](https://github.com/toml-rs/toml). The new provider uses the existing native graph/workspace contracts and preserves all prior acceptance evidence.

M1's [scoped receipt](../acceptance/cross-stack/m1-native-observations/receipt.json) records 22 independent process controls, 10 native TOML tests and the full Rust workspace regression gates on Intel. Nested provider-child cancellation has not yet been established by these controls; it remains a required M5/X13 check before the whole development workflow can be accepted. The legacy direct process-group tests are not evidence for that additional nesting case.

## Opt-in standalone package roots

General project adoption adds rootMode=standalone-package to native Cargo configuration. The default remains explicit-workspace with its original required [workspace] table. Standalone mode requires manifest and workspaceManifest to name the same package manifest, with a [package] table, no [workspace] table and no package.workspace selection. Every ancestor Cargo.toml must be absent; existence or an unavailable metadata probe refuses before Cargo runs without reading ancestor manifest values. This bounds implicit parent-workspace discovery without changing the project manifest. The actual metadata workspace_root must still equal the declared root, and its Cargo.lock, applicable configuration/toolchain capture, tool hashes, offline/locked flags and byte rechecks retain their existing requirements. Standalone receipts identify rootMode explicitly. This does not add glob members or arbitrary Cargo config support.

The retained scripts/project_cargo_qualification.py driver exercises actual Wargame package metadata and verifies the original default still refuses. This is observation evidence only: it does not execute its build scripts, compile Axum, validate an API or qualify the application. Run it through the existing Intel supervisor with explicit native Cargo/rustc binaries and Cargo home.
