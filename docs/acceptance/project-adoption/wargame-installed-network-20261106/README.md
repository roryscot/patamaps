# Wargame builds and network checks using installed Patamaps output

On Norway, Wargame's original production build and test-service launcher
built a new Next application and Rust service using the client and witness
from the [freshly installed native Patamaps package](../wargame-installed-profile-20261106/README.md).
The Rust target began empty. The build reused the retained npm dependencies
and offline Cargo inputs. Strict TypeScript compilation reproduced the
accepted client JavaScript. The Rust compiler dependency record names the
newly emitted witness, and the API listener belonged to the new binary.

The first invocation passed the build and service-readiness checks, then
stopped before the network assertions when Node treated the CommonJS
client as an ES module. A second invocation stopped in a precheck that
mistakenly required equal modes on two generated map assets with equal
bytes. The private build had created them with mode 0600, while the
accepted public asset files were mode 0644. Both failures are preserved.

The final run added an explicit CommonJS package boundary for the test
client, verified the two asset digests and reused the newly built Rust and
Next outputs. All 13 original network checks and 22 exchanges matched the
frozen Wargame result, including both proxy branches, request size
limits, stale generation rejection and the unavailable upstream.

The independent review rehashed 546 inputs and verified the original 2,820
Next entries and four restored filesystem identities. The prior binary and
contract selection were preserved. Owned services stopped and all three
reservations released. The build stayed within the existing 4 GB growth cap.

This passes the native-package transport workflow in lab mode. The
source-installed compiler's matching emission has separate evidence.
The rebuilt runtime was not exercised with source-installed outputs,
managed identity, or the browser suite in these runs.

[Independent review](review.json)
