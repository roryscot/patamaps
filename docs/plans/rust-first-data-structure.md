# Rust-first data structure and library refocus

Status: active implementation plan. This is the current product direction for
new work. The prior MetaMap capability record remains historical evidence; the
integration-enhancement backlog remains separate.

## Goal and boundary

Make Patamaps useful first as an in-process Rust data structure for representing
and querying stable semantic identities and their explicitly typed
correspondences. A Rust consumer must be able to create a graph in memory,
check it, find its entities and mappings, and traverse relationships without a
CLI, generated files, Node, a browser, network access, or an application build.

A graph's data and its validation status are distinct. Constructors create
draft records; the existing checked graph remains the authority for validation.
Never silently infer domain meaning, authority, provenance, trust, or approval.
The public data structure should be approachable without hiding when additional
relation definitions or explicit provenance are required.

## Reuse and optional layers

- Reuse the typed graph, entity, mapping, provenance and relation-pack records in
  patamaps-contracts; preserve existing serialization and stable identities.
- Reuse CheckedGraph validation, indexes, lookups, trace, impact, composition,
  and existing diagnostics in patamaps-core. Preserve checked immutability and
  semantic/security invariants; do not make invalid records appear checked.
- Keep projection, scientific adapters, governance, CLI, activator, workspace
  capture and build/watch tooling as separately usable layers. They are not
  prerequisites for the core in-process example. Existing consumers, wire
  formats, parity evidence and operational safeguards remain intact.
- Keep Next.js/browser/deployment and scheduler qualification in the separate
  integration backlog. Do not expand those qualifications to gate the library.
- Do not discard historical data or existing features as part of this refocus.
  Consider retirement only after a separate usage, migration and deletion review.

## Milestones and acceptance

1. **In-memory on-ramp.** Provide explicit, documented draft constructors for
   the existing model and an executable Rust consumer example. It must create
   entities and a correspondence in memory, supply relation semantics and
   provenance, validate, look up and traverse the graph. Tests cover a valid
   relationship and rejection of duplicate identities and missing endpoints.
   No CLI, fixture JSON, app, filesystem or network is required at runtime.
2. **Library usability.** Audit and improve lookup, iteration and error
   ergonomics with external-consumer tests. Define mutation/edit semantics before
   adding a mutable API: failed edits must not corrupt the last checked graph.
   Document ownership, ordering, limits, and which records are unchecked.
3. **Dependency and packaging boundary.** Measure the actual minimal consumer
   dependency tree and compile footprint; separate optional dependencies only
   where evidence and compatibility support it. Verify a fresh consumer using
   the library without installing the CLI or application tooling. Do not claim
   a smaller or faster library until measured.
4. **Compatibility and integration.** Retain existing contract and kernel
   tests; verify public/wire compatibility for changed records. Demonstrate an
   existing Rust application using the library directly, without making
   Next.js, browser tests, deployment or performance targets a prerequisite.
5. **Docs and release.** Make the library-first guide the primary entry point,
   clearly distinguish optional tools, document versioned migration, and
   publish only after independent package and consumer verification. A release
   is a separate action; this plan does not assert one occurred.

## Execution and reporting

Work on Norway using the existing storage and exclusive scheduling limits.
Use focused tests before broader checks, retain failures, and commit and push
coherent milestones. No deletion or storage-policy change is authorized by
this plan. If a build cannot be admitted, preserve the implementation and
report the exact limitation rather than presenting unrun tests as passed.

## Current checkpoint, 2026-11-28

