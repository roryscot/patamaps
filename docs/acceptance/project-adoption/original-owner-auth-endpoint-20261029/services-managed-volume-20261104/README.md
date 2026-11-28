# Docker-volume candidate refused before startup

On2026-11-04 the new labelled volume/container were created but remained
stopped: the exact identity-file mount assertion refused Docker's /host_mnt
path projection. No metadata setup, database initialization, migration, API,
HTTP case or browser case ran.

Read-only inspection copied only the two generated identity files from the
stopped owned container and verified their digests against the intended host
files. The public summary includes counts/digests only. The next candidate
admits only the exact host path or its /host_mnt projection, retains read-only
mounts and requires actual byte comparison before startup. Other paths refuse.

The first collector repeated the literal-path assertion and failed; its source
and failure are retained privately. The repaired review uses the verified
mount/content evidence without rerunning an application. It confirms failed
supervisor/guard1, released reservation, stopped container, preserved volume,
143 unchanged prior failure files, closed test ports and unchanged unrelated
database. No deletion, interruption, policy increase or acceptance occurred.

The source patches reconstruct the executed storage changes from the previous
[full data-owner runner](../services-data-owner-proposal-20261102/run.py).
The directory header is preparation evidence only; it was not applied in this
run. Raw reviews/authorization records remain private; review.json is an
allowlisted summary bound to its private original by SHA-256.
