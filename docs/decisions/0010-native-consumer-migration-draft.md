# Separate native consumer migrations

The CreateUser routing consumer and MGI scientific lookup are independent Rust
workspaces. They have no Patamaps compiler dependency at runtime. Installation
copies checked static artifacts into disposable consumers, builds their real
modules and executes their native tests. No production consumer is modified.

The routing migration retains the original operation, schema, handler,
correspondence and owner fact IDs, policy declarations, environment selectors
and owned exclusions. The original JavaScript validator/service remain unchanged
as a behavioral shadow. Nine inputs include ECMAScript whitespace cases where
Rust's ordinary `trim` would change behavior. An explicit module map resolves
owned byte-checked Rust sources before ordinary Cargo export/type checking.

All 22 original scenario expectations remain intact in the frozen corpus and
are exercised through actual candidate builds or runtime calls. D002 serializes
JSON at the initial string-function interface. D008 maps only the old
`SHARD_COMPOSITION_CONFLICT` finding to `CONFLICTING_SHARD_DEFINITION` and the old
`STALE_PROJECTION_GENERATION` finding to
`PROJECTION_GENERATION_RECHECK_FAILED`. Both original expectations and complete
native findings are retained. These name changes do not make a refused candidate
usable. Rejected candidates leave the accepted consumer bytes unchanged.

The scientific migration reuses the original `lookup.mjs` unchanged through an
explicit target-table adapter. Every returned subject, target, relation and full
assertion matches the static Rust lookup; seven assertion IDs and distinct
duplicate-pair metadata survive. Consumer exploratory declarations and ordinal
costs do not become scientific evidence.

The staging helper is consumer-owned build tooling, not a general Rust scanner,
OS sandbox or protected publisher. Trusted local configuration supplies its
module map and Cargo inputs; its source receipts do not attest a complete
toolchain dependency closure. Graph ownership declarations are not host grants.
Protected implementation moves, unchanged IDs, fresh approvals and rollback are
separate Linux lifecycle tests. The complete consumer sequence composes independent
shards, captures their bytes, checks a chain derivation, tolerates unknown
identity only through explicit policy and charges the complete three-mapping
dependency closure once. Stricter evidence and budget controls refuse. Actual
CLI inspection and bounded repair leave protected state unchanged. The generated consumer
executes under UID 65534 after activation, the move and fresh-approved rollback.
The debug host tests and the separately built release executables pass on the
recorded ARM64 Linux/ext4 guest, including actual UID-65534 consumption after
activation, the implementation move and rollback. See the
[Linux native receipt](../acceptance/linux-vm/native-tests.json) and
[release-host receipt](../acceptance/linux-vm/release-host.json). Production
installation and activation remain separate adoption actions.

The shared fixture's portable stages passed on macOS: native proof/policy and
budget checks, exact capture/replay, actual read-only inspection/repair and
generated native dispatch. The portable result does not establish external
approval, host publication or the governed move/rollback sequence. Those
boundaries are evaluated by the separate Linux run. See the
[portable lifecycle receipt](../acceptance/lifecycle-pure.json).

See [binding results](../acceptance/native-binding-matrix.json),
[scientific results](../acceptance/scientific-native/acceptance.json) and the
[five legacy migration reports](../acceptance/legacy-migration/acceptance.json).
Legacy reports preserve raw original generations and record every changed
envelope, pack/graph binding and relative pack URI. They are fresh evaluations;
historical execution and approvals are not migrated.
