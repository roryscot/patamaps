# ELF target preflight

Development-tree command (not included in the published 0.1.0-alpha.1 CLI):

```sh
patamaps elf-target-check retained/bin/server \
  --target linux/amd64 \
  --digest "$EXPECTED_SHA256"
```

Set EXPECTED_SHA256 to the full sha256: digest from the reviewed producer receipt.

Supported targets are `linux/amd64` and `linux/arm64`. The command reads a
regular file up to 256 MiB, binds all observed bytes to the supplied digest and
checks the ELF64 little-endian version-1 header, generic/Linux OSABI, executable
or shared-object type and declared machine. Unix leaf symlinks and nonregular
inputs refuse. It writes only JSON to stdout on success and executes no artifact.
A refusal exits nonzero with an `ELF_*` diagnostic.

Use the digest from the selected producer/context receipt, rather than treating
a newly computed digest of an unknown file as evidence of its provenance.
An owner may invoke the check through an existing `verificationSteps`
`ProjectCommand`; declare the CLI, arguments, command bounds and applicable
captured inputs using the existing contract. The check is opt-in; it does not
automatically change existing build or launch behavior.

`matched-elf-target-header` is a scoped header observation. A generic ELF OSABI
does not prove Linux; shared objects may lack an executable entry point.
Program segments, dynamic loader, libraries, CPU features, dependencies and
actual runtime behavior are unverified. The inspected path could change before
a later, separate launch. Retain immutable artifact bindings and qualify the
real runtime independently. This check grants no deployment authorization and
does not close G5 wrong-architecture runtime or stale generated-contract gates.

Header fields and machine values follow the primary
[ELF header specification](https://gabi.xinuos.com/elf/02-eheader.html) and
[assigned machine registry](https://gabi.xinuos.com/elf/a-emachine.html).


## Verify a known runtime before selection

Put the following command in an existing ProjectBuild plan's verificationSteps.
Replace the checker path and digest with your pinned checker and reviewed
producer receipt. Capture the opaque runtime through the normal context binding.
Select runtime as an explicit file output.

```json
{
  "profile": "patamaps-project-command-1",
  "workingDirectory": ".",
  "environmentReferences": {},
  "invocation": {
    "executable": "/absolute/path/patamaps",
    "arguments": [
      "elf-target-check",
      "runtime",
      "--target",
      "linux/amd64",
      "--digest",
      "sha256:REPLACE_WITH_REVIEWED_64_LOWERCASE_HEX_DIGEST"
    ],
    "codeInputs": [],
    "bounds": {
      "maximumElapsedMs": 60000,
      "maximumStdoutBytes": 65536,
      "maximumStderrBytes": 65536
    }
  }
}
```

Failure preserves the prior selected.json. State must be outside the source and
every enclosing Cargo workspace, in a root counted by the storage supervisor.
This pattern checks a prebuilt artifact with a known producer digest; it does
not infer one for arbitrary fresh build output.

The [actual Rust component case](../acceptance/project-adoption/g5-native-architecture-selection-20261022/receipt.json)
verified x86_64 selection, authentic ARM64 refusal, unchanged pointer, offline
replay and harmless selected Linux execution. It did not activate the component
or qualify an external project's deployment.
