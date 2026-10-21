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

Continue the pinned Fumadocs Next.js source/dependency preparation. Commit
dcd0cb79ddfd0cb54791733f744f86a7882841c2 fixes final report aggregation after
the preparation commands had succeeded. Targeted workflow 39622949635 was
dispatched on that revision; its hosted runner remains queued.
The workflow runs source acquisition tests with a retained fixture root, then
rebuilds the CLI and repeats preparation. It skips full capability and
cross-stack jobs. A successful preparation still does not establish a Next
application build, runtime behavior, deployment or installed workflow.

## Unfinished Next preparation checkpoint

At source b02430434dd25036e7a793341dc989a6e7b0459c, Fumadocs preparation
workflow run 39534703032 failed in its final collector with an undefined
safe_oids name. Recorded preparation commands, including frozen dependency
installation, returned zero; final report/budget aggregation did not complete.
No application build/runtime acceptance follows. Run 39533833003 previously
failed on an unsupported pnpm retry option. Preserve both failures; neither
demonstrates a Patamaps product defect. This work is deferred, not accepted.

## Selection and completion rule

Select one workstream, named project, observable outcome, resource budget and
focused verification before starting. Reuse existing contracts. Broaden checks
only when changed behavior or an unresolved failure justifies them. Commit
verified increments with exact source identities. Do not repeat complete CI,
large evidence capture or storage scans merely to maintain momentum.

New evidence may expose a genuine C01–C19 defect; record its requirement and
reproduction in the capability plan. An enhancement does not become a parity
blocker simply because a qualification harness has a failing test.
