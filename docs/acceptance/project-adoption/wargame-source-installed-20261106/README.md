# Wargame build and lab runtime using source-installed Patamaps output

The source-installed Patamaps CLI's [verified Wargame output](../wargame-installed-profile-20261106/README.md)
drove a new Rust and Next production build on Norway. Wargame's original
build and service scripts ran with an empty Cargo target, retained npm
dependencies, and the existing offline Cargo inputs. Strict TypeScript
compilation matched the accepted JavaScript. Rust compiler dependencies
bound the emitted Axum witness, and the live API used the new binary.

The original 13 network checks passed across 22 HTTP exchanges. A
separately queued run used those same Rust and Next builds with the
original Playwright configuration and pinned Chromium. All 22 original
test identities passed, 11 desktop and 11 narrow, without skips or
retries. The browser run used a separate copy of the Next output so
runtime cache writes stayed outside the producing tree.

The independent network and browser reviews rehashed 537 and 547 inputs
respectively. The prior Rust binary and bundle pointer matched, all
2,820 entries of the prior selected Next tree were verified, and all
2,779 entries of the source-installed producing Next tree survived
the browser run unchanged. The owned services stopped and both
reservations released under the existing limits.

The Patamaps CLI was reused from its [earlier exact source installation](../installed-original-owner-next-20261027/package-source-review.json).
This passes the source-installed Wargame build and lab transport and
browser workflow. The managed checks on the same builds are recorded below.
A single successful aggregate native suite remains open.

[Network review](network-review.json) · [Browser review](browser-review.json)

## Managed identity and detached restore

The original managed suite on the same source-installed builds passed
the identity and authoring integrations. Its detached restore check
failed at archive extraction verification. The wrapper's file-creation
mask changed 2,012 extracted files from mode 0644 to 0600. The
independent comparison verified that every expected payload byte matched.
The failed invocation and its extracted tree are preserved.

The original focused detached check then passed under mask 022 with
isolated PostgreSQL 18.6 and synthetic OIDC. It restored and exercised
a separate database while the original fixture's connections were
denied. The independent review streamed all 2,185 regular archive
members, including the exact source-installed Rust binary and Next
build ID. The three managed integrations passed across the two
invocations, each with two browser cases.

Both invocations restored the 72 prior evidence files by identity and
digest and kept the original and producing Next trees intact. Both
owned clusters stopped, both tool mounts detached, and both
reservations released. The detached check qualifies this synthetic
fixture and archived runtime.

[Managed review](managed-review.json)
