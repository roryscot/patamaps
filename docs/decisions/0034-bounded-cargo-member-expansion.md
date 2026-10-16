# Bounded Cargo workspace member expansion

Status: implemented and verified by scoped Linux controls at63abaed. G3 remains incomplete.

The owner may select workspaceMembers: bounded-directory-globs in the native Cargo
provider. Default literal-paths behavior still refuses glob members. The new mode
supports one complete * directory segment with normalized literal prefix/suffix,
including crates/*. Other glob syntax, multiple stars and workspace exclusions
in combination with glob expansion refuse until explicitly supported. This is a
reviewed subset, not full Cargo glob compatibility.

Reuse captured manifest bytes, native filesystem path checks and actual Cargo
metadata. Before invoking Cargo, enumerate the selected pattern at most 1024
entries, reject symlink traversal, non-UTF8 names, unsafe paths and non-directory
matches. Each expanded Cargo.toml must already be an explicit captured input;
never load an uncaptured manifest's values. Sort exact names and relative manifest
paths into the retained observation. Repeat expansion after metadata and refuse
changes. Source bytes, tool hashes and existing root/config checks still apply.
At most 128 declarations and 1024 expanded member matches per observation are
supported. Empty globs refuse. Excluded members and broad **/?/[] glob grammars
remain separate required adoption work.

Acceptance requires a real offline Cargo metadata workspace with an explicit
lock and captured sources; old default refusal; missing manifest, symlink, path
escape, unsupported syntax/exclusions, empty and expansion-bound refusals;
post-observation inventory mutation refusal; and an offline retained replay with
no source/tool lookup. Unit checks cover bounded expansion separately from actual
Cargo metadata. Passing expansion alone proves neither compilation nor workflow
acceptance. Directory equality is an endpoint observation, not a claim that no
transient filesystem change could occur between the two checks.

Cargo's documented member behavior remains the reference:
https://doc.rust-lang.org/cargo/reference/workspaces.html#the-members-and-exclude-fields

## Scoped verification

CI38847576022 passed all four jobs. Its explicit discovery phase retained 31
distinct controls and 80 commands, including nine G3 cases and glob-backed
workspace replay after configured provider/Cargo/rustc/root-manifest paths became
unavailable with an empty external PATH. The [scoped receipt](../acceptance/project-adoption/g3-cargo-members-63abaed/receipt.json) preserves observed request/shard digests, command outcomes,
source/tool identities and exact coverage limitations. Expanded fixture build
scripts were not executed; metadata observation is not compilation.

Earlier CI38846332010 passed its existing jobs but did not call this driver.
Its green source status is not used as proof of the new controls. Existing-project
Cargo qualification, additional reviewed config/Next contexts and the rest of the
adoption plan remain required. New retained-staging controls introduced after
63abaed have separate current-source verification pending.

## Literal exclusion extension — implementation, execution pending

The explicit workspaceExclusions: literal-paths mode requires bounded-directory-globs.
Default refuse-with-globs retains the current rejection and its frozen negative.
Support at most128 unique normalized workspace-relative literal directory paths;
no glob syntax, escapes, duplicate/nested values or ancestor/descendant overlap with a
matched member directory. Explicit literal member/exclusion overlaps also refuse.
Exact matched ordinary glob directories can be excluded
without loading their manifest values or requiring those manifest captures.
Selected path dependencies still require their captured manifests, even if the
dependency package is excluded from workspace membership. This is not arbitrary
Cargo exclusion compatibility or proof that Cargo performs no filesystem reads.

Record exact excluded directory names alongside included manifest expansion;
count both against the existing1024 aggregate match bound. Check the same inventory
after metadata; an excluded-directory membership mutation must refuse. Confirm
included members against actual Cargo output as before. Capture retains the raw
root manifest and declaration context; excluded values are not added to inputs.

Acceptance: actual offline Cargo with a malformed, uncaptured excluded manifest
succeeds and emits only retained members; default mode still refuses; missing
included capture, excluded path dependency without captured manifest, ambiguous
literal overlap, duplicate/escape/glob exclusions and symlinks refuse. A controlled
post-metadata added excluded match must refuse. Preserve earlier failed receipts.
Execution is pending until the new controls pass; the63abaed receipt predates it.
