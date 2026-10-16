# Bounded Cargo workspace member expansion

Status: implemented with frozen controls; execution pending. G3 remains incomplete.

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
