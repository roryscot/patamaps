# Align every supplied scientific payload

An [independent valid external-metadata probe](../acceptance/capabilities/scientific-partial-source-external-resume-2026-10-15T03-09-32.299572Z/receipt.json)
against published source `a781406` reproduced a native bug. Genuine partial
packages verified and complete contradictory packages refused, while a supplied
genuine TSV paired with an altered recorded row verified when external metadata
bytes were absent. The earlier probe and counterexample remain preserved.

Crate creation now checks every payload that is present. Included TSV columns
and rows must reproduce the recorded document. When declared external metadata
is absent, recorded metadata is used only as parsing context for the included
TSV; its missing bytes remain unverified digest references. Included metadata
must match the recorded metadata even when TSV bytes are absent. Declaring an
external metadata source cannot enable embedded-metadata mode.

The four included/absent inventory combinations retain their original meaning.
No source is fetched, manufactured as an included payload, authenticated, or
promoted into scientific truth. Incomplete raw sources still cannot enter closed
governed candidate artifacts. Crate verification regenerates these same checks.

[Focused native tests and clippy](../acceptance/capabilities/scientific-alignment-focused-2026-10-15T03-17-33.314363Z/receipt.json)
pass valid inventories, independent TSV/metadata contradictions and mode refusal.
The [unchanged independent external-metadata counterexample](../acceptance/capabilities/scientific-alignment-independent-after-2026-10-15T03-30-54.192893Z/receipt.json)
now refuses the altered partial package while the genuine partial control still
verifies. [All ten compiler stages](../acceptance/capabilities/compiler-2026-10-15T03-25-51.400752Z/receipt.json)
pass for the combined repaired source. Installed/package/platform milestones
remain separately required.
