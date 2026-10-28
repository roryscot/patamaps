# Original Next runtime architecture qualification

Status: planned independent G5 increment. The retained-dynamic Chatbot phase has
exhausted its runtime budget; its symbol-profile proposal remains unapplied and
awaits approval. This increment uses the separately retained actual Next 16.1.6
owner output. It does not retry that Chatbot phase or any I3e/API/benchmark case.
The full G0–G6 adoption objective remains unchanged.

## Existing inputs and implementation

Reuse the digest-bound native `elf-target-check`, native ProjectContext,
ProjectBuild selection/refusal/offline verification, and the existing resource
executor. The ELF API and self-hosted architecture-selection controls already
pass at their recorded sources. Add no parser, graph framework or build system.

The accepted actual owner runtime is still present in the retained deployment
workspace a96986e9-673c-4940-8d68-71e08ed53e85. Its fixed expected manifest names
2,480 application files, no links, build ID 88oi95a5YM6PvetCCaAoU, and Linux
build-receipt digest a4cb438d9e3edb3e89f2680ec8917496b381a4641b27954c326bb167099a81eb.
Its expected.json digest is b08b5a281185568cc48a14a533339ad49a7656bf433c060a098245ad03a88577.
The directly referenced original-owner receipt records commit
c61d51a57120abbbca65d4cb4a432c1cef9343bb and source context
f873090e94e1f019dc664f52e0c0bc9648fe260b9f65a942f72b856e341709c3.
The later installed capture is cd9edf4dc51b3a2089620cb68441e852c5a233f031650a905d4e9a214502e33a;
record this declared SDK/generation lineage separately from the original commit.
Read and hash only those declared application members; preserve the separate
old wrong-config variant and every original path. Current observed modes must
be bound separately; do not infer historical modes from that byte-only manifest.
Do not reopen the closed 6cd78da3 build workspace or rebuild the application.

Reuse its pinned Node 24.11.1 x64 binary
5796fd9700e83170bc7ddfdf7f18858c794a9f91cb39dd6f9e95060b292f2563
(121,116,896 bytes). Original archive checksum matches the official x64 release.
For the negative candidate, acquire only the genuine same-version ARM64 Node
from the official archive. Freeze archive checksum
6b0863fb9f627bf4a6c5948dce1de4398174a2e05dbe717503d828e211ca01f0,
member node-v24.11.1-linux-arm64/bin/node. Retain the archive and selected member;
do not fabricate an ELF machine header or unpack unrelated dependencies.

The existing Darwin CLI cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355
reports compiler7261d652/workspacef086e884. Confirm its engine and unchanged
relevant Rust inputs before reuse. For the managed Linux verification command,
extract only the exact native CLI from the already verified b6157b8 artifact
12851904399, ZIP digest eecf2a8d57cc0361f427129ddce98006a9d6190b50b68810ec7dab43486589ce.
Native executable digest aaefe1394d50b3e11b1465fef4a0be1885089c8e108e317120cb09d55cf85455.
Decode the archive in memory; verify exact distribution/member/source identities.
Do not retain another raw CI ZIP or dependency tree.

## Frozen acceptance and sequence

1. Record read-only eligibility: original application/build/Node/CLI/manifest
   identities and bounded native matching-target observation. This is preparation,
   not application, architecture-refusal or selection acceptance.

2. Under canonical native-exclusive admission, acquire the one ARM64 archive
   (80 MiB compressed, 256 MiB selected-member, 1 GiB aggregate scan bounds).
   Native ELF checks must match x64/amd64 and ARM64/arm64 with their actual digests,
   then refuse authentic ARM64 for declared linux/amd64 with ELF_ARCHITECTURE.
   Correct digest must be supplied so this cannot pass by ELF_BINDING refusal.

   Reuse the existing owner-declared runtime selection pattern for Node, with
   explicit public nonsecret producer metadata and opaque context capture.
   Select x64, attempt ARM64 with the same declared amd64 requirement, preserve
   selected.json byte-for-byte and verify the accepted x64 state after that
   refusal. Use the established accounted external state envelope outside Cargo.
   Rename only newly owned source/snapshot paths for offline binding verification;
   retain them, then prove exact selection/artifact preservation. This selects
   an existing runtime; no Node or application compilation is performed.

3. Prepare one fresh managed quota workspace. Copy only the 2,480 frozen original
   application members, the selected x64 Node, authentic ARM64 candidate, exact
   Linux ELF-verifier CLI and bounded controller/metadata. Verify copied bytes
   and current modes; retain originals, source states, images and every output.

   In the isolated Linux workload, inspect the actual kernel/volume/namespace
   configuration before effects. Verify CLI engine, source/app/build identities
   and both ELF reports. Start the unchanged actual application with the admitted
   selected x64 Node and observe real public HTML, then stop its child/listener.
   A correct-digest ARM64 candidate must fail native target verification before
   any downstream application launch; prove the launch counter/marker unchanged.
   Then restart the unchanged x64 selection and require real public HTML again.
   Preserve exact app/Node/selection bytes and stop every owned child/listener
   and the owned managed container. Recheck the original protected records.

4. Independently inspect actual receipts, exact source/tool/archive/selection
   bindings and stopped resources. Publish only reviewed bounded hashes/counts/
   outcomes and executed review code. Private runtime files/configuration,
   responses and raw logs stay on Intel.

Use one initial end-to-end attempt and at most two demonstrated repairs for
this independent increment. Preserve failures and reuse completed phases when
their bindings still match; do not repeat a passed application to fix an
inspector. A new failure beyond that budget needs separate approval.

## Resources and limits

All allocating preparation uses the existing canonical Intel supervisor:
4 GB growth, 500 MB reserve, 100 GB retention and native-exclusive fallback.
No policy change. Declare managed functional limits before preparation:
CPU2, memory1.5 GiB, no swap, PIDs256, fixed writable quota1 GiB, read-only root,
network none and no host/source mount. Queue the managed job separately after
native preparation releases; do not nest or bypass fairness.

Use the existing digest-pinned Linux image
69f919497cada9a8611f3de61df902d9f94bf20f84552ef5bd93125c38608ef9.
Verify it and actual enforcement; do not substitute a VM or another project.
Keep 30-second readiness, 2-second requests and existing bounded child cleanup.
Native preparation has a 900-second work budget; managed controller180 seconds.
Admission waits are observations of the same handle, not reasons to restart.
A capacity, ownership, dependency or loader refusal is a recorded failure;
never erase data, expand a limit or borrow a service to obtain a pass.

## Meaning and exclusions

The result, if all gates pass, is explicit digest/target admission before effects
plus actual independent Next startup with the selected correct runtime.
It is not kernel exec-format denial, an automatic check on every CLI invocation,
general ELF/loader/library/OS validity, ARM application execution, authentication,
stale-contract acceptance, performance or a complete deployment release.
Stale generated-contract refusal remains a separate required gate. All earlier
failures, the original-owner API/I3e decisions, benchmark quiet window and the
retained-dynamic retry proposal remain unchanged.

No original source/selection mutation, deletion, service interruption, unrelated
database use, registry/trust/production/parallel activation or application rebuild.
The broader named-owner and full G0–G6 requirements remain open.

Primary references: existing native ELF implementation and the
[architecture-selection receipt](../acceptance/project-adoption/g5-native-architecture-selection-20261022/receipt.json).
Node archive checksum source: https://nodejs.org/dist/v24.11.1/SHASUMS256.txt.
ELF observation limits: https://gabi.xinuos.com/elf/02-eheader.html.
