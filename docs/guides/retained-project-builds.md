# Retained project builds

Run project-build through the applicable project/application storage supervisor:

    patamaps project-build build-plan.json --source /work/service --state /work/build-states/service
    patamaps project-build-verify /work/build-states/service

The state parent must already exist. State must be outside the original source tree and outside every enclosing Cargo workspace. The original source supplies selected bytes; programs run in a new retained candidate, with owner-declared cwd and absolute executable paths.

The plan uses profile patamaps-project-build-1 and embeds five existing declarations:

- project: a patamaps-project-inputs-1 ProjectProfile, explicitly selecting immutable UTF-8 source/configuration/tooling inputs.
- workspace: a WorkspaceConfig whose paths are relative to that staged source. Every capture must be viable before build commands start.
- buildSteps: one or more ProjectCommand declarations.
- verificationSteps: one or more ProjectCommand declarations, run after the initial artifact snapshot.
- outputs: explicit objects with path and kind (file or tree), relative to the candidate.

Generated workspace outputs are staged alongside source and become immutable selected command inputs. Do not also select old copies of those output paths as original source inputs. Program environmentReferences resolve only captured nonsecretConfiguration strings; ambient environment and secret references remain unresolved. See decision0038 for command JSON.

Declared artifact bytes, Unix mode bits and tree membership must stay unchanged through verification and the final source/tool checks. Directory symlinks, file symlinks and special files refuse. File size is bounded at4GiB, combined artifact bytes at16GiB, tree depth at128 and entries at32768, with the normal record byte limit. These observations do not attest ACLs, xattrs, dynamic dependencies or runnable architecture.

A successful update atomically replaces selected.json and preserves the exact previous pointer in the new attempt. Failed, raced and interrupted attempts remain; pre-publication failures preserve the old pointer. A matching input key checks stored bindings/current selected bytes and reports verification:not-repeated with cacheHits:0. Use --force to execute a fresh attempt rather than taking that no-op path.

project-build-verify rechecks retained records and candidate artifact bytes without rediscovering original source or executing recorded tools. Relocated state was tested when bytes/modes are preserved. Pin the creating Patamaps executor source/identity for historical verification. Saved command evidence is not a signed execution attestation, current authorization or deployment activation.

The current workflow inherits bounded selected text capture; it does not restore opaque source dependencies, package installs, original executable metadata or an entire arbitrary project automatically. Verification commands can own runtime checks, but readiness/HTTP semantics require actual qualification. Foreground watch, actual-project measurements, installed-consumer workflow and full real application acceptance remain separate required work.

### Observing declared changes

Run `patamaps project-build-input-key PLAN --source OWNER` to observe the
same input key used by `project-build`, without creating build state or executing
providers, build commands or verification commands. The key binds the declared
selected source, plan, configured executable targets and Patamaps engine.
Unknown or missing selected inputs and unavailable configured executables refuse.

This is the polling primitive used by the foreground controller below. It is not an atomic
filesystem snapshot, admission, readiness, a complete dependency closure, or
permission to bypass the storage supervisor. A build still recaptures and verifies
its inputs before publication. Unselected files do not affect this key. The controller below supplies scoped lifecycle and per-update supervision; full
application workflow qualification remains incomplete.

### Foreground watch controller

Native input observation and selected-binding verification each default to a
30-second deadline. For a measured larger context, pass
--inspection-timeout-ms 120000 before --runner to give each inspection up to
two minutes. The accepted range is 1000..3600000 milliseconds. This changes only
the inspection deadline; native validation, per-build policy leases and declared
command budgets still apply. It does not establish practical watch performance.

The generic controller lives in scripts/project_watch.py. Start it outside any
allocating storage lease, after building the CLI:

```sh
python3 scripts/project_watch.py owner-build.json \
  --source /absolute/owner --state /absolute/retained-state \
  --compiler /absolute/patamaps \
  --runner /absolute/node /absolute/storage-supervisor.mjs patamaps --
```

Place --runner last: all remaining arguments are the exact policy command prefix.
On the configured Intel development host, sourcing the development environment
provides the default runner. No runner means refusal when that environment is
absent. Do not wrap the entire watcher in the heavy-run supervisor. Each update
enters the configured runner; idle polling does not acquire its lease.

Rust observes the declared input key, revalidates each build, retains attempts
and publishes selection. The controller debounces changes. Failed keys, including
policy exit75, are not retried until an input change or explicit restart. Missing
inputs report unavailable and preserve existing selection. Returning to an
unchanged successful key uses Rust's no-op verification semantics, without
rerunning build commands or inventing cache hits.

