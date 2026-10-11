# R9 adapter and distribution draft

The implemented package adds explicit workspace discovery, generation and read-only drift
checking. Admission, projection and replay use the same Rust kernel.
Acceptance requires a native portable-shard path without Node, refusal of source
escapes and malformed process responses, unchanged baselines after drift checks,
cached/uncached equality, and independently installed Rust, Python and TypeScript
consumers outside this checkout.

The process protocol supplies bounded UTF-8 source contents, exact byte receipts,
configuration and a request digest. The host fixes an absolute executable and an
argument vector; it does not interpolate a shell command. Responses must echo the
exact request and input receipts, provide a closed draft shard and diagnostics,
and fit declared output and time bounds. The executable and declared code inputs
are fingerprinted. Neither this protocol nor those fingerprints sandbox an
arbitrary provider or establish completeness of its dependencies. External
process results are therefore rerun on every generation and check. They are not
accepted from cache. Discovery claims do not confer ownership or signing grants.

Portable-shard cache entries are untrusted: every hit is compared with the exact
shard decoded from the current captured source. Cache keys include profile,
compiler identity, complete configuration and source bytes. Cache status is
operational metadata and cannot change semantic output. No cache supplies trust,
current time, active state, or evidence absent from the inputs.

MetaMap's pinned TypeScript/Zod, Next.js and simple exporters can be invoked by an
optional Node bridge. The bridge writes only supplied sources into an isolated
temporary tree. Legacy envelopes are converted explicitly and original bytes
remain receipts; unsupported fields reject in Rust rather than being dropped.
Node and the pinned discovery package are optional dependencies of that bridge.

The initial Rust SDK distribution is a complete source workspace, containing
Cargo.lock, the toolchain declaration, crates, packs, schemas and notices. Its
embedded source identity uses files across crate boundaries, so individual
crates are not claimed as independently publishable crates.io packages. Native
binary bundles record the actual target, toolchain, features and file hashes;
source identity alone is not binary authentication. Thin Python and TypeScript
wrappers invoke the same installed native CLI without a second semantic engine.
Packaging and disposable installation tests do not publish or activate anything.

The nine-crate source bundle also includes consumer templates, test drivers and
acceptance records. Historical distribution/source archives remain beside the
repository records. The final installation receipt identifies both archives and
is kept outside those archives to avoid a recursive inventory. Source installation
uses the complete workspace; the native archive supplies the CLI, license,
attribution and its distribution receipt. No protected activator installation is
included in the macOS archive.

The Linux native bundle may additionally contain the separately tested fixed
activator. Its byte digest is explicit in the distribution receipt. Bundling
does not perform owner installation, trust bootstrap or activation; actual
protected-host acceptance is recorded separately. The installation harness
records the actual operating system rather than inheriting a macOS label.
