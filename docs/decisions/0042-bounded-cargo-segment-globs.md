# Decision 0042: opt-in Cargo segment globs

Status: implemented candidate; compilation, CLI/native execution and upstream
qualification pending. This extends the general project-adoption plan, not its
acceptance scope.

The public tokio-rs/axum workspace at
fc78d5bcdb276bd6fb53cf2db55e91757eabb469 declares members=["axum","axum-*"].
Decision0034 deliberately limits bounded-directory-globs to an entire star
segment, so it cannot interpret this existing workspace. Do not rewrite upstream
manifests or widen that old mode silently.

A separate workspaceMembers: bounded-segment-globs declaration allows exactly
one star within one directory segment, including prefix/suffix forms such as
axum-*, *-service or http-*-api. An empty star match is allowed. Recursive stars,
multiple wildcard segments, question/bracket/brace globs, traversal, absolute
paths and unsupported separators remain refused. Only ordinary matching
directories and captured ordinary Cargo.toml files participate. Unmatched names
are not manifest inputs; they still count toward the 1,024 inspected-entry bound.

Reuse the existing enumeration, 128 member declaration, 1,024 aggregate expansion,
path/segment, explicit literal-exclusion, pre/post-metadata comparison and actual
Cargo-member validation contracts. Matched symlinks and files refuse, including
symlinks named by an exclusion. An uncaptured matching manifest refuses. Receipt
workspaceMembers.mode records the new declaration. Default literal-paths and
existing bounded-directory-globs behavior remain unchanged.

Verification must preserve all old controls and cover real-shaped prefix
expansion, suffix/combined matching, exclusions, missing capture, matching files
and symlinks, unsupported grammar, nonmatching-entry enumeration bounds, full CLI
receipts and post-metadata mutation refusal. The upstream Axum workspace remains
unqualified until its exact pinned bytes, tools, configuration, feature/platform
selection and actual Cargo metadata are captured and compared. No build-script
execution or domain correspondence inference is added.
