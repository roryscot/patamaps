# Retained Seeder context refusal before stale-selection comparison

On Intel Norway, the original installed watcher attempted to verify the
retained source-built edited Seeder selection before observing the older
owner inputs. Its strict native runner launched `project-build-verify`.
Patamaps returned exit 2 with `PROJECT_CONTEXT`. The second command,
`project-build-input-key`, never ran. The ordinary guard preserved the
failure, confirmed the two process groups stopped and released the
96 MB reservation. The unrelated database retained its start identity.

An independent full context comparison checked 195,946 present entries
against the selected attempt's manifest and captured inputs, including
file digests, modes and symlink targets. The remaining 31 entries were
absent. They are ordinary dependencies totaling 350,566,593 logical
bytes. Each has a SHA-256-matching copy in both the retained snapshot and
the separately installed owner's candidate. The scan establishes
the missing dependencies, without establishing when they disappeared.

All 4,964 declared artifact files, 1,048 declared artifact directories
and 1,885 owner source inputs across the two source-built generations
were preserved, along with the selected pointer, attempt set and
driver lock. No files were restored or deleted. The failed execution
and exact private recovery preimages remain on Norway.

The separately installed generation contains the same accepted graph
edit and passed the earlier [matching-input watcher postcheck](../original-owner-watch-readonly-verification-20261106/README.md).
It is the basis for the subsequent stale-input trial. This result
establishes fail-closed context validation before comparing input keys.
