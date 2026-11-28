# Wargame lab browser preservation and PostgreSQL 18 prerequisite

On Norway, the original Wargame Playwright config and both original
spec files ran against the retained production Next build and Rust
API, with 11 desktop and 11 narrow cases passing. The same pinned
Chromium headless shell was reused. Wargame's candidate guard exited 0.

The [previous browser run](../wargame-owner-browser-20261106/README.md)
passed the same cases but failed the wrapper's whole-tree check when
Next created route-cache files. This run moved the prior route-cache
directory to a fresh retained location before starting the services.
It started from an empty cache and retained the 24 new cache files
separately after the services stopped. It then restored the prior cache
at its original inode and path. An independent review matched all
2,820 retained Next tree entries, 111 frozen inputs, the Rust API
binary, Next build ID and generated-bundle pointer. The reservation
released and the unrelated database retained its start identity.

A separate guarded prerequisite verified the [Postgres.app 2.9.6
release](https://github.com/PostgresApp/PostgresApp/releases/tag/v2.9.6)
archive against GitHub's SHA-256, checked its signature and executed
six Intel PostgreSQL 18.6 tools from a read-only mount. A fresh
socket-only cluster passed an actual dump-and-restore round trip.
The cluster stopped and the image detached. The image, fixture data
and dump remain retained. This prerequisite exercised the database
tools with synthetic data. The original owner's native persistence and
managed browser suites have their own acceptance records.
