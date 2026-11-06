# Original-owner watcher verification under the strict read-only profile

The installed watcher and compiler used by the earlier owner case were
rehash-checked. The compiler matches the native registrar's pinned
binary. Its existing one-attempt state, selected pointer and driver
lock were used directly.

The first preflight passed a dependency-injection argument available
in the checkout to the older installed verifier, which refused before
native launch. The corrected adapter routed the installed module's
subprocess calls through a closed check for the two expected argument
vectors. The first corrected run started the real verifier and hit the
preflight's 60-second timeout. Both refusals and their stopped-resource
reviews are preserved. The final run used the original owner watch
bound of 900 seconds per inspection.

Under a 128 MB native reservation, the pinned Python worker ran the
actual installed `verify_selected_step` through the strict Darwin
inspection profile. Both `project-build-verify` and
`project-build-input-key` completed. Their input keys matched the
selected generation. The installed watcher emitted its expected
nonce-bound selection record, and input observation ran no build
commands.

A separate verifier checked both native lifecycle channels and kernel
group stops. It rehashed 2,482 selected files and 943 source inputs,
verified the one selected attempt and driver lock were preserved, and
confirmed the protected database start identity and reservation
release. The guard and supervisor exited 0. Timings in the
[review](review.json) are observations from this qualification run.

The scope verifies read-only compatibility on the actual owner
selection. The registered controller still needs a closed operation
for the paired post-update checks. Full watch execution, actual owner
parent death, automatic registered release and changed-generation
lifecycle acceptance remain open.
