# Integration enhancement backlog

Owner scope revision: 2026-10-21. The product stopping boundary is the
[C01–C19 native capability goal](../../BUILD_PLAN.md), with its identified-source
acceptance and explicit compatibility limits. The separate Intel adoption goal remains active and uses this backlog for priorities.
These tasks are not prerequisites for the capability milestone. Existing
implementations, failed runs and evidence are preserved.

The [former adoption plan](2026-10-15-general-project-adoption.md) retains detailed
G0–G6 requirements and historical checkpoints. The
[support matrix](../guides/project-support-matrix.md) records scoped results;
a passed fixture or metadata observation is not general support.

| Workstream | Existing result | Remaining work if selected |
| --- | --- | --- |
| Real Rust application onboarding | Explicit project capture, Cargo observations, scoped Axum transport and pinned upstream Axum build/tests/replay | Choose one owner application and correspondence; wire generated artifacts into its real handler and run its own positive/refusal tests. |
| Broader Next.js/framework integration | Selected production build, public HTTP/browser paths and declared observations | Qualify a named rewrite, route-group or Server Action boundary with non-writing controls. Authenticated backend/permissions remain unaccepted. |
| Retained builds and portable development loop | Controlled watch/recovery and scoped actual Rust retained workflow | Application-specific dependency closure, fresh installed workflow and measured edit-loop behavior; no blanket hermeticity or speed claim. |
| Deployment expansion | Scoped actual Linux output/runtime and deployment refusals | Remaining wrong-architecture/stale-contract controls or a chosen deployment profile. Production activation remains separate. |
| Performance acceptance | Existing functional timing records | Define comparison and acceptance budgets before exclusive measured execution. Diagnostic profiling remains separate. |
| Storage and reservation infrastructure | Installed qualified protocol3 reservations and bounded retention controls | Maintenance for demonstrated failures; no infrastructure prerequisite for parity. Preserve native/benchmark exclusive fallback. |
| Qualification tooling | Source-preparation privacy controls and retained failed runs | Repair only for selected qualification work; collector defects are not product defects without a reproduced product failure. |

## Current selected work

Pinned Fumadocs source and frozen dependency preparation passed; see the
[preparation receipt](../acceptance/project-adoption/g3-fumadocs-source-preparation-2026-10-21/receipt.json).
The subsequent [production-build attempt](../acceptance/project-adoption/g3-fumadocs-next-build-2026-10-21/receipt.json)
failed at owner command pnpm --filter docs run build:pre in workflow
39625379329 on Patamaps commit 5048d309. Three source-acquisition tests, the
native release CLI build, source privacy/capture/staging and frozen install
passed. The selected source contained 2,792 paths / 47,825,903 bytes; copy
digests were checked before the pre-build. A read-only audit of the exact pinned
upstream commit 2919bf9 confirmed apps/docs defines build as
pnpm build:pre && next build && pnpm build:post; build:pre runs the owner's
fuma-cli/compiler registry generation. The compiler reported unresolved
package-local aliases and relative imports in packages/radix-ui. The source
files and their declared TypeScript alias configuration were present in the
pinned tree and selected inventory. This is evidence against source omission,
but does not establish whether the cause is an upstream compiler defect or an
unsupported build precondition. Next production compilation never started, so
this remains a failed project candidate, not a Patamaps product failure or a
G3 pass. Owner post-build / Orama, runtime, HTTP, browser, deployment and
installed workflows remain unverified. Preserve this failed run and its
artifact; do not patch the upstream candidate or retry the unchanged build.
Continue G3 with another unchanged real Next.js application whose production
build can run without unresolved owner-side prerequisites.

## Unfinished Next preparation checkpoint

At source b02430434dd25036e7a793341dc989a6e7b0459c, Fumadocs preparation
workflow run 39534703032 failed in its final collector with an undefined
safe_oids name. Recorded preparation commands, including frozen dependency
installation, returned zero; final report/budget aggregation did not complete.
No application build/runtime acceptance follows. Run 39533833003 previously
failed on an unsupported pnpm retry option. Preserve both failures; neither
demonstrates a Patamaps product defect. This work is deferred, not accepted.

## Hyperbound Next source candidate (2026-10-21)

The unchanged Hyperbound checkout at commit `7721da50e4a817dafb13a8e4cd10347e7ee884f7`
is a real Next 14.2.14 candidate with 54 App Router pages and explicit route-group
structure. Its declared Node version is 22.8.0 and installed TypeScript is 5.5.4.
A path-only profile selects 66 tracked inputs: 61 Next special files and the
package/runtime/configuration/lock files. It excludes `.env`, `node_modules`
and `.next`; no source bytes were added to the profile.

The supervised observation request `b8283792-531e-49b8-8fbb-ca7663bc5eca`
finished with confirmed workload stop and lease release, but the guard refused
before capture or staging because retained-output headroom was insufficient.
The failed guard record is retained at
`/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/d5c00cfa-dd7c-4720-a9bf-5d38900dd7d0/run.json`.
No Next build ran. Route-group/dynamic observations, configuration semantics,
runtime, browser, deployment and installed-consumer acceptance remain unverified.
The compact [receipt](../acceptance/project-adoption/hyperbound-next-source-20261021/receipt.json)
preserves the scope and exact result. Continue only after resolving headroom under
the existing retention policy; do not bypass the guard or remove files without a
fresh exact-list approval.

## Selection and completion rule

Select one workstream, named project, observable outcome, resource budget and
focused verification before starting. Reuse existing contracts. Broaden checks
only when changed behavior or an unresolved failure justifies them. Commit
verified increments with exact source identities. Do not repeat complete CI,
large evidence capture or storage scans merely to maintain momentum.

New evidence may expose a genuine C01–C19 defect; record its requirement and
reproduction in the capability plan. An enhancement does not become a parity
blocker simply because a qualification harness has a failing test.
