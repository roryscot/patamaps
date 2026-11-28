# Byte-preserving recovery of a closed preparation image

A quota preparation that ended before container creation left a closed,
fully allocated image. The scheduler's historical stop proof and a fresh
mount, open-file and container inspection confirmed it was unused. A
read-only survey found six allocated ranges containing only zeros.

The guarded recovery passed three filesystem controls, rechecked every
target block before and after releasing its allocation, and journaled
each range. An independent review rehashed all 133,169,152 logical bytes
and checked file size, inode, owner, mode, the closed state and the
unchanged historical failure. The image keeps the same SHA-256. Summed
allocation fell by 133,099,520 bytes. The native reservation finished
and released. The unrelated database kept its start identity.

The resulting nominal headroom is about 260 MB, based on the admission
inventory and observed allocation change. Safari still needs about
540 MB more for its frozen reservation. The managed Linux runtime
job also needs additional room. A fresh admission scan must verify
either job. No files were deleted. [Independent review](review.json)
