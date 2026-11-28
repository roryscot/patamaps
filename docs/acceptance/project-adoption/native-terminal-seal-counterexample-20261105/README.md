# Actual lost-final-record release defect
The isolated real-controller test receives six raw control records from an actual zero-exit native operation, but forwards only the first five to the receiver. Native registration and physical stop are known; the final normal-success record is missing. The previous staged bridge nevertheless marks the reservation finished and releases it. The independent counterexample confirms this violates the conservative incomplete-proof requirement. All owned groups physically stopped; no parallel workload was launched.

The proposed bridge requires the complete normal-success seal for controller exit zero, including registration, the expected inner/outer sequence counts, final completion, closed data streams and unchanged bindings. A failed or signaled controller may still release a completely known stopped workload; it is not represented as a successful operation. Unknown outcome and existing protocol/observer/probe/binding uncertainty continue to hold.

Twenty-eight decision controls pass. A frozen twelve-case regression, seven conservative holds plus five real lifecycle cases, is queued under the existing exclusive guard. At this checkpoint it is **not independently accepted**. The earlier duplicate-output failure and missing-helper fixture failure remain retained. No installed guard/trust or parallel activation follows from a proposed fix.

Raw private diagnostics remain on Norway under .tools/native-guard-single-output-complete-fixture-20261105. The bounded independent counterexample and proposed patch are included here.

The subsequent [twelve-case independent regression](../native-normal-seal-twelve-cases-20261105/README.md) now passes. The counterexample remains a failed historical result; installed and parallel activation remain unchanged.
