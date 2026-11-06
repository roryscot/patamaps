# Prelaunch disk-growth check

The failed Linux source inspection recorded a 334,585,856-byte physical
pool drop between the initial capacity witness and the witness immediately
after the retention scan. Owned-volume accounting stayed the same. The
worker opened its mount log after the second witness. These observations
place the pool drop before the mount. Its cause remains unknown.

The previous staged native guard applied the startup free-space threshold
after scanning retention, then first enforced the job growth allowance in
the running child's monitor. The two-line [candidate patch](prelaunch-growth.patch)
checks the same growth and reserve limits again immediately before spawn.
The original baseline, limit and ownership checks still apply.

An isolated scheduler fixture with a real shell child reproduced the
spawn, budget stop and retained lease when a pre-existing container was
represented in the injected inventory. The candidate refused both an
inventory-time loss and a container-snapshot-time loss before spawning.
The exact growth boundary and unchanged capacity both allowed the command.
A follow-up request queued and released on the same isolated scheduler
after the refusal. The baseline and candidate runs of probe.mjs and the
requeue-probe.mjs run produced the [recorded results](review.json).
The probes use a baseline and patched copy in adjacent fixture directories.

The shared installed guard was not changed. The original failure and both
pending approvals remain separate from the fixture results.
