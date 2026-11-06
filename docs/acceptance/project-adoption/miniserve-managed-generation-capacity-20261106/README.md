# Managed Miniserve generation replay stopped during preparation

The first Norway preparation used an incorrect repository-relative tool
path. It exited before downloading the archive or creating a workspace,
and its ordinary reservation released. The corrected attempt used the
same Linux CI artifact, verified it in memory and checked that the exact
compiler and selected state total 45,143,024 bytes. It did not write an
extra archive or intermediate selected-state copy.

The native supervisor admitted the corrected attempt under a
96,000,000-byte reservation. It then charged 105,111,552 bytes of growth
while the managed executor was still preparing admission. Every recorded
owned-volume sample showed the same count and byte total. The charge
includes physical-pool changes, so the source of that growth is unknown.
The guard recorded exit 75 and the supervisor exited 1. No managed
request, quota workspace or container was created. The Miniserve
stale-key and matching-key cases did not run on Norway.

The lease remained held after the supervisor could not confirm shutdown.
Early stop inventories detected the observation process itself. Running
the observer from outside the project with a minimal environment allowed
three complete checks with zero matching processes, open files or
containers. The exact stopped reservation released. The original guard
failure, 19 frozen inputs and unrelated database identity were preserved.
No files were deleted.

The [real Linux CI result](../miniserve-deployment-generation-20261106/README.md)
remains the current end-to-end evidence for this deployment control.
Managed replay on Norway needs enough retention headroom for a preparation
reservation larger than this observed stop.
