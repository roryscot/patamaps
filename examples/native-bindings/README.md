# Native CreateUser consumer

This is a separate Rust port of the pinned MetaMap routing consumer. Its authored
semantic IDs, correspondences, owner fact scopes, contexts and exclusions come
from `fixtures/reference/examples/routing/bindings`. The original JavaScript
validator and handler remain unchanged as an independent behavioral shadow.

`scripts/test_binding_matrix.py` copies this consumer outside the checkout,
converts the old envelopes explicitly, authors Rust locators and byte digests,
and tests all 22 original scenarios. Both the input validator and handler are
statically linked through generated bindings. The executable has no Patamaps or
Node runtime dependency. The JSON input/output is serialized at the draft
string-function boundary; this is not the original JavaScript API.

`build.py` is a narrow, consumer-owned staging helper. An explicit local module
map selects owned `.rs` files; it checks containment and byte digests, captures
authored control inputs, calls the installed native compiler and lets Cargo
resolve the real exports and types. It writes only a fresh candidate directory.
Failures leave the previously accepted consumer untouched. Generated modules
are created during the test, so this template alone is not a prebuilt consumer.

Configuration and compiler inputs are trusted local consumer choices. This
helper does not sandbox Cargo, authenticate producer declarations, attest a full
toolchain dependency closure, manage protected activation or replace the Linux
activator. Approval and activation are tested separately at their own boundary.