The in-memory graph on-ramp, checked editing, relation lookup and named error
accessors are implemented. Native-only and default focused tests passed on
Norway; the [registry fix CI](https://github.com/roryscot/patamaps/actions/runs/46104931415)
also passed in-memory and freshly packaged-crate checks at source `303c9f5`.
The exact-import registry fix accepts a complete native pack set in either
order; incremental registration and the separate legacy snapshot retain their
existing rules.

A [fresh-target native-only consumer measurement](../acceptance/library/native-consumer-footprint-norway-20261127.json)
ran on Norway with cached registry sources. It is a single measurement, not a
comparative benchmark. A [limited alpha wire comparison](../acceptance/library/alpha-wire-compat-20261127.json)
passed for the listed fixtures and rejection cases; it is not a universal
compatibility proof. A scoped existing Rust application was tested with an
earlier Git revision on hosted Intel macOS, not through its graphical UI; the
newer pinned Git revision's exact fetch has not been independently exercised.

The [library guide](../guides/rust-library.md) and
[migration guide](../guides/rust-library-migration.md) describe usage and
limits. The local `0.1.0` archives in the [archive record](../acceptance/library/local-crate-archives-20261127.json)
predate the registry fix and are not current candidates. No `0.1.0` core or
contracts release has been published. Publication is a separate action. The
original project-adoption goal remains open in the
[integration backlog](integration-enhancement-backlog.md); its broader gates
are not prerequisites for the in-process library.

## Historical checkpoints

The tracker carries a separate unfinished integration objective. The user's
newer Rust-first direction is recorded here and remains the product priority;
the integration objective is not marked complete. The first draft constructors, in-memory example, and focused tests are implemented.
An initial Norway run was refused before compilation because retained allocation
was 101,480,141,409 bytes against the 100 GB cap and 500 MB reservation. That
refusal is preserved; later Linux and Norway outcomes are recorded below.

After the approved 90,000-file cleanup, the focused run was admitted but stopped
before tests completed because shared-pool free space fell beyond the 500 MB
allowance. The guard retained its reservation after a permission error; repeated
process/container checks supported recovery of that reservation only. The failed
run is preserved, no policy changed, and the library tests and example remain
unverified. Shared-pool movement is not proof of which process consumed space.

A second Norway attempt was also stopped by the unchanged 500 MB guard after
shared free space fell during the admission scan. Its stopped reservation was
recovered after ownership checks and its failure retained. Existing Linux CI
compiled the core as a dependency; focused example and test coverage has been
added to CI but must pass before it is claimed. Norway verification remains
separate.

Linux CI passed the initial focused in-memory tests and example at a48726a.
An explicit clone-and-recheck edit method and failure-isolation test passed
in the later Linux CI run at 760378b. Norway results remain separate from
Linux CI.

A standalone path-dependent Rust consumer has been prepared for CI. The first
lockfile generation attempt could not find rustc because PATH omitted the
pinned toolchain; repeating with that toolchain in PATH succeeded offline. No
compilation occurred in that attempt. The standalone consumer passed Linux CI at 760378b; Norway execution remains unverified.

The Linux run at source 760378b passed three focused in-memory tests, the
in-memory example, the standalone path-dependent consumer and the existing
60-test workspace library suite. A Norway cargo tree inspection found 108
normal dependency package identities beneath the standalone consumer on the
host default target; this excludes the consumer itself and does not measure
compile time, binary size, all targets, or build dependencies. Reducing that
footprint remains a separate measured design task.

A default-on legacy-compat feature is being introduced so existing consumers
retain their current API while a native-only consumer can disable legacy
compatibility. On Norway, offline cargo tree reports 30 normal dependency
package identities beneath the standalone consumer in native-only mode, down
from 108 with defaults, on the same host target and counting method. These are
dependency-tree counts, not compile-time, size, or performance measurements.
Both configurations and the standalone consumer passed focused Linux CI at
e4ccd68. The legacy pack and registry regression tests and existing workspace
library suite also passed. Those Linux results do not establish a release or
broad compatibility.

The first locked consumer tree inspection refused because the new feature
selection required a lockfile update. The consumer lockfile was updated offline;
subsequent locked tree checks succeeded. This was a dependency-resolution
refusal, not a completed build or a library test result.

On 2026-11-25, the focused native-only in-memory library tests passed on
Norway at source 4a2024d: four tests, using the existing 500 MB guarded
reservation. The compiler reported that optional debug-symbol stripping failed
because rust-objcopy could not load libLLVM; the test command exited zero.
The earlier storage-guard failures remain preserved. This result does not
verify the default-feature configuration, a published crate, or a real Rust
application on Norway.

The standalone path-dependent Rust consumer also compiled and ran on Norway
on 2026-11-25 under a 500 MB guarded reservation. It checked and edited its
graph. The same debug-symbol stripping warning appeared. This is an example
consumer, not verification of a published package or an existing application.


The relation-index iterator and its consumer coverage were added on 2026-11-25.
The first Norway check stopped before tests completed after the 500 MB
shared-pool growth guard fired during admission; its reservation was retained
after ownership stop could not be confirmed by the guard. Normal recovery
refused incomplete ownership. The failed run remains preserved; no test pass
is claimed until separate verification completes.

Linux CI subsequently passed the relation lookup in default and native-only
focused tests, the standalone consumer and existing regression checks at
source f89d278. [Receipt](../acceptance/library/relation-lookup-linux-f89d278.json).
This does not resolve Norway's retained reservation or verify a published package.

Both Linux native-acceptance architecture jobs passed at source fa2c452 after
scoping the imported example's dead-code allowance to the test module. The
earlier failures and the separate Norway reservation remain. [Receipt](../acceptance/library/clippy-fix-linux-fa2c452.json).


A later read-only recovery diagnostic preserved the ownership predicates and
stopped before lease release. Its exact process snapshot identified a newly
started Docker CLI child of Docker Desktop as the project-command match; token,
open-project-file and matching-container counts were zero. The match appeared
in the process command/environment listing, but its relationship to the held
workload is not established. Earlier recovery refusals remain preserved, the
reservation remains held, and no service or safeguard was changed.


The held native reservation was subsequently released after the original
scoped recovery passed three complete ownership checks, including its final
locked check. The failed guard and original request were archived; the
unrelated database remained running. This recovery did not turn the earlier
interrupted Norway library tests into a pass.

A later Norway retry passed all five native-only in-memory library tests,
including relation lookup, and the standalone path-dependent consumer. Its
500 MB reservation released; the debug-symbol stripping warning persisted.
The earlier guard failure remains preserved. This does not verify a published
crate or an existing application.

On Linux CI at source 5612baf, fresh local 0.1.0 archives of core and contracts
passed default and native-only extracted-package consumers, focused core tests,
and contracts tests. The consumer resolves contracts through a local Cargo
patch to the extracted archive. Neither current crate was published. Norway
admission for the candidate was refused by the existing retention limit; the
CI result does not turn that refusal into a Norway pass.
