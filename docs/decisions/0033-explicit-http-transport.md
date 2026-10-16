# Explicit transport clients and module-local Axum witnesses

Status: implemented and verified by the scoped Linux controls at sources 1588a3c and 5880cbe.
This is a G2 extension, not completed existing-project qualification.

The owner-declared patamaps-http-transport-1 profile separates HTTP operations
from domain commands. An admitted projection selects handler/input/endpoint slots.
The input carries its JSON Schema; the handler declares Rust extractors, output,
response/error schemas, scalar parameters and limits. Locators bind the actual
Rust module/function and exact source digest. Existing domain identities and
branch locators remain intact; select transport operations explicitly by ID.

    patamaps link graph.json policy.json projection.json --relation-pack routing.json --as-of TIME --format http-client --output client.ts
    patamaps link graph.json policy.json module-projection.json --relation-pack routing.json --as-of TIME --format axum-witness --output witness.rs

Both use checked projections. Emission alone establishes no compilation, runtime
observation, source authentication, current authorization or activation.

## Rust integration

Include the witness inside the existing declared Rust module. The witness names
its private functions and types in that scope, checks ordered arguments and the
exact async return type, and checks Axum Handler compatibility. It registers no
application routes and does not invoke business handlers.

Handler HTTP attributes have this shape:

```json
{
  "profile": "patamaps-http-transport-1",
  "modulePath": "src/api.rs",
  "arguments": [
    {"extractor": "state", "type": "Context"},
    {"extractor": "json-result", "type": "Evaluate"}
  ],
  "output": {"mode": "result-json", "successType": "Reply", "errorType": "Problem"},
  "responseSchema": {},
  "errors": [],
  "limits": {"requestBytes": 1048576, "responseBytes": 16777216, "depth": 64, "values": 100000},
  "frontendGroup": "evaluation-proxy"
}
```

responseSchema and each error schema must be complete supported draft 2020-12
schemas, not placeholders. Error entries contain status and schema; unique 400–599
statuses preserve structured errors such as {error,issues}, including dynamic
messages. The JSON DTO subset from decision0032 is reused; unsupported assertion
keywords/formats still refuse except the explicitly bounded transport extensions below.

Transport parsing additionally asserts canonical hyphenated UUID text (36 ASCII
characters, hexadecimal groups 8-4-4-4-12, either hex case, no version/variant
restriction). It supports exactly the pattern `^(0|[1-9][0-9]*)$` as unsigned
decimal text: no sign, leading zero, whitespace, exponent or Unicode digit.
These strings stay strings, including quantities above u64. Arbitrary patterns
and other string formats refuse. `uint64` and `int64` are explicitly restricted
to the interoperable safe integer range (0..9007199254740991 and its signed
counterpart), intersected with declared bounds. Larger numeric values refuse;
applications needing them must declare an explicit string representation. This
is a supported subset, not full 64-bit JSON numeric coverage. The older JSON-2
profile retains its UUID, pattern and 64-bit-format refusals.

The scalar controls echo typed u64/i64 values and exact quantity strings through
real Rust and the controlled proxy, and freeze malformed UUID/quantity and unsafe
integer input/response controls. Serde String alone does not enforce UUID or the
decimal pattern on the server; these are generated client assertions, not a claim
that the witness makes server validation equivalent. The [5880cbe scalar receipt](../acceptance/project-adoption/g2-http-transport-5880cbe/receipt.json)
records 86 distinct controls and all four CI38845561544 jobs passed. It includes
31 completed HTTP exchanges, 45 runtime client controls, seven emission refusals,
two Rust signature refusals and one TypeScript refusal. The accepted 1588a3c
receipt predates the scalar extensions and remains preserved.

Extractors: state, json, json-result, path, query and headers. Typed variants
carry an explicit Rust type path; headers means HeaderMap. Body extraction must
be last and is unavailable for GET/HEAD. Output modes are result-json
(Result<Json<Success>,(StatusCode,Json<Error>)>), json response
(the concrete Axum Response type), and native (an explicitly named IntoResponse
return type such as StatusCode). Generic Rust syntax is not injected: use a
module-local alias where a complex type is needed.

