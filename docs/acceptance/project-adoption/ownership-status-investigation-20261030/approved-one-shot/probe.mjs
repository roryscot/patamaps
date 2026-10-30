
import { inheritedLease } from '/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs';
import { Scheduler, processIdentity, nativeFinalizationPending } from '/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import { execFileSync } from 'node:child_process';
import { MacDocker } from '/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs';
const diag=stage=>process.stderr.write(JSON.stringify({stage,atMs:Date.now()})+'\n');diag('module-imports-complete');
diag("lease-before");
const lease=inheritedLease();if(!lease)throw Error('MEASUREMENT_LIVE_PARENT_REQUIRED');
diag("lease-after");
diag("status-before");
const s=new Scheduler(process.env.WARGAME_STORAGE_LEASE_DIR).status();
diag("status-after");
const r=s.requests.find(x=>x.id===lease.requestId);if(!r)throw Error('MEASUREMENT_REQUEST_REQUIRED');
diag("ancestry-before");
let p=process.ppid,ancestor=false;for(let n=0;n<64&&p>1;n++){if(p===lease.pid){ancestor=true;break;}p=Number(execFileSync('/bin/ps',['-p',String(p),'-o','ppid='],{encoding:'utf8'}).trim());}
diag("ancestry-after");
diag("pressure-before");
const pressure=Number(execFileSync('/usr/sbin/sysctl',['-n','kern.memorystatus_vm_pressure_level'],{encoding:'utf8',timeout:15000}).trim());
diag("pressure-after");
diag("memory-before");
const memory=execFileSync('/usr/bin/memory_pressure',['-Q'],{encoding:'utf8',timeout:15000}).match(/System-wide memory free percentage:\s*(\d+)%/);if(!memory)throw Error('MEASUREMENT_MEMORY_TELEMETRY');
diag("memory-after");
const percent=Number(memory[1]);if(percent<0||percent>100)throw Error('MEASUREMENT_MEMORY_TELEMETRY');
diag("containers-before");
const ids=new MacDocker().running();
diag("containers-after");
diag("proof-output-before");
process.stdout.write(JSON.stringify({id:r.id,ownerPid:lease.pid,phase:r.phase,state:r.state,project:r.project,
 ownerAlive:r.ownerAlive,ownerIdentityVerified:r.owner.identity===processIdentity(lease.pid),ownerIsAncestor:ancestor,
 exclusive:r.exclusive,enforcement:r.enforcement,resourceLimits:r.limits,nativeResourceCapsEnforced:false,heartbeatStale:r.heartbeatStale,cancellationRequested:r.cancellationRequested,
 memoryPressureLevel:pressure,memoryPressureFreePercentage:percent,memoryPressureCapacityEstimateBytes:Math.floor(Math.max(0,percent-1)*s.machine.memoryBytes/100),otherActiveReservations:s.requests.filter(x=>x.id!==r.id&&(['running','needs-review'].includes(x.state)||nativeFinalizationPending(x))).length,
 runningContainers:ids.length,interactiveReserve:s.interactiveReserve,machine:s.machine}));

diag("proof-output-after");
