# 0030 — Retained native development previews

The foreground driver in examples/cross-stack/dev.py inventories all supported
application inputs, periodically reconciles the complete inventory, and debounces
edits. It excludes generated/compiler output from feedback. A no-op reports that
verification was not repeated; it does not count as a cache hit or fresh result.

Each update creates a retained candidate. Source admission and offline replay,
ordinary Cargo tests/build, Next.js build/typecheck, and generated-client HTTP
checks must all succeed before one atomic pointer selects the candidate's
generated files and runnable preview. Readers bind the pointer to an immutable
verification receipt and output hashes. Rejections and cancellation preserve the
previous selection; candidates, logs, and pointer history remain available.

The snapshot is checked against the before inventory, including unexpected
candidate files, and source/tool/context hashes are checked again before
selection. This detects observed races; it is not an operating-system snapshot
or a sandbox against a malicious application. Local selection is not production
activation. Native-host preview compilation does not establish a Linux artifact,
image behavior, or browser hydration. Those remain mandatory release lanes.

On Intel, source the existing native environment and launch watch outside the
heavy-run wrapper. Each update acquires the existing supervisor lease separately:

    source .tools/intel-bootstrap/development-env.sh
    "$PATAMAPS_DEV_PYTHON" -B examples/cross-stack/dev.py --watch \
      --state .tools/cross-stack/development-preview \
      --compiler target/release/patamaps \
      --cargo "$(rustup which cargo)" --rustc "$(rustup which rustc)" \
      --node "$PATAMAPS_DEV_NODE"

State must be outside the application source. The compiler must already be built.
The ordinary one-shot driver can run under patamaps_run without --watch.
No permanent daemon, VM, deletion, registry publication, or deployment is needed.

The independent matrix in scripts/cross_stack_development.py exercises real
compilation/HTTP, no-op behavior, missing compiler, duplicate JSON keys, a
snapshot race, actual Cargo failure, continued usability of the old selection,
single/batched edits, lost-event reconciliation, generated feedback, concurrent
pointer readers, a route rename, and nested-tool cancellation. The matrix is
required acceptance, not a claim that it passed merely because it is implemented.