One witness selects exactly one captured module. A client may cover multiple
modules; existing projection collections can produce separate module witnesses.
The owner must verify captured source bytes around generation/build. The witness
does not inspect router macros, prove actual route registration, infer Serde
equivalence or enforce schema validation on the server. Actual HTTP checks remain
required. Native Axum extraction retains its existing wire behavior; unlike the
synchronous JSON DTO dispatcher, the witness does not normalize request numbers.

## HTTP behavior and bounds

Supported methods: GET, POST, PUT, PATCH, DELETE, HEAD and OPTIONS. Backend paths
use Axum brace parameters; frontend templates may also use Next-style colon
parameters. Single-segment names must match on both sides. Literal dot segments,
duplicate parameter names, catch-alls and arbitrary URI syntax refuse.

Shared frontend method/path pairs require the same explicit nonempty
frontendGroup. Backend method/path pairs remain unique. A group is an owner
declaration, not proof of the proxy's branch selection. Preserve whole-request
envelopes separately from heterogeneous domain commands; test each actual branch.

pathParameters, queryParameters and headerParameters are optional complete schema
objects. They must be exact flat objects of strings, booleans or numbers.
All path fields are required and must match both templates. Query fields may be
optional. Array/custom query encodings are unsupported. Headers use lowercase,
non-reserved names and trimmed printable ASCII values; the combined declared
header footprint is bounded to 8 KiB. Host/content-length/content-type/connection
and cookie headers cannot be supplied through this contract. Body content type
is application/json.

Generated types require options when required path/query/header values exist.
Runtime checks remain authoritative for physical bounds and exact object fields.
Path values are encoded individually; empty/dot segments refuse. Query keys are
serialized in sorted order. A caller supplies a trusted base URL on Node; browser
calls may use the current origin. AbortSignal and an explicit fetch transport are
supported. These do not authenticate the peer or confer an activation state.

Request JSON bytes are checked before fetch, up to 16 MiB. Response streams are
bounded and cancelled on overflow, up to 64 MiB; JSON content type and strict UTF-8
decoding are required. Configured depth is 1–128 and value visits 1–1,000,000.
Integral values retain the safe-JSON range. HEAD has null success/error bodies; HTTP 204/205 successes also require null
contracts and decode as no content.
Failures distinguish request, parameter encoding, input limit, response limit,
content type, invalid JSON, response schema and error schema. The generated client
contains operation descriptors, validators/types and a projection digest; the
full projection graph stays in its separate evidence artifact.

## Verification and remaining work

The controlled service preserves its private async handlers and existing router.
Its source controls exercise state, structured errors, shared proxy branches,
seven methods, path/query/header encoding, body/stream byte bounds, cancellation,
typed missing-parameter refusal, invalid group/parameter declarations and wrong
private input/output signature refusals.

    python3 -B scripts/test_cross_stack.py --phase transport-http

Use Intel's supervisor. The source CI lane fetches the committed consumer lock
with --locked and keeps it in the small diagnostics artifact. Its exact 52-package
lock was prepared in CI38841848134 and verified on Intel against the artifact
digest; the lock SHA-256 is
7d3728eaff7984b32f1454ff9b213d427bcf92d15ef96dde7b9e8812c85b20fd.
Source CI38843082846 passed with that committed lock. The scoped receipt is
[the transport acceptance record](../acceptance/project-adoption/g2-http-transport-1588a3c/receipt.json).
All four jobs passed; the Axum consumer itself executed on Linux x86_64.
The 47 distinct controls comprise 26 completed HTTP exchanges, 13 client runtime
controls, five emission refusals, two Rust signature refusals and one TypeScript
missing-parameter refusal. The other jobs retain their established kernel and
image/browser scope; they do not qualify an Axum image or an existing application.
Module-local Result/F/Fut aliases and no-content status codes are explicit controls.

The controlled proxy is a Node test server, not an observed Next.js proxy.
Real Wargame/Seeder qualification, actual Next behavior, general project
orchestration, Cargo/deployment contexts and installed consumers remain required
by the adoption plan. No VM, cleanup, production deployment or registry publication
is part of this work.
