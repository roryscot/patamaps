# Retained project builds

Run project-build through the applicable project/application storage supervisor:

    patamaps project-build build-plan.json --source /work/service --state /work/build-states/service
    patamaps project-build-verify /work/build-states/service

The state parent must already exist. Its canonical directory must be included in the storage supervisor’s retained-allocation and free-space checks. A symlink inside a counted root is insufficient when accounting skips symlinks. Intel’s Patamaps guard uses explicit retentionRoots for the canonical state parent; verify the check reports that root before building. State must be outside the original source tree and outside every enclosing Cargo workspace. The original source supplies selected bytes; programs run in a new retained candidate, with owner-declared cwd and absolute executable paths.

The plan uses profile patamaps-project-build-1 and embeds five existing declarations:

- project: a patamaps-project-inputs-1 ProjectProfile, explicitly selecting immutable UTF-8 source/configuration/tooling inputs.
- workspace: a WorkspaceConfig whose paths are relative to that staged source. Every capture must be viable before build commands start.
- buildSteps: one or more ProjectCommand declarations.
- verificationSteps: one or more ProjectCommand declarations, run after the initial artifact snapshot.
- outputs: explicit objects with path and kind (file, tree or closed-tree), relative to the candidate.

Generated workspace outputs are staged alongside source and become immutable selected command inputs. Do not also select old copies of those output paths as original source inputs. Program environmentReferences resolve only captured nonsecretConfiguration strings; ambient environment and secret references remain unresolved. See decision0038 for command JSON.

Declared artifact bytes, Unix mode bits and tree membership must stay unchanged through verification and the final source/tool checks. Ordinary file/tree outputs refuse symlinks; all output kinds refuse special files. File size is bounded at4GiB, combined artifact bytes at16GiB, tree depth at128 and entries at32768, with the normal record byte limit. These observations do not attest ACLs, xattrs, dynamic dependencies or runnable architecture.

An explicit output kind closed-tree additionally permits symlinks only when
their resolution stays inside that individual declared tree. The native
fingerprint binds link text and mode, all physical directory/file members and
file bytes/modes, without traversing link targets during enumeration. The
existing internal-context closure validator checks bounded resolution over
that inventory, rejecting absolute/escaping/dangling/cyclic targets. Links cannot
borrow a target from another output root. All existing entry/depth/byte/record
limits apply. Ordinary tree output still refuses every symlink.

Closed trees are private output artifacts, not nonsecret captured inputs.
Their binding and selected execution receive the same pre/post verification as
other artifacts. This does not admit mutable runtime caches or prove standalone
application/dependency closure. [Native verification](../acceptance/project-adoption/g5-native-closed-tree-20261024/attempt-2/independent-verification.json)
at6b5404d passed59 library tests,31 integration tests and strict Clippy, and
selected/verified the real78-link Next standalone tree. That historical
host-served profile failed because its producer tree acquired cache files.
The separate [read-only image runtime](../acceptance/project-adoption/g5-next-retained-runtime-20261024/accepted-40069762886/independent-verification.json)
passed at0a40a4c: the selected generation stayed unchanged while a separate64MiB
cache accepted writes and enforced its quota, with producer sources/tools
unavailable during28 browser groups/four unchanged upstream tests. Actual kernel
CPU/memory/swap/PID limits and owned-runtime cleanup passed. The [exact fresh source/native installed replay](../acceptance/project-adoption/g5-installed-retained-next-20261024/accepted-40071420581/independent-verification.json)
now also passes at80ae616/engine2fc8a201 for that pinned profile. Neither result
establishes full OS/dependency closure, network isolation, performance or
production activation.

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

### Declare frontend and backend error boundaries

A generated transport client validates the errors declared by its owner profile.
When a frontend proxy adds a status that the native service does not emit, include
that status and its actual response schema in the explicit transport declaration.
For example, a Next proxy may return 503 when its Rust upstream is unavailable;
an undeclared 503 correctly refuses as HTTP_ERROR_CONTRACT rather than inventing
a typed error. Keep tests for the legacy refusal, declared error admission and
malformed error-body refusal. Controlled transport replies establish client
contract behavior; qualify actual production listeners and proxy branches
separately before claiming runtime compatibility.

## Execute a verified selection

This command is a checkout feature added after the published 0.1.0-alpha.1 CLI.
Use a CLI built from this revision and the same storage supervisor as the build:

    patamaps project-exec-selected /work/build-states/service run-command.json

The command uses the existing patamaps-project-command-1 schema. Its working
directory is relative to the selected candidate, and environmentReferences
resolve only through the retained nonsecretConfiguration. It does not inherit
the caller's environment or rediscover the original source.

Patamaps acquires the same cooperative driver.lock used by project-build,
verifies the pinned selection and its declared source, generated, context and
compiled output bindings, then launches the explicit trusted command. A stale
declared artifact is refused before the command starts. A competing build or
selected execution is refused while this lock is held. The lock remains held
through command execution and a second selection verification.

Exit 0 means completed-selected-project-command: the command completed under
its bounds, bindings still verify, and the selection pointer is unchanged.
Exit 1 reports refused-selected-project-command after command admission,
including a nonzero command, unresolved environment reference, output mutation
or pointer mutation. Exit 2 reports an operational/preflight refusal; no command
is launched when the selected bindings or lock fail preflight.

The report includes the underlying ProjectCommand report, pointer comparison
and postExecutionVerification. Post-command refusal cannot undo command effects. A selected file digest does not prove it was compiled from the emitted
source; the build verification steps must establish that relationship.
These are declared-byte checks and a cooperative lock, not filesystem isolation
against hostile writers, dependency closure, continuous runtime monitoring, or
permission to deploy or activate anything. An undeclared output is not covered.
Use bounded startup probes or functional checks; long-running services hold the
lock until they finish. Ordinary child process groups retain the CLI's existing
parent-death cleanup; detached processes and external services require their
own lifecycle controls.

Build verification is tied to the creating engine. Preserve the creating CLI
and evidence before changing engine source; do not silently reinterpret old
selections under a different engine.

The [authentic client receipt](../acceptance/project-adoption/g5-authentic-client-selected-exec-20261022/receipt.json)
records native TypeScript emission, compilation from captured compiler inputs,
selected module loading, older-artifact refusal before module load, and restoration.
It does not repeat real application/network acceptance.


The packaged scripts/installed_selected.py wrapper verifies the exact installed
source inventory and executes these same native commands. Its existing default
is180 seconds for each complete call. For a larger declared context, configure
--inspection-timeout-seconds and --execution-timeout-seconds explicitly; each
accepts integers1..3600. Inspection covers engine and selected binding checks;
execution covers the entire selected call, including native pre/post checks.
The receipt records both settings and each command's effective timeout. These
outer wrapper limits do not change the trusted native command's own bounds or
prove practical latency. The wrapper still requires the existing host supervisor
outside its qualified GitHub Linux environment.
