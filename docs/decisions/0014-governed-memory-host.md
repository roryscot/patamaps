# Governed native memory activation

The pinned reference `governed-activation.test.ts` demonstrates a substantive
memory workflow: externally selected trust and time, exact signed artifacts,
state preservation on refusal, current authorization on identical retries,
stale-base refusal and freshly approved rollback. The legacy Rust transport
does not implement its governed overload, and the protected Linux host does
not provide this portable workflow. C11 therefore requires a native host.

Implement `MemoryHost` in the existing activator crate, reusing
`check_prepared`, `verify_approval` and the current proposal/artifact/signature
contracts. The owner supplies a context provider at construction. Requests
contain neither trust nor time; the provider fixes consumer, environment and
trust identity. Memory trust must have no Linux deployment binding. Read the
provider again and repeat authorization immediately before replacing state.
Exclusive Rust borrowing serializes transitions; no callback runs after that
last verification and before the assignment.

Use a distinct `patamaps-memory-draft-1` profile, manifest type and address
domain. Its source executor binds the memory implementation and existing
governance executor. Never label memory state as Linux protected persistence.
Expose immutable state and a typed activated/already-active result. A rejection
or host failure leaves the previous state intact. An identical retry rechecks
current trust/time against its original proposal baseline; a different change
uses the actual current state as its baseline. Rollback is a newly signed
proposal against that current state.

An untrusted memory manifest and complete file inventory can be reverified as
historical evidence using the recorded accepted trust/time. This cannot seed a
host or authorize publication under current trust. Checked state has private
fields and no `Deserialize` implementation. Manifest address, predecessor,
executor, signatures and all artifact bytes are rechecked before it is exposed.

Acceptance requires portable Rust tests for actual bootstrap/move/rollback,
rejection preservation, current retry/expiry/revocation, altered bytes,
manifest tampering, foreign executors, owner-context failure and changes between
preparation and commit. Include these tests in the compiler milestone and an
installed native consumer at the next package milestone. Original reference
tests and expectations remain unchanged. Implementation alone does not satisfy
acceptance, and this profile never substitutes for C12 Linux platform checks.
