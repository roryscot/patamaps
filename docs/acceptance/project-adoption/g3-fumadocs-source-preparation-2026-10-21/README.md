# Pinned Fumadocs source and dependency preparation

The dedicated [GitHub Actions run 39622949635](https://github.com/roryscot/patamaps/actions/runs/39622949635)
passed its single Fumadocs preparation job at Patamaps source
dcd0cb79ddfd0cb54791733f744f86a7882841c2. The three focused Git source-acquisition
tests passed. The workflow built the identified Patamaps CLI, captured, verified
and staged the selected public Fumadocs source, then installed the declared root
and docs workspace dependency closure with a frozen lockfile and lifecycle scripts
disabled. Installed versions were Next 16.4.2 and Turbo 2.11.9.

The upstream source is pinned to
2919bf9a9a84a7a594d42460878548d0677d7bb3. The selected inventory contains
2,792 paths / 47,825,903 bytes (digest in receipt). The tracked
apps/docs/.env and examples/marble-cms/.env.example paths were excluded; their
unique Git blobs were absent and the paths were never materialized. Original
selected source remained unchanged. All 27 recorded command exit codes were zero,
and each stdout/stderr digest matched the downloaded artifact logs.

The workflow used about 2.23 GB of its 4 GB growth limit. Its 544,988-byte
artifact digest, receipt digest and expiry are recorded in receipt.json. The
compact result is public; detailed logs and selected-source inventory are
available in the time-limited Actions artifact.

This result is preparation only. The Next build and the owner's pre/post-build
scripts were not run. No application route, HTTP response, browser behavior,
Server Action, deployment, dependency hermeticity or performance claim follows.
GitHub Discussion posting and Orama indexing did not occur. The other capability
and cross-stack jobs were skipped by the selected workflow dispatch.
