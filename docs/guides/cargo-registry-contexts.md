# Explicit Cargo registry contexts

Status: passed for pinned Miniserve 0.35.0 in the bounded Linux profile.
[Run 40050181349](https://github.com/roryscot/patamaps/actions/runs/40050181349)
at `73c7c88` passed all 325 unchanged upstream tests, eight actual HTTP controls,
registry/snapshot corruption refusals before effects and restored offline replay.
[Independent review](../acceptance/project-adoption/g3-cargo-registry-context-20261023/registry-accepted-40050181349/independent-verification.json)
verified all 456 package checksums,874 registry files and60 selected application
files from the exact artifact. Previous failed executions remain preserved in
the [integration backlog](../plans/integration-enhancement-backlog.md).
Fresh current-engine source/native installation and registry replay now also
[passed independent review](../acceptance/project-adoption/g3-cargo-registry-context-20261023/installed-accepted-40051317674/independent-verification.json):
both installed compilers verified/executed the selected application, registry
tampering refused before effects, and restored bindings/bytes remained unchanged.
All eight HTTP controls passed with each installed compiler. No complete
dependency closure or general Rust support is asserted by these results.

Patamaps already accepts opaque inputs through ProjectContext and composes them
with source, workspace admission, commands and artifact selection in ProjectBuild.
The Cargo qualification uses those Rust contracts without adding another build
engine. The registry inventory helper is qualification tooling, not a new stable
Cargo discovery API.

## What is retained

The explicit context contains unchanged selected application files and the
original public crates.io distribution archives and sparse-index bytes from a
fresh download home. Every archive must match its exact Cargo.lock checksum;
missing, extra or corrupt archives refuse. Other registries, credential/config
injection, ambiguous configuration, symlinks and an oversized inventory refuse.
No extracted dependency source tree is captured. The originals are public
registry artifacts, not owner-created archives concealing excluded files.

A fresh, credential-free home matters: copying an existing ~/.cargo would also
copy configuration, credentials, unrelated packages and mutable state. The helper
scripts/cargo_registry_context.py inventories only the allowed original archive
and index files; its stage function verifies source/copy digests. The current
combined file-byte ceiling is 256 MiB. Unknown requirements require a separate
review; the helper does not silently skip missing dependencies.

Cargo fetch --locked without --target downloads dependencies for all targets,
according to the [Cargo command contract](https://doc.rust-lang.org/cargo/commands/cargo-fetch.html).
The pinned Miniserve case expects all 456 registry packages in its unchanged
lockfile. This archive inventory does not claim successful compilation on every
platform.

## Native build composition

Use project-context-capture on an explicit selection of the application and
registry files. Bind the returned digest and absolute snapshot path through
patamaps-project-build-context-1. Keep overlays empty when nothing is replaced.
Only declare the host output subtree bundle writable; do not declare the registry
archive/index subtree or the whole Cargo home writable. See the
[retained workflow](retained-project-builds.md) for the existing plan contract.

The qualification's owner plan captures its build helper, shell recipe, nonsecret
executor configuration and complete registry digest inventory. Cargo, rustc and
Docker executable identities are checked before/after execution. The existing
Rust project-build command verifies the input/context bindings around execution,
snapshots the produced bundle and atomically selects only a successful attempt.

The managed workload sees the candidate and original archive/index directories
through read-only mounts. Cargo extraction, locks, target files, HOME and TMPDIR
live in a fresh bounded /work filesystem. The original configured download home
is renamed before execution and is not mounted. No host user home, credentials
or Docker socket is mounted. The read-only /etc/alternatives mount supplies OS command aliases.
Only the runner's public CA bundle at /etc/ssl/certs/ca-certificates.crt is
mounted for the default WebDAV client's system trust store. Its bytes are bound
in captured executor configuration, private-key markers refuse, SSL_CERT_FILE is
explicit, a normal verifying SSL context must load CA roots before Cargo, and
the bundle digest is checked afterward. No private certificate directory or user
key is mounted. This remains an external OS input.
Host tools, Rust toolchain and the original pinned
public test clone remain read-only external inputs; they are not closed by this
registry snapshot.

The CI executor requires capacity for two CPUs, 6 GiB memory with zero swap and
512 PIDs. It checks Docker settings before start and actual kernel limits before
Cargo. The root is read-only; /work has a 3 GiB quota, with Docker's separate
64 MiB /dev and 1 MiB /dev/shm also checked. External networking is absent;
dual-stack loopback remains available for actual upstream HTTP tests. Explicit
container-local hosts, nsswitch.conf and host.conf (multi on) are captured as
nonsecret inputs and mounted read-only. A Rust TcpStream probe covers both address
families before Cargo; host/global kernel settings stay unchanged. Both --locked and
--offline remain set, but physical networking enforcement is a separate check.

## Executable and evidence

The original release build runs first. A single executable is copied through a
bounded regular-member tar reader, capped at 32 MiB and digest checked, before
the unchanged default upstream tests are released. Files in tmpfs are streamed
with docker exec and tar; Docker documents this [copy limitation and alternative](https://docs.docker.com/reference/cli/docker/container/cp/#corner-cases). Raw stdout/stderr stay in
bounded private qualification logs. The selected bundle contains the exact
executable and compact execution receipt. The existing deployment qualifier
then exercises its eight actual HTTP checks and four selection refusals.

Registry snapshot corruption must refuse before a marker build command and keep
the previous selection. A changed selected archive must likewise refuse
project-exec-selected before a marker effect. Restore the retained original;
project-build-verify must still work when configured original owner/cache/snapshot
paths are unavailable. Offline verification rechecks retained bindings; it does
not rerun Cargo or attest current deployment authorization.

One successful selected-state archive retains each original registry member once.
The CI artifact ceiling is 320 MiB and retention is 14 days. Do not also upload
fresh extracted sources, original clones, failed candidate copies, raw logs or a
second original snapshot. Durable Git evidence consists of compact receipts and
exact artifact digests; it is not a dependency mirror.

The eight original Miniserve TLS/auth test fixture files remain outside every
Patamaps capture. Tests use the pinned public clone. This preserves the existing
privacy boundary while leaving owner test-context closure explicitly open.
Performance, full OS/toolchain closure and production activation remain open.
That earlier installed result covers registry/selected-state replay.
[Fresh installed owner builds](../acceptance/project-adoption/g5-installed-rust-owner-build-20261024/accepted-40118700332/independent-verification.json)
now pass for the exact development-profile source/native pair at8c6de4,
workspace enginea5d602de. Both installed compilers rebuilt pinned Miniserve from
the original selected source/registry inputs, each passing325 unchanged tests,
the eight HTTP controls twice, four selection refusals and registry/stale-runtime
before-effects checks. Review rehashed both owners'874 registry members and60
source files and matched1,203 packaged source members against Git. Checkout
compiler/qualifier absence, source restoration and stopped owned containers
passed. See the [bounded plan](../plans/2026-10-24-installed-rust-owner-build.md).
Declared dependency compiler artifacts were reused when building the installed
source CLI; complete external OS/toolchain/test-fixture closure and performance
remain unaccepted.


The unchanged QR test requires a URL outside the loopback address ranges. Its
profile assigns192.0.2.2/32 to the existing owned lo interface before Cargo. A
separate original-image helper shares only that network namespace, has only
NET_ADMIN, no host mounts and strict CPU/memory/PID limits, and must exit with
Running=false/Pid=0 before the workload starts. The workload has zero effective
capabilities. Onlylo remains; the address has no external peer/gateway and both
external-route checks still refuse. This is an explicit local qualification
address, not general network/deployment support or changed upstream behavior.
