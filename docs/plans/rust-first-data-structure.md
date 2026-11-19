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

## Current checkpoint

The existing tracker contains a paused, unfinished integration goal and cannot
replace it through the available goal API. The user's new direction is recorded
here; the integration objective is not marked complete. The first draft constructors, in-memory example, and focused tests are implemented.
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
