# Pinned Fumadocs Next build attempt

This acceptance attempt is failed and remains so. Git source-acquisition controls,
the Patamaps CLI release build, selected-source privacy/capture/staging, tool
identity checks, and frozen dependency installation passed. The source pin was
2919bf9a9a84a7a594d42460878548d0677d7bb3; 2,792 selected inputs totaling
47,825,903 bytes were copied and digest-checked in the build candidate.

The owner's pnpm --filter docs run build:pre command exited 1 in
fuma-cli/compiler. The diagnostics report package-local path aliases and
relative imports as unresolved. The named source files were present in the
selected-input inventory; the exact cause is undetermined. This is not evidence
of a Patamaps product failure, and it is not a passing application build.
The Next production build did not start. Runtime, HTTP, browser, deployment,
dependency-closure, and application acceptance remain unverified.

The original helper receipt incorrectly left preBuildExecuted false because it
set that flag only after a successful exit. The command record and retained log
show the pre-build was invoked and exited 1. The helper source now sets the flag
before invocation; the original run artifact remains unchanged.

The owner post-build, which may update the remote Orama index, was not run.
No application GitHub Actions or external writes were invoked. The CI artifact
and exact digests are listed in receipt.json; its logs are retained on Intel
under /tmp/patamaps-fumadocs-failure.ceY8vL.