The process wrappers monitor actual parent relationships on both sides of the
policy runner. Cleanup covers ordinary child process groups; independently
detached or adversarial processes are outside that guarantee. Owner-declared
verification commands remain the only readiness evidence. The controller does
not establish arbitrary application HTTP readiness, a complete build context,
dependency closure, performance claims or installed-consumer acceptance.


A zero runner exit also requires native selected-build binding verification and
a match against the current declared input key. A runner that skips the command
cannot claim an update while stale or absent selection remains. This check
repeats artifact/binding verification, not application runtime commands.

Native Intel qualification covers10 controlled workflow/lifecycle cases, plus
separate preflight refusals. See the scoped watch acceptance record. Linux CI
controls use an explicitly isolated runner fixture and retain their own evidence;
they are not substitutes for actual Intel policy execution. Python3.13 on Unix
is the native tested runtime; other runtime coverage belongs to its identified CI.

### Existing application command qualification

The [Avaelus/Seeder record](../acceptance/project-adoption/seeder-actual-next-commands-20261016/receipt.json)
qualifies project-exec on a retained existing Next 16.1.6 monorepo: 878 selected text
inputs, captured nonsecret environment, an explicitly captured configuration
helper, and hash checks on the Next/TypeScript entrypoint scripts. The actual
application build and separate TypeScript 5.9.3 --noEmit check passed. Capture
verification also passed while the configured owner/program paths were
unavailable. That replay checks input bindings, not a new execution or execution
attestation.

This uses an already prepared root. Installed dependencies were retained in a
separately verified snapshot; node_modules remains excluded from the native text
capture. This does not qualify reconstruction through project-build, artifact
selection, watch on this app, generated-contract integration, HTTP/browser
behavior or installed/deployed general workflows. The original checkout remains
unchanged. Next-generated candidate metadata and the qualification helper are
identified separately from original application source.

## Explicit owner preparation

The project-build and project-build-input-key commands accept --preparation
preparation.json together with --context context.json. Existing plan files, Rust
entry points and build behavior remain valid without this opt-in contract.
scripts/project_watch.py accepts the same flag and passes it to input observation
and each native update.

~~~json
{
  "profile": "patamaps-project-preparation-1",
  "commands": [
    {
      "profile": "patamaps-project-command-1",
      "workingDirectory": ".",
      "environmentReferences": {},
      "invocation": {
        "executable": "/absolute/path/to/node",
        "arguments": ["scripts/generate-contract.mjs"],
        "codeInputs": ["scripts/generate-contract.mjs"],
        "bounds": {
          "maximumElapsedMs": 60000,
          "maximumStdoutBytes": 65536,
          "maximumStderrBytes": 65536
        }
      }
    }
  ],
  "outputs": {
    "src/generated/contract.ts": "sha256:<exact-captured-file-preimage>"
  }
}
~~~

Replace the illustrative digest with the actual 64 lowercase hexadecimal digits.
An output value of null requires the path to be absent from the captured context.
Output files must be nonsecret UTF-8 selected-input paths and must be excluded
from the plan's source inputs and workspace emissions. There are at most 32
preparation commands and 64 generated files. Preparation requires a sealed
retained context so its final filesystem membership can be checked. Output
preimages belong to this contract, not to the context's ordinary overlays.
Generated paths cannot overlap the context's build writable paths or credential
paths; these contracts are rejected before preparation commands run.

The driver stages the context and selected inputs, checks each preimage, runs
trusted preparation commands with the existing command supervisor and selected
input checks, then captures the declared generated files. Existing file modes
must match their captured modes. New files use the selected-input mode 0600;
new parent directories use 0700. For shell generators, umask 077 supplies these
modes. Generated files become immutable selected inputs for subsequent build and
verification commands. Preparation does not receive the build's writable-path
allowance: final changes outside declared generated files fail the closed-context
check before build commands start.

Preparation commands and captured output bytes are retained in the existing
attempt. Their contracts and executable bindings contribute to the native input
key, including watch observation. Failed commands, stale preimages, missing or
unsafe outputs, changed selected inputs and undeclared final writes preserve the
previous selection. Selected-build verification checks retained command records,
generated bytes and context bindings without rediscovering original source or
running generation again. An unchanged-key build still reports verification
not-repeated; it does not claim renewed execution.

