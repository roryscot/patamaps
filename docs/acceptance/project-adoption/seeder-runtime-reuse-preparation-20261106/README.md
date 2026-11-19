# Seeder retention measurement and copy-free runtime preparation

The canonical read-only inventory measured 99,754,368,560 retained
bytes under the 100 GB ceiling. Current headroom is 245,631,440 bytes.
A staged 800 MB run therefore needs about 554 MB more headroom. The
prior 300 MB run was admitted and then stopped after 654 MB of
conservative growth.

A private exact inventory identifies 24,720 ordinary files in ten
finished runtime copies. They account for 757,227,520 allocated bytes.
All files matched their original selected artifacts by SHA-256.
Three sample restores checked bytes, mode and modification time.
The accepted selected state and the focused Mobile Chrome runtime
are recovery and reuse sources. Full original-path restoration
has not been exercised. The exact inventory stays private; its
digest and aggregate proof are in [the review](review.json).
No deletion has occurred.

A separate checker matched all 2,472 files in the retained, accepted
Mobile Chrome runtime to the selected artifact manifest. A Darwin
sandbox fixture allowed reading the protected directory and writing
private state while denying writes to the protected directory.
The staged Safari launcher uses that runtime instead of copying
another 75,722,752 bytes and rehashes it before and after use.
Python compilation and JavaScript syntax checks passed. The live
Next runtime, Safari cases and full browser matrix remain unrun
in this staged reuse scope.
