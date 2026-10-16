# Watch guardian cleanup
The source-bindings job in CI run 38882742159 failed runner-death cleanup. A policy runner that leaves its guardian in the runner process group can cause outer cleanup to kill that guardian before it stops the independently grouped native build.

Each guardian now establishes its own session when necessary. The deterministic regression reproduced surviving tool processes with the previous controller and no survivors with the fix. Its owned processes were stopped after observation.

Native Intel verification: scripts/project_watch_controls.py --compiler .tools/project-adoption/next-compiled-seeder-retry2-20261016/tooling.retained-offline/provider passed all 11 controls through the configured storage supervisor. Source digests and compiler digest are retained in watch-receipt.json. These controlled lifecycle checks do not establish application acceptance. The separate retained-context implementation is excluded from this commit.
