# Final accounting and release of stopped native work

The [active-parent-death run](../original-owner-foreground-registered-watch-20261106/README.md)
recorded a volume-query error during cancellation. A separate fault
injection on Norway reproduced a finalization defect in the same staged
guard. After a native process exited and its group was gone, an exception
in the final capacity sample left its isolated request marked running
and its lease present. No terminal receipt was written.

The [candidate patch](final-accounting.patch) records final capacity and
retention-probe errors separately. A failed probe makes the command
return 75. Proven stopped workloads still release their reservations,
with their failed accounting recorded in the archived receipt. Uncertain
ownership still holds the reservation for review.

The [ordinary probe](probe.mjs) exercised a final capacity failure, a
final retained-roots failure, both failures, uncertain ownership and a
normal exit. The four released cases each admitted and released a
follow-up command on the same isolated scheduler. A separate registered
probe ran the pinned native engine through the reviewed capsule. The
registered call sealed normally, and the injected final capacity error
returned 75 with the stopped-workload proof and release recorded.

These runs used isolated fixture schedulers and injected accounting
results. The installed guard and shared scheduler remained in place.

[Independent review](review.json)
