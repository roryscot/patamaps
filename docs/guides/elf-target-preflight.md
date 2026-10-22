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
