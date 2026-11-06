# Installed owner watcher refuses stale Seeder inputs

The original installed watcher on Intel Norway was given the known
baseline inputs while the installed owner's selected generation contained
the later, accepted graph edit. That installed generation already passed
the [matching-input postcheck](../original-owner-watch-readonly-verification-20261106/README.md).
The [earlier stale-input trial](../seeder-stale-selection-context-refusal-20261106/README.md)
used the older source-built candidate. Its 31 missing dependencies
caused context verification to refuse before observing the baseline key.

The follow-up used the same installed watcher and Patamaps compiler with
the independently verified installed selection of the edited graph.
`project-build-verify` returned the installed edited generation's
expected key. `project-build-input-key` returned the independently
recorded baseline key without executing commands. The watcher refused
with `WATCH_SELECTION_DOES_NOT_MATCH_CURRENT_INPUTS` and emitted no
selection event. The native calls used the strict read-only runner
and its existing 900-second bound per call.

The 96 MB ordinary guard charged 4,923,392 bytes and released
normally. An independent review checked the exact two native commands,
their terminal records, four stopped process groups and the unchanged
unrelated database identity. It rehashed 4,964 artifact files and 1,885
owner inputs across the baseline and installed edited generations and
checked 1,048 artifact directories. The selected pointer, attempt set
and driver lock were unchanged. There were no application builds,
deployments, file deletions or dependency restorations.

This qualifies stale-input refusal by the actual original watcher's
read-only postcheck. The registered guard integration, active parent
death, changed-build lifecycle and owner deployment refusal cases
remain separate acceptance checks.
