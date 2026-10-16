# Finite JSON DTO HTTP contracts (draft profile 2)

Status: implementation and regression controls added; execution receipts determine acceptance.
This extends checked HTTP emission with the owner-selected handler profile
patamaps-http-json-2. The original patamaps-http-object-strings-1 remains supported.
Selecting a schema does not infer a Rust type, router, semantic identity or Serde behavior.

The existing graph admission and projection select the operation, byte-bound
crate::module::function, explicit request/response/error names and endpoint.
Cargo still checks the actual function signature and Serde traits. The current
emission path remains synchronous typed dispatch at unique literal POST routes.
Stateful async Axum, shared-endpoint discrimination, path/query/header binding
and other methods remain G2 work. This stage is not full project qualification.

## Supported schema and wire domain

Both root schemas identify JSON Schema draft 2020-12. Supported DTO assertions:

- Objects with declared properties, optional or required fields, and boolean or
  typed additionalProperties. Required names must be unique declared properties.
- Arrays with optional minItems/maxItems and an item schema.
- Strings with minLength/maxLength, string enum or string const.
- Boolean, null, finite numbers and safe integers with minimum/maximum.
- Integer formats uint8/16/32 and int8/16/32 impose their actual ranges.
- Finite acyclic local references of the form #/$defs/Name, where Name contains
  ASCII letters, digits, underscore or hyphen. All declared definitions are checked.
- oneOf requires exactly one matching alternative. anyOf requires at least one.
  A two-element type array containing null supports nullable primitive/object DTOs.
- Boolean nested schemas and the empty schema support JSON values or refusal.

title, description, default and examples are annotations. Defaults are not applied.
Unknown assertion keywords, unsupported formats, external/recursive references,
allOf and reference siblings with additional assertions refuse generation.
No arbitrary Serde enum, flattening, custom serializer or macro equivalence is claimed.

A schema has at most 256 KiB, 128 definitions, 128 properties per object, depth32
and 2,048 expanded nodes. Length/count constraints are integral through1,000,000.
The generated wire profile bounds values to depth64 and16,384 value visits.
Integral-valued JSON numbers must lie within ±9,007,199,254,740,991; larger Rust
integers require an explicitly reviewed wire representation, not silent rounding.
Other numeric values must be finite. Request bytes retain the existing8,192-byte
dispatch limit. Larger application body limits remain configurable-framework work.

Rust and TypeScript checks count Unicode scalar values. Client validators reject
unpaired surrogates, nonfinite/unsafe numbers, undefined, sparse arrays, cycles
and non-plain objects. HTTP responses are parsed JSON objects. These are JSON DTO
validators, not an object-code sandbox.

Before typed Serde decoding, generated Rust dispatch normalizes only fields
declared integer by their selected schema. Thus numeric spellings1.0 and1e0 can
satisfy an integer contract. Number-typed fields are left intact, including
negative zero on direct HTTP input. anyOf normalization uses its first matching
alternative; oneOf has a unique selected alternative. Generated-client
JSON.stringify follows JavaScript's ordinary wire behavior, including -0 becoming0.

TypeScript emits nested types and string literal unions. Its index signature for
typed additional properties includes declared property types to avoid excluding
valid known fields; runtime validation supplies the more precise distinction.
Types alone do not establish exact object cardinality or replace wire validation.

Generated consumers contain static validation/normalization expressions and their
existing Serde/HTTP dependencies. They do not call Patamaps or compile a graph on
the request path. Successful emission is not evidence of application execution.

## Verification

The existing retained entry supports:

    python3 -B scripts/test_cross_stack.py --phase json-http

Use Intel's installed storage supervisor. The required source CI lane also calls
scripts/project_http_json.py after existing source/supervision checks. It freezes
nested DTO, optional/null, array, enum, integer lexeme, negative-zero, invalid
shape, depth and oneOf ambiguity cases before execution; generates from admitted
bindings; compiles real Rust and TypeScript; and exercises the real HTTP service
and generated client. Controlled non-JSON client values are never sent as wire
requests. All candidates, vectors, failed attempts, logs and receipts remain.
This synthetic regression preserves source bytes and does not substitute for
the separate existing Wargame/Seeder runtime qualification in the adoption plan.
