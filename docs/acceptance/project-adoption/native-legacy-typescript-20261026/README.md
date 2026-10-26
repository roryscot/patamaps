# Native legacy TypeScript renderer

The native v1 projection dispatcher now renders the owner's demonstrated static
TypeScript table. The SDK only transports the request and declares its result.
This read-only rendering does not confer admission or activation.

The guarded qualification ran cargo test --locked --offline -p patamaps-core
--test legacy_projection; cargo test --locked --offline -p patamaps-core --lib
legacy_projection::tests; cargo build --locked --offline -p patamaps-cli; and
scripts/parity/projection_typescript_contracts.mjs against the retained original
Metamap0.5.0. All passed; [receipt](receipt.json) binds code, engine and outputs.

Default/named/nullish-name output matches the original bytes. Four generated
modules passed TypeScript semantic checks and actual execution. Nested
prototype-looking properties remain own data; caller text cannot execute.
Twenty-two native refusals cover exports, malformed/stale records, header
injection, cardinality and bounded output expansion. The original66-case
projection fixture is unchanged; its four regression tests and two internal
resource tests passed.

Legacy rendering intentionally refuses unsafe export globals, malformed
content-addressed records and oversized output. This is not a blanket claim of
the original emitter's acceptance domain. The actual owner generators/tests,
full G6 integration and performance acceptance remain pending.
