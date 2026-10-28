# Native cancellation ownership isolation

Status: fixed single-process kernel prerequisite independently passes on Intel
macOS15.8.1; trusted-controller integration and automatic release remain unqualified.
This follows the actual
[parent-death release failure](../acceptance/project-adoption/original-owner-active-parent-death-20261028/receipt.json).
The approved metadata recovery is complete. Full G0–G6 adoption and W0/W1 remain
open; the original no-op/idle/SIGTERM pass remains accepted.

## Scope and acceptance

The failure is in the native cancellation ownership boundary. A dead process
group and unchanged container IDs cannot exclude work inside an existing
container. Preserve the current conservative guard for every unconfined or
uncertain workload. Do not stop the unrelated database or weaken its checks.

First qualify a fixed, opt-in Darwin single-process inspection primitive.
It must deny new processes, network/Unix connections, broker lookup and writes
outside its declared private work directory. Start a new session, close extra
descriptors, and give the payload pipe-based standard streams. Existing open
descriptors are significant: Apple's local sandbox(7) says restrictions are
generally checked when acquiring resources. A network-only rule is insufficient.
The installed sandbox-exec(1) also labels the tool deprecated; qualify only the
observed host/runtime and refuse unavailable/changed enforcement.

The primitive is for inspection, not arbitrary builds that fork. It grants
filesystem reads required by the bound tools; existing source/configuration
capture allowlists still apply. It does not establish CPU/memory quotas,
general sandbox escape resistance or automatic reservation release.

## Increment order

1. Inspect current supervisor code, platform documentation and failure receipts.
2. Implement the fixed primitive and a guarded real-kernel qualifier using
   test-owned files, socket listeners and signal handlers only. Freeze20
   positive/negative controls, four root refusals, ordinary unsandboxed endpoint
   baselines, exec persistence, fork/posix_spawn refusal, session identity and
   descriptor/connected-stdin closure. Preserve all attempt outputs and sources.
   Initial qualification plus at most two evidence-backed repairs; do not
   remove controls or broaden network/IPC/process/write permissions for a pass.
3. Review trusted-controller integration into existing execution contracts.
   Only a verified isolated path may suppress preexisting-container uncertainty;
   declarations, environment flags or a child-reported token alone cannot.
   Keep process/stream/container stop checks and default fallback unchanged.
   No installed supervisor modification or parallel activation occurs in step2.
4. Verify integration with controlled cancellation/crash and enforcement-change
   refusals before proposing another bounded real-owner parent-death case.
   Bind exact helper/CLI/config/runtime identities. The previous case approval
   and its recovery approval are consumed; they do not authorize a repeat.
5. Close actual parent-death only after the real case meets the unchanged60s
   release criterion. Continue changed-generation, authenticated-owner,
   deployment, installed-consumer and actual performance requirements afterward.

All allocating qualification uses the existing Intel canonical supervisor:
4GB growth,500MB reserve,100GB retention, native-exclusive fallback.
No file deletion, service interruption, resource-policy increase, VM, registry/
production/trust activation or parallel activation is included.

## Platform evidence

Use the current host's Apple sandbox-exec(1), sandbox(7) and public system
profiles as execution-specific evidence, including descriptor acquisition and
inheritance rules. Apple's [App Sandbox documentation](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox)
describes broader sandbox capabilities; it is not a specification for this
deprecated command's private profile language. Actual kernel denial tests are
required before making an enforcement claim.


## Kernel prerequisite result

[Independent review](../acceptance/project-adoption/native-inspection-kernel-20261028/receipt.json)
passed all20 frozen kernel controls, four unsafe-root refusals and four
unsandboxed endpoint baselines on Intel macOS15.8.1. Exec-in-place retained the
restrictions; fork/posix_spawn, outside writes/signals, TCP4/TCP6/Unix and Mach
lookup denied. The connected-stdin and explicitly inheritable extra-descriptor
controls passed. Allowed fixture read/write succeeded. All known test processes
stopped and the canonical reservation released. Attempt0 passed without repairs;
all sources, outputs and fixture files remain preserved.

This does not qualify automatic reservation release, arbitrary builds, native
CPU/memory enforcement or the actual owner under this profile. Next inspect the
existing read-only CLI under the same fixed primitive, then integrate only a
trusted controller whose entire untrusted execution is demonstrably confined.
The installed guard and native fallback have not changed.
