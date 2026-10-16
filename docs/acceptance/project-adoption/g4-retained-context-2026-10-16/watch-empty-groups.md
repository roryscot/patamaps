# Empty process-group cleanup on macOS

The first reconstructed Next build was not accepted: its wrapper raised EPERM during process-group cleanup after compilation. Its failed receipt and entire output remain retained privately.

The guardian now treats Darwin EPERM as benign only after the native process listing confirms the owned group has no live, non-zombie members. Permission errors for live groups still refuse, as do failed or malformed observations. Ordinary descendant TERM/KILL cleanup remains.

A frozen previous controller reproduced rejection of an injected empty-owned-group EPERM. The corrected controller passed normal success, explicit exit 7, timed success, empty-group EPERM and live-group permission refusal controls. The first probe used an absent /bin/true on macOS; that harness setup failure is retained and excluded from the regression claim.

The complete Intel watch suite passed 12 controls through the actual per-update storage supervisor using the current compiled CLI. The receipt records exact source/tool digests and confirms they stayed unchanged. These controlled lifecycle checks do not establish application runtime or deployment acceptance.

The separate real-project receipt records successful full context reconstruction, Next build, TypeScript checking and unchanged input hashes/modes/links with the earlier configured candidate path unavailable. Its measured build times are not watch/edit latency or cold/warm comparisons. Native context integration into project-build, generated-contract replacement, runtime and installed qualification remain unfinished.
