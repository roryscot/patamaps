# Owned Docker-volume accounting on Norway

The staged task adapter now charges exact retained bytes of Docker volumes labelled to this project, in addition to every original accounting root. The existing canonical guard, policy, fair queue, shared-output protection and native-exclusive fallback remain. Installed guard source and limits are unchanged.

[Independent review](review.json) verifies17 mock controls, bounded real metadata, actual256MiB admission and normal release, and unavailable metadata refusing before queue/worker. The positive job charged49,999,557bytes from two owned volumes in addition to97,041,559,552root bytes. All source inputs and the installed guard digest match. No application or unrelated service ran in these controls.

The capacity callback preserves the minimum actual free space and additionally charges positive growth on each root filesystem and in owned volumes against the same declared allowance. This intentionally may double charge Docker growth already reflected physically. Unknown data/identity or unavailable accounting refuses. Docker metadata is sampled at most1second old, with4second socket/5.5second process bounds; original monitor cadence and native cancellation fallback remain. This is conservative monitoring, not a hard native filesystem quota, container-output quota qualification or parallel activation.

The three helper/test sources and zero-context adapter patch are published for review. Raw Docker metadata, commands, service data and ownership records remain private. No file was deleted.
