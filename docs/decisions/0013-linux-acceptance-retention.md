# Linux host acceptance and fixture preservation

C12 requires actual Linux execution on x86_64 and ARM64. The native workflow
prepares both hosted architectures, pins the official checkout/artifact Actions
commits, installs the declared Rust toolchain, and runs debug native tests plus
the protected host tests against separately built release production binaries.
Actual architecture, UID, source inventory, binary hashes and executor identities
are recorded. A workflow definition or a cross-compilation is not platform
acceptance.

The test runner uses isolated fixture trust with known test keys. It does not
install production trust or activate a production consumer. The fixture root
and `TMPDIR` are a fresh root-owned directory under `/tmp`. Complete stdout,
stderr, receipts and fixture archives are retained, including failed runs.
Artifact collection runs even after failure.

The prior Patamaps test source is byte-preserved in
[the retention transition record](../history/linux-fixture-retention-2026-10-14T16-27-27.254546Z/receipt.json).
Original MetaMap tests and expected results are not edited. Patamaps cleanup
now renames the former pointer, symlink and lock files into a fixture archive;
fixture destruction is replaced with a retained-path report. All original
refusal/success assertions remain.

The hard-link test retains both links and their shared inode. The subsequent
positive control recreates the exact original trust bytes at the configured path
with one link and the original permission mode. It additionally checks byte
equality. This preserves the original hard-link refusal and the subsequent
ordinary publication test. Linux execution must verify the changed restoration
step; static inspection does not prove it.

The owner approved requesting `workflow` scope for the existing Rory CLI login.
The refresh flow recognized `roryscot` and reached GitHub's passkey confirmation;
completion and the resulting token scopes still require verification. The prior
token reported `gist`, `read:org` and `repo`. The workflow stays local until
authentication completes. Current Linux gates remain open; historical ARM64/ext4
evidence retains its original source and binary identities. No local VM is
created by this workflow.

Runner labels were checked against the official
[GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The current published draft remains separate from registry publication and
production installation, bootstrap or activation.
