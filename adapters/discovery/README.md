# Patamaps discovery draft

This optional Node package discovers Prisma, TypeScript/Zod, Next.js App Router,
configured JSON collections, legacy source catalogs, SSSOM TSV sources and portable MetaMap graph shards. It contains the pinned
Apache-2.0 fact parsers extracted from MetaMap 0.7.1, with their public discovery
classes and type declarations. `provenance.json` identifies every original and
extracted file. The package declares TypeScript 5.9.3, Ajv 8.20.0, ajv-formats 3.0.1 and the Patamaps native SDK 0.1.0 and does not load a MetaMap
package. Admission, ownership, proof, policy and governance stay in Rust.

The `./process` entry accepts the Patamaps captured-input process protocol on
stdin. Configure an absolute Node executable and this entry in a workspace
invocation, and include the actual provider/helper/tooling files in its
`codeInputs`. The host clears the environment and verifies request/input
binding. Process caching remains disabled while complete provider dependency
closure is unproved.

The process validates source receipts before staging and requires configuration
paths to stay within that captured tree. It retains each staging directory under
the caller's working directory as `.patamaps-discovery-*`; removal requires the
owner's explicit approval. Direct discovery classes retain the original
filesystem API and use the caller's repository root.

These are seven discovery workflows. The complete seven-adapter, workspace and
installed replacement parity gates remain separate acceptance work.

The shard adapter uses Ajv only to check the unchanged pinned graph shape.
Its sole code relocation makes that schema URL local to this package. Unknown
relations and policy decisions remain the composed Rust workspace's responsibility.
The original MetaMap 2.0 graph envelope is accepted by this optional provider;
the native portable-shard path accepts the Patamaps graph envelope directly.

Scientific discovery uses the Rust parser, source-config validator,
interpretation and canonical digests. Call `configureDiscoveryNative` with an
absolute Patamaps executable before using `SssomTsvAdapter` directly. For the
captured process, pass `--native /absolute/path/to/patamaps` after the process
entry. Include the SDK and fixed profile data in the declared code inputs as
well as the provider code. The current process request remains bounded at
16 MiB; component parsing at 64 MiB does not establish that full workspace
workflow. Process caching remains disabled because the native helper's full
dependency closure is still an acceptance obligation.

The package also connects the native SDK's legacy workspace API to the built-in
adapters. `configureDiscoveryNative` selects the Rust executable for workspace
assembly, cache decisions, snapshots, validation, baseline comparisons and file
outputs. `discoverLegacyWorkspace`, `checkLegacyWorkspace` and
`writeLegacyWorkspaceOutputs` are exported from this package. A caller can use
`LegacyAdapterRegistry` to supply its own adapter callbacks; the original
configuration and shared context reach those callbacks unchanged.

Use `loadLegacyMetamapConfig` from `patamaps-native-sdk-draft` to load the
original configuration shape. Discovery defaults to reading and writing caches.
Pass `{useCache: false, writeCache: false}` for discovery without cache writes.
Checking compares against the configured graph baseline. Writing outputs is an
explicit call and replaces the four configured files. This compatibility
workflow observes legacy graphs; it does not activate a native generation.

The SDK declares this provider as an optional peer dependency. Pure assembly,
snapshots, checks with caller-supplied adapters and custom registries can use the
SDK directly; default built-in discovery requires this package. Full public
contract, package replacement and platform acceptance remain open.
