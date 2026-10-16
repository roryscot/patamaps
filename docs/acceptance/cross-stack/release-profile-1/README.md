# Accepted cross-stack profile 1

[M0–M7 and X01–X20](receipt.json) passed for the pinned fixture at source
6047fb6dc6c917028de271b77128c9ec6717e5de.
[CI 38827441367](https://github.com/roryscot/patamaps/actions/runs/38827441367)
completed successfully: Linux x86_64 and ARM64 native regressions, source bindings,
and the required Linux-amd64 image/browser/installed-consumer lane. The Intel
[native gate](../final-native/receipt.json) passed separately through the unchanged
storage supervisor. No registry or production activation occurred.

| Evidence | Executed result |
| --- | --- |
| [Source admission and offline replay](linux-source.json) | 14 controls; newly discovered unmapped leaves refuse; relocated inputs, lock lineage and rehashed substitution checked. |
| [Preview/watch](linux-development.json) and [Intel](../m5-development/receipt.json) | 13 controls on each host; previous selection remains usable after actual Cargo failure; complete atomic generations and cancellation verified. |
| [Linux image](linux-image.json) | 21 controls; actual BuildKit/Cargo/ELF, inspected config/notices/image identity, HTTP, browser, negative images and native evidence refusals. |
| [Chromium](browser.json) | Real form POST201/500, delayed hydration, colon/literal-percent/Unicode detail routes and no page errors. |
| [Pinned MetaMap comparison](metamap-image.json) | 10 controls using actual release observations; unchanged 610 tracked reference files; fresh conversions and real evaluator. |
| [Exact Linux installation](linux-installed.json) | 14,197 installed source files verified, exact native binary/engine identity and full mixed workflow repeated. |
| [Runtime after compiler removal from its configured path](installed-workflow.json) | Actual generated app still runs after the test installation's compiler is renamed and graph compilers are absent from its request path. Bytes remain retained. |
| [Plan controls](x01-x20.json) | Each of X01–X20 points to actual controls or selected passing unit log entries; no owner disposition replaced a required check. |

Actual argv, exit codes, timing and stream hashes are in these raw receipts.
Native commands included cargo fmt --all -- --check; cargo clippy --workspace
--all-targets --locked --offline -- -D warnings; cargo test --workspace --locked
--offline; cargo test --workspace --doc --locked --offline; and cargo build
--release --workspace --locked --offline. The native discovery22, binding20 and
Docker-observation23 matrices, installed preview and seven-provider checks also
passed. The first direct adapter invocation omitted its existing runner and
failed before any controls; the journal and successful retained-runner retry are
both preserved in the native gate.

The Linux workflow ran scripts/ci_cross_stack.py with source, development, image,
compatibility and installed phases. [Run/artifact metadata](ci-run-summary.json)
identifies the exact source and successful jobs. Small diagnostic ZIPs were
[downloaded and SHA-256 checked](diagnostic-artifact-retrieval.json) on Intel;
[full source, image and architecture archives](full-archive-retention.json) are
retained on Intel with local hashes matching GitHub. The embedded
[owned-image archive](owned-image-archive-verification.json) was also hash-checked;
both accepted positive image IDs are present. Full restoration was not exercised.
Earlier failures, original expectations and assertion corrections remain in
m6-image-browser/ and the historical milestone records. In particular, detached
Docker startup can return success while its container log reports exec format
error; the accepted architecture check requires that causal runtime diagnostic
and an independently rejected real AArch64 ELF.

Acceptance is for this fixed Next.js/Rust/Cargo/Linux-amd64 recipe and supported
string-object schema profile. Application ownership supplies meaning. Shared
portable discovery means matching engine decisions cannot disprove a shared
provider defect. A moved-handler comparison has source/Cargo evidence; its own
receipt does not pretend that variant rebuilt an image. Offline replay checks
recorded lineage rather than authenticating tool execution or rerunning Docker.
Arbitrary frameworks, macros, shell effects, rewrites, secrets and other image
platforms remain outside this accepted profile. Raw fixture timings do not
establish a performance advantage, and lockfiles do not prove independently
reproducible binaries.