Commands remain explicitly trusted, not sandboxed. Final filesystem checks do
not prove that no transient writes occurred, and executable dependency closure,
runtime behavior, deployment and application acceptance are separate requirements.
The Rust APIs build_project_with_preparation and
project_build_input_key_with_preparation take optional existing context and
preparation references; old functions delegate with no preparation.

### Migrating an existing generator

Keep the owner's rendering and implementation-coverage checks. Replace only the
graph parsing/compilation/projection calls, then run that same generator as a
preparation command. The retained Next qualification used this pattern with an
unchanged owner generator; its [baseline record](../acceptance/project-adoption/g6-owner-native-preparation-2026-10-16/baseline.json)
binds the actual inputs, compiler hashes and framework checks.

1. Capture the project dependencies, native binary and SDK runtime files inside
   the closed retained context. Opaque binaries belong in the context, not in the
   UTF-8 project input profile. Keep the package layout and internal links intact.
2. Select the graph, policy, projection specification, generator and adapter/SDK
   text as project inputs. Include the actual scripts in command codeInputs.
   Existing limits still apply: at most 1,024 selected text paths, a bounded
   16 MiB capture record, and at most 128 code inputs per command.
3. Remove generated files from project source inputs and workspace emissions.
   Declare each preparation output using its exact captured manifest digest, or
   null for an absent path. Generated files cannot overlap build writable paths.
4. Run the owner generator as preparation, followed by the real framework build,
   type checking and owner verification commands. Generation must fail the build
   when parsing, graph compilation, projection or implementation coverage fails.
5. Verify changed generated content reaches the actual consumer, and a failed
   generation preserves the prior selection. Replaying retained bindings and a
   native no-op do not repeat runtime checks. Installed, HTTP/browser and
   deployment qualification are separate from successful compilation.

For an existing generator that imports original v1 observation APIs, a narrow
adapter can preserve its imports while moving computation into Rust. The example
below assumes these captured files:

~~~text
.patamaps/tools/patamaps
.patamaps/tools/sdk/*.mjs
.patamaps/tools/sdk/package.json
.patamaps/tools/compat.mjs
.patamaps/tools/loader.mjs
~~~

In compat.mjs:

~~~javascript
import { fileURLToPath } from "node:url";
import {
  createLegacyValidationApi,
  createCanonicalApi,
} from "./sdk/index.mjs";

const executable = fileURLToPath(new URL("./patamaps", import.meta.url));
const api = createLegacyValidationApi(executable);
const canonical = createCanonicalApi(executable);

export const RelationRegistry = api.LegacyRelationRegistry;
export const coreRelationPack = api.legacyCoreRelationPack;
export const parseRelationPack = value => api.parseLegacyRelationPack(value);
export const parseViabilityPolicy = value => api.parseLegacyViabilityPolicy(value);
export const parseProjectionSpec = value => api.parseLegacyProjectionSpec(value);
export const compileMetamap = (...args) => api.compileLegacyMetamap(...args);
export const compileProjection = (...args) => api.compileLegacyProjection(...args);
export const stableJson = value =>
  JSON.stringify(canonical.legacyReferenceValue(value), null, 2) + "\n";
~~~

In loader.mjs:

~~~javascript
export async function resolve(specifier, context, nextResolve) {
  if (specifier === "@roryscot/metamap") {
    return {
      url: new URL("./compat.mjs", import.meta.url).href,
      shortCircuit: true,
    };
  }
  return nextResolve(specifier, context);
}
~~~

The generation command uses an absolute configured Node executable, root cwd,
and this argv (replace the owner script path):

~~~json
[
  "--experimental-loader",
  "./.patamaps/tools/loader.mjs",
  "scripts/generate-routes.mjs"
]
~~~

Apply the loader to the generation process only. Framework build and request
processes consume the generated contract; they do not need this loader. Capture
relation packs as explicit data inputs as well. The adapter covers only the
listed original v1 observation APIs; it neither admits a native generation nor
implements arbitrary original SDK exports or executable semantic profiles.
The passing retained case used Node 22.23.3. Other runtimes and generator imports
require their own checks.

Preparation environment references resolve captured nonsecretConfiguration
strings. Secret references remain unresolved labels; capture a separately
declared nonsecret configuration projection instead of raw secret-bearing files.
A captured tool/dependency tree does not itself establish complete executable
dependency closure or practical development-loop performance. The retained case's
500.397-second full build and 34.716-second no-op leave that performance work open.
