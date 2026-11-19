# Managed Miniserve deployment generation replay on Norway

Norway replayed the exact selected state and creating compiler from the
[Linux qualification](../miniserve-deployment-generation-20261106/README.md)
inside its existing managed executor. The stale key for the intended
9101 listener returned exit 2 and no runtime probe directory was
created. The selected 9100 key ran the actual Miniserve executable and
passed all eight HTTP and startup checks. The selected pointer and
post-execution artifact bindings matched.

The run used one CPU, 256 MiB of memory, zero swap, a read-only root,
no external network and a single writable quota mount. The independently
checked quota filesystem was 66,019,328 bytes. Kernel limits matched.
All 49 imported files were rehashed and checked before execution, after
stale refusal and after the successful probe. The owned container and
host process group stopped, both reservations released, and the unrelated
database retained its start identity.

The [earlier capacity stop](../miniserve-managed-generation-capacity-20261106/README.md)
is preserved. After the [byte-preserving recovery](../five-closed-images-allocation-recovery-20261106/README.md),
the executor created a stopped quota workspace. The first import into
it failed because the archive omits explicit parent directory entries.
The workspace still contained only the executor's four empty directories.
A fresh guarded preparation verified its identity, created the missing
parents and imported the same archive directly into that same workspace.
The initial import failure remains in the private evidence.

This verifies the current generation guard against a real Rust service
on Norway. The 9101 generation was observed in CI and did not execute.
Production activation, private owner deployment and performance
qualification remain separate.
