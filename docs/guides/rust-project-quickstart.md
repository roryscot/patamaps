# Start using Patamaps in a Rust project

Start with one correspondence in an existing crate: a stable command identity,
its handler identity and required schema/policy. Patamaps checks declarations
and emits static data; it does not infer domain meaning or turn a locator
string into a function call. Connect generated identities to your real handler
and test that connection.

## Get the compiler

The CLI is published on crates.io as `patamaps-cli` version
`0.1.0-alpha.2`. Install that exact alpha version with:

~~~sh
cargo install patamaps-cli --version 0.1.0-alpha.2 --locked
~~~

The alpha.2 package verification, fresh Cargo-home installation of the exact
candidate archives, and generated-Rust consumer compilation passed in
[Linux x86_64 CI](https://github.com/roryscot/patamaps/actions/runs/40117789049).
The install rehearsal used a debug build. Public crate downloads and registry
checksums match those tested archives; see the
[publication receipt](../releases/0.1.0-alpha.2/publication.json).
Alpha.2 includes project-exec-selected and the retained-output checks.
Building from this checkout requires Rust 1.99 as declared in rust-toolchain.toml:

~~~sh
cargo build --release --locked -p patamaps-cli
~~~

On the shared Intel Mac, use the existing storage supervisor instead:

~~~sh
/Users/admin/.nvm/versions/node/v22.23.3/bin/node \
  /Users/admin/Documents/Codex/storage-safeguards/run-project.mjs patamaps -- \
  /Users/admin/.rustup/toolchains/1.99.0-x86_64-apple-darwin/bin/cargo \
  build --release --locked -p patamaps-cli
~~~

The existing Intel executable is
/Volumes/dev_src_case_sensitive/projects/patamaps/target/release/patamaps.
Record the source revision and executable identity; historical acceptance does
not automatically cover a later build.

## Declare and generate one binding

Create a new patamaps directory in your application containing graph.json,
policy.json, projection-spec.json and routing-pack.json. Use the checkout's
fixtures/routing/{graph.json,policy.json,projection-spec.json} and
relation-packs/routing.json as schema examples. Replace example identities,
labels and locators with your declarations. Keep semantic IDs stable when
files/functions move. Sample TypeScript locators are data, not Rust discovery.

The graph declares concepts/implementations and mappings; the policy declares
mapping properties/constraints; the projection chooses checked subjects/slots.
Match graph ID/revision and referenced IDs. Do not select secrets.

With PATAMAPS set to the absolute executable, run from your application:

~~~sh
"$PATAMAPS" validate patamaps/graph.json \
  --relation-pack patamaps/routing-pack.json
"$PATAMAPS" link patamaps/graph.json patamaps/policy.json \
  patamaps/projection-spec.json \
  --relation-pack patamaps/routing-pack.json \
  --as-of 2026-10-21T12:00:00Z --format rust \
  --output src/patamaps_generated.rs
~~~

Use an explicit evaluation time appropriate to your policy/evidence, not the
sample date indefinitely. Generate into a new path; the CLI refuses accidental
overwrite. For later generations, use the explicit --overwrite option only for
your designated generated file. Fail the build on a refused/nonzero generation
rather than consuming stale output.

## Connect the artifact to real code

The basic Rust emitter provides PROJECTION_JSON and a SemanticId parser for
selected subjects. It does not emit your handler body or HTTP server. Include
the generated module in your crate:

~~~rust
#[allow(dead_code)]
mod correspondence {
    include!("patamaps_generated.rs");
}
~~~

Use SemanticId::parse(command_id) at your dispatch boundary and explicitly map
accepted IDs to existing handlers. Unknown IDs remain errors. The embedded
projection contains checked slot/mapping/target records for application wiring.
Including the module alone does not prove the handler matches its declared
target; assert the real dispatch.

Run your normal cargo check/test commands through your project's required
guard. Add a positive dispatch test, unknown-command refusal and missing-required-
mapping generation refusal. Move a handler and update its locator: its semantic
command ID should stay stable. Commit the generated artifact or regenerate it
deterministically before compilation under your project's chosen policy.

This first integration needs no runtime MetaMap, Node, compiler service,
retained application-build controller or deployment harness. For HTTP/Axum,
select the supported explicit contract profile and qualify your actual types.
For compiler embedding, use local patamaps-core/patamaps-projection crates and
their checked-state APIs; decoded records are not admitted values.

For Linux runtime selection, the native [ELF target preflight](elf-target-preflight.md)
checks a reviewed producer digest and declared architecture before selection.
Use immutable artifact bindings and qualify the actual runtime separately.

See the [support matrix](project-support-matrix.md) for additional scoped results.
Broader work belongs to the [enhancement backlog](../plans/integration-enhancement-backlog.md).
