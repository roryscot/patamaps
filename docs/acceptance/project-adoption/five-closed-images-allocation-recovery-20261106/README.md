# Byte-preserving allocation recovery in five closed images

The read-only survey inspected five previously qualified Patamaps quota
images after their owning requests finished. Their stopped container
identities, detached images, absence of open file handles and previous
whole-image digests were confirmed. The survey counted only aligned
4 KiB all-zero blocks within filesystem-reported data extents. The
reported data extent sizes agreed with each file's allocated size.

After the known filesystem fixture passed its three controls, the
guarded worker verified each of the 466 exact ranges was zero before
and after reclaiming its allocation. It recorded intent and completion
for every range. The independent review rehashed all 2,276,458,496
logical bytes and matched the image paths, inodes, sizes, ownership and
modes. Allocated size fell by 133,820,416 bytes. The image bytes and all
files were preserved.

The 64 MiB native reservation exited successfully and released.
The unrelated database kept its start identity. The review establishes
reclaimed allocation. Application admission and replay are measured
by their own later reservations.
