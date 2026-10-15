# 0033 — Exact installed cross-stack consumers

The package gate creates a fresh unpublished source/native archive pair with
the existing deterministic packager. It checks both distribution digests,
safe archive members, every installed source-inventory entry, absence of
unlisted source files, exact installed executable bytes, and installed engine
identity against the installed source.

A separate Python process executes the copied consumer scripts. Linux CI reruns
the actual BuildKit/image/HTTP/browser workflow with the installed executable;
it does not rebuild or import the graph compiler from the development checkout.
The Native Mac lane uses the same installed preview workflow under the caller's
real supervisor lease. Fresh dependency directories use the pinned lockfiles;
retained dependencies are never removed or overwritten by npm ci.

After generation/acceptance, only this retained test installation's compiler is
renamed to an explicitly recorded unavailable path. The already-built Next app
and service run again with no graph compiler on PATH and the configured compiler
unavailable. Linux uses the exact ELF extracted and inspected from its image for
this final host-runtime control; prior controls separately prove actual container
behavior. Runtime source imports and package dependencies remain ordinary
Next/React/Serde/HTTP/TOML dependencies. No graph compiler enters a request path.

Archives, installation files, compiler bytes under the renamed path, candidate
images, logs, traces and outputs remain. A renamed test compiler can be recovered
from that path or the verified native archive. There is no registry publication,
production activation or deletion. The gate records actual results; implementation
alone is not installed-consumer acceptance.
