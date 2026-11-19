# Fresh-directory metadata attempt: refused before database initialization

Run on Norway on 2026-11-04 under the owner's autonomous continuation instruction.
All425 frozen bindings matched before and after execution. The Docker archive
metadata operation returned0, but the independent in-container guard printed:

    PATAMAPS_DATA_OWNER process=501:20 data=0:0 mode=700

The guard therefore refused before invoking the original PostgreSQL entrypoint.
The new data directory remains empty. No migration, seed, HTTP authentication or
browser case ran. This is a failed candidate correction, not an accepted fix.

The independent review verifies the actual failed supervisor/guard, released
reservation, stopped owned container/attachment/group, bounded private streams,
93 preserved previous failure files, required ports closed and unchanged unrelated
database identity. Resource limits and acceptance assertions are unchanged.
No deletion or service interruption occurred.

The owner now authorizes implementation and checks until final review; see the
[continuation scope](../../../../plans/2026-11-04-adoption-closeout.md).
A distinct next attempt will use a new labelled Docker-managed data volume and
create a fresh UID501:GID20 subdirectory before startup. This changes only owned
test storage; it does not modify an existing database or run the server as root.
The actual guard and both TCP readiness checks still must pass.

Docker's [volume documentation](https://docs.docker.com/engine/storage/volumes/)
describes Docker-managed persistence separately from host bind mounts. Its
[copy documentation](https://docs.docker.com/reference/cli/docker/container/cp/)
describes archive UID/GID preservation. Neither establishes that the next
candidate works on this host; runtime verification remains required.
