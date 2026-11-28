#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync, renameSync, readdirSync, existsSync, realpathSync, statfsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { randomUUID, createHash } from 'node:crypto';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

export const defaultDirectory = path.join(os.homedir(), 'Documents/Codex/.storage-control/heavy-builds');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const now = () => new Date().toISOString();
function read(file, fallback) {
  try { return JSON.parse(readFileSync(file, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return fallback; throw error; }
}
function save(file, value) {
  const staging = `${file}.${randomUUID()}.staging`;
  writeFileSync(staging, JSON.stringify(value, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  renameSync(staging, file);
}
export function alive(pid) {
  if (!Number.isSafeInteger(pid) || pid <= 0) return null;
  try { process.kill(pid, 0); return true; }
  catch (error) { return error.code === 'ESRCH' ? false : null; }
}
export function processIdentity(pid) {
  if (alive(pid) !== true) return null;
  try { return execFileSync('/bin/ps', ['-p', String(pid), '-o', 'lstart='], { encoding: 'utf8', timeout: 2000 }).trim() || null; }
  catch { return null; }
}
export function nativeFinalizationPending(r) {
  if (r.enforcement !== 'native-exclusive' || r.state !== 'finished' || r.leaseReleaseCompleted === true) return false;
  if (alive(r.owner?.pid) === false) return false;
  const current = processIdentity(r.owner?.pid);
  return current === null || typeof r.owner?.identity !== 'string' || current === r.owner.identity;
}

export function canonical(location) {
  let current = path.resolve(location), tail = [];
  while (!existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) throw new Error('Cannot establish output identity');
    tail.unshift(path.basename(current)); current = parent;
  }
  return path.join(realpathSync(current), ...tail);
}
export function overlap(a, b) {
  return a === b || a.startsWith(b + path.sep) || b.startsWith(a + path.sep);
}
export function outputConflict(a, b) {
  return a.outputs.some(x => b.outputs.some(y => overlap(x, y))) ||
    a.instances.some(x => b.instances.includes(x));
}
export function redactCommand(command) {
  let hide = false;
  return command.map(value => {
    if (hide) { hide = false; return '[redacted]'; }
    if (/^--?(?:password|token|secret|api[-_]?key|authorization)(?:=|$)/i.test(value)) {
      if (!value.includes('=')) hide = true;
      return value.split('=')[0] + '=[redacted]';
    }
    if (/:\/\/[^/]*@/.test(value)) return '[redacted-url]';
    return value;
  });
}
export function nativeRequest({ project, command, diskBytes, root, label, phase = 'functional', outputs = [root], instances = [] }) {
  if (!['functional', 'diagnostic', 'benchmark'].includes(phase)) throw new Error('Invalid phase');
  if (!Number.isSafeInteger(diskBytes) || diskBytes <= 0) throw new Error('Declare a positive maximum disk growth');
  return { project: canonical(project), command: redactCommand(command), label, phase,
    outputs: outputs.map(canonical), instances,
    limits: { cpu: os.availableParallelism(), memoryBytes: os.totalmem(), diskBytes },
    enforcement: 'native-exclusive', exclusive: true };
}

// Stage 2 planner. Runtime admission is deliberately disabled until the real
// backend's qualification is retained. Declarations alone are never evidence.
export function parallelEnabled(directory=defaultDirectory) {
  try {
    const config=read(path.join(directory,'scheduler/parallel.json'),null);
    if(config?.version!==3||config.enabled!==true||config.host!==os.hostname())return false;
    const base=path.dirname(fileURLToPath(import.meta.url));
    if(!['buildctl.mjs','resource-executor.mjs','buildctl-cli.mjs'].every(name=>config.bindings?.some(b=>b.file===path.join(base,name)&&
      createHash('sha256').update(readFileSync(b.file)).digest('hex')===b.sha256)))return false;
    if(!config.bindings.every(b=>path.isAbsolute(b.file)&&/^[0-9a-f]{64}$/.test(b.sha256)&&createHash('sha256').update(readFileSync(b.file)).digest('hex')===b.sha256))return false;
    const receipt=read(config.receipt);
    const required=['system-metadata-readonly','native-finalization-handoff','actual-guard-native-followup-managed-progress','two-job-overlap','simultaneous-acquisition','writable-enospc','fixed-image-bound','kernel-limits',
      'queued-cancellation','running-cancellation','owner-crash-surviving-container','confirmed-crash-recovery',
      'output-conflict','instance-conflict','benchmark-exclusive','native-barrier','fair-queue','unmanaged-fallback','capacity-refusal','altered-enforcement-refusal','pause-preserved','cli-integration','persistent-output-restart'];
    return createHash('sha256').update(readFileSync(config.receipt)).digest('hex')===config.receiptSha256&&
      receipt.status==='passed-stage-two-runtime'&&receipt.host===config.host&&receipt.engineId===config.engineId&&required.every(x=>receipt.controls?.includes(x));
  } catch { return false; }
}
export const parallelActivated = parallelEnabled();
export const interactiveReserve = { cpu: 2, memoryBytes: 4 * 1024 ** 3, diskBytes: 5 * 1024 ** 3 };
export function usableCapacity(machine, reserve = interactiveReserve) {
  if (!machine || !['cpu', 'memoryBytes', 'diskBytes'].every(k => Number.isFinite(machine[k]) && machine[k] >= 0)) return null;
  return Object.fromEntries(['cpu', 'memoryBytes', 'diskBytes'].map(k => [k, Math.max(0, machine[k] - reserve[k])]));
}
export function verifyContainerLimits(inspect, request) {
  const h = inspect?.HostConfig, c = inspect?.Config;
  if (!h || !c || !inspect.Id || !inspect.State || inspect.State.Running !== false)
    throw new Error('Container must be inspected stopped before admission');
  if (c.Labels?.['buildctl.request'] !== request.id || c.Labels?.['buildctl.project'] !== request.project)
    throw new Error('Container ownership mismatch');
  if (h.Privileged || h.PidMode === 'host' || h.IpcMode === 'host' || h.NetworkMode === 'host' || h.AutoRemove)
    throw new Error('Unsafe or unrecoverable container isolation');
  if (h.NetworkMode !== 'none' || !h.CapDrop?.includes('ALL') || (h.CapAdd ?? []).length ||
      !h.SecurityOpt?.some(x => /^no-new-privileges(?::true)?$/.test(x)) ||
      (h.Devices ?? []).length || (h.DeviceRequests ?? []).length || (h.VolumesFrom ?? []).length)
    throw new Error('Unqualified network, privilege or device access');
  if (!h.ReadonlyRootfs || (inspect.Mounts ?? []).length || Object.keys(h.Tmpfs ?? {}).length)
    throw new Error('Writable mounts need an independently verified disk quota backend');
  if (c.Volumes && Object.keys(c.Volumes).length) throw new Error('Image declares writable volumes');
  if (h.NanoCpus !== Math.round(request.limits.cpu * 1e9) || h.Memory !== request.limits.memoryBytes ||
      h.MemorySwap !== h.Memory || !Number.isSafeInteger(h.PidsLimit) || h.PidsLimit <= 0)
    throw new Error('CPU, memory, swap and PID enforcement required');
  if (h.LogConfig?.Type !== 'none') throw new Error('Unbounded container logs are not allowed');
  if (request.phase === 'diagnostic' && !(h.CpuShares > 0 && h.CpuShares <= 128))
    throw new Error('Diagnostics require low scheduling priority');
  return { containerId: inspect.Id, requestId: request.id, cpu: request.limits.cpu,
    memoryBytes: request.limits.memoryBytes, diskBytes: request.limits.diskBytes,
    readonly: true, observedAt: now() };
}
export function admission(request, active, capacity, evidence) {
  if (!capacity || ![capacity.cpu, capacity.memoryBytes, capacity.diskBytes].every(x => Number.isFinite(x) && x >= 0))
    return 'unknown capacity';
  if (active.some(x => outputConflict(request, x))) return 'shared output or application instance';
  if (active.length && (request.exclusive || request.phase === 'benchmark' ||
      active.some(x => x.exclusive || x.phase === 'benchmark'))) return 'exclusive work';
  if (active.length >= 2) return 'two-job limit';
  for (const r of [request, ...active]) {
    if (!r.exclusive && (!evidence?.[r.id] || evidence[r.id].requestId !== r.id ||
        evidence[r.id].cpu !== r.limits.cpu || evidence[r.id].memoryBytes !== r.limits.memoryBytes ||
        evidence[r.id].diskBytes !== r.limits.diskBytes || !evidence[r.id].readonly)) return 'unverified enforcement';
  }
  for (const key of ['cpu', 'memoryBytes', 'diskBytes']) {
    if (![request, ...active].every(r => Number.isFinite(r.limits[key]) && r.limits[key] > 0)) return 'invalid reservation';
    if ([request, ...active].reduce((n, r) => n + r.limits[key], 0) > capacity[key]) return `insufficient ${key}`;
  }
  return null;
}
export function fairHead(requests, grants) {
  const waiting = requests.filter(r => r.state === 'queued');
  return waiting.sort((a, b) => (grants[a.project] ?? -1) - (grants[b.project] ?? -1) || a.sequence - b.sequence)[0];
}

export class Scheduler {
  constructor(directory = defaultDirectory) {
    this.directory = directory;
    this.root = path.join(directory, 'scheduler');
    mkdirSync(path.join(this.root, 'requests'), { recursive: true });
    mkdirSync(path.join(this.root, 'transactions'), { recursive: true });
  }
  requests() {
    return readdirSync(path.join(this.root, 'requests')).filter(x => x.endsWith('.json'))
      .map(x => read(path.join(this.root, 'requests', x))).sort((a, b) => a.sequence - b.sequence);
  }
  file(id) {
    if (!/^[0-9a-f-]{36}$/.test(id)) throw new Error('Invalid request ID');
    return path.join(this.root, 'requests', `${id}.json`);
  }
  transaction(fn) {
    const lock = path.join(this.root, 'transaction');
    try { mkdirSync(lock); }
    catch (error) { if (error.code === 'EEXIST') { const e = new Error('Scheduler transaction busy; ownership retained'); e.code = 'BUSY'; throw e; } throw error; }
    try {
      save(path.join(lock, 'owner.json'), { pid: process.pid, startedAt: now() });
      return fn();
    } finally {
      // Preserve every transaction, including failed operations. A crashed
      // transaction stays locked for explicit review rather than guessing.
      renameSync(lock, path.join(this.root, 'transactions', randomUUID()));
    }
  }
  enqueue(spec) {
    return this.transaction(() => {
      const meta = read(path.join(this.root, 'meta.json'), { next: 0, grants: {} });
      const request = { ...spec, id: randomUUID(), sequence: meta.next++, state: 'queued',
        owner: { pid: process.pid, identity: processIdentity(process.pid), user: os.userInfo().username },
        createdAt: now(), heartbeat: now(), progress: 'Waiting for admission', processGroup: null,
        containerIds: [], ownershipSealed: false };
      save(path.join(this.root, 'meta.json'), meta); save(this.file(request.id), request); return request;
    });
  }
  update(id, fields) {
    // Only the live request owner writes these fields. Atomic replacement keeps
    // readers consistent without generating a transaction archive per heartbeat.
      const record = read(this.file(id));
      if (!record || record.owner.pid !== process.pid || record.owner.identity !== processIdentity(process.pid))
        throw new Error('Request ownership mismatch');
      for (const key of Object.keys(fields)) if (!['heartbeat', 'progress', 'processGroup', 'ownershipSealed'].includes(key))
        throw new Error('Unsupported request update');
      Object.assign(record, fields); save(this.file(id), record); return record;
  }
  tryAcquire(id, acquire) {
    return this.transaction(() => {
      const all = this.requests();
      for (const r of all) if (r.state === 'queued' && alive(r.owner.pid) === false) {
        r.state = 'cancelled'; r.progress = 'Queued owner confirmed stopped before admission'; save(this.file(r.id), r);
      }
      const request = all.find(r => r.id === id);
      if (!request || request.state !== 'queued') throw new Error('Request is not queued');
      if (request.owner.pid !== process.pid) throw new Error('Request ownership mismatch');
      const meta = read(path.join(this.root, 'meta.json'));
      if (fairHead(all, meta.grants)?.id !== id) return null;
      const active = all.filter(r => ['running', 'needs-review'].includes(r.state));
      if (active.length || all.some(nativeFinalizationPending)) return null;
      // Older guards use this same atomic directory. Never reclaim their lock
      // from a missing PID: child/container ownership is unrecorded.
      if (existsSync(path.join(this.directory, 'active-run'))) return null;
      const lease = acquire();
      lease.phase = request.phase;
      save(path.join(this.directory, 'active-run/owner.json'), { ...lease,
        project: request.project, phase: request.phase, command: request.command, requestId: request.id });
      request.state = 'running'; request.startedAt = now(); request.heartbeat = now();
      request.progress = 'Admitted exclusively; preparing guarded workload';
      save(this.file(id), request);
      meta.grantSequence = (meta.grantSequence ?? 0) + 1;
      meta.grants[request.project] = meta.grantSequence; save(path.join(this.root, 'meta.json'), meta);
      return lease;
    });
  }
  cancel(id) {
    return this.transaction(() => {
      const r = read(this.file(id));
      if (!r || r.state !== 'queued' || r.owner.pid !== process.pid) throw new Error('Only the queued owner can cancel');
      r.state = 'cancelled'; r.finishedAt = now(); r.progress = 'Cancelled before admission'; save(this.file(id), r);
    });
  }
  finish(id, stopped, releaseStoppedLease = null) {
    return this.transaction(() => {
      const r = read(this.file(id));
      if (r.owner.pid !== process.pid) throw new Error('Request ownership mismatch');
      // Finish and legacy lease archival share the admission transaction.
      if (stopped && releaseStoppedLease) releaseStoppedLease();
      r.leaseReleaseCompleted = stopped && typeof releaseStoppedLease === 'function';
      r.state = stopped ? 'finished' : 'needs-review'; r.finishedAt = now(); r.heartbeat = now();
      r.progress = stopped ? 'Owned workload confirmed stopped' : 'Owned workload stop unconfirmed; reservation retained';
      save(this.file(id), r);
    });
  }
  status() {
    const raw = read(path.join(this.directory, 'active-run/owner.json'), null);
    const enabled=parallelEnabled(this.directory);
    return { version: 2, parallelActivated:enabled, mode:enabled?'verified-reservations-with-exclusive-fallback':'exclusive-fallback', observedAt: now(),
      interactiveReserve,
      machine: { cpu: os.availableParallelism(), memoryBytes: os.totalmem(),
        freeMemoryBytes: os.freemem(), freeDiskBytes: Number(statfsSync(this.directory, { bigint: true }).bavail * statfsSync(this.directory, { bigint: true }).bsize) },
      legacyLease: raw ? { pid: raw.pid, label: raw.label, startedAt: raw.startedAt,
        project: raw.project ?? 'unrecorded-legacy-project', phase: raw.phase ?? 'unknown-legacy-phase',
        command: raw.command ?? ['unrecorded-legacy-command'],
        ownerAlive: alive(raw.pid), recovery: 'No automatic release without owned-workload proof' } : null,
      transactionBlocked: existsSync(path.join(this.root, 'transaction')),
      requests: this.requests().map(r => {
        const h=read(path.join(this.root,'heartbeats',`${r.id}.json`),{});
        return { ...r,...h,ownerAlive:alive(r.owner.pid),
          cancellationRequested:existsSync(path.join(this.root,'cancellations',`${r.id}.json`)),
          heartbeatStale:['queued','running','needs-review'].includes(r.state)&&Date.now()-Date.parse(h.heartbeat??r.heartbeat)>15000 };
      }) };
  }
}

export async function queueLease(directory, spec, acquire, { signal, pollMs = 500, onQueued = () => {} } = {}) {
  const scheduler = new Scheduler(directory);
  let request;
  while (!request) {
    if (signal?.aborted) throw new Error('Queue cancelled');
    try { request = scheduler.enqueue(spec); }
    catch (error) { if (error.code !== 'BUSY') throw error; await sleep(pollMs); }
  }
  onQueued(request.id);
  try {
    for (;;) {
      if (signal?.aborted) { scheduler.cancel(request.id); throw new Error('Queue cancelled'); }
      try {
        const occupied = existsSync(path.join(directory, 'active-run')) ||
          scheduler.requests().some(r => ['running', 'needs-review'].includes(r.state));
        const lease = occupied ? null : scheduler.tryAcquire(request.id, acquire);
        if (lease) return { ...lease, buildctlRequest: request.id };
        scheduler.update(request.id, { heartbeat: now() });
      } catch (error) { if (error.code !== 'BUSY') throw error; }
      await sleep(pollMs);
    }
  } catch (error) {
    try { scheduler.cancel(request.id); } catch { /* retained for explicit review */ }
    throw error;
  }
}

export function workloadStopped(pgid) {
  if (!Number.isSafeInteger(pgid) || pgid <= 0) return false;
  try { process.kill(-pgid, 0); return false; }
  catch (error) { return error.code === 'ESRCH'; }
}
export function containerSnapshot() {
  const executable = ['/Applications/Docker.app/Contents/Resources/bin/docker', '/usr/local/bin/docker', '/opt/homebrew/bin/docker'].find(existsSync);
  if (!executable) return { known: true, ids: [], backend: 'not-installed' };
  try {
    const ids = execFileSync(executable, ['ps', '--quiet', '--no-trunc'], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'] }).trim().split('\n').filter(Boolean);
    return { known: true, ids, backend: 'docker' };
  } catch { return { known: false, ids: [], backend: 'docker', reason: 'Runtime ownership cannot be inspected' }; }
}

export function confirmedStopped(record, { groupStopped = workloadStopped, inspectContainer } = {}) {
  if (!record.ownershipSealed || !record.processGroup || !Array.isArray(record.containerIds)) return false;
  if (!groupStopped(record.processGroup)) return false;
  for (const id of record.containerIds) {
    let state;
    try { state = inspectContainer?.(id); } catch { return false; }
    if (!state || state.Id !== id || state.State?.Running !== false || state.State?.Paused || state.State?.Restarting) return false;
  }
  return true;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2);
    if(args[0]==='status') {
      if(args.some((x,i)=>i>0&&x!=='--watch'))throw new Error('Use status [--watch]');
      const scheduler = new Scheduler();
      const show = () => console.log(JSON.stringify(scheduler.status(), null, 2));
      show(); if (args.includes('--watch')) setInterval(show, 2000);
    }else throw new Error('Use the buildctl launcher for prepare, run, cancel or recover');
  } catch (error) { console.error(error.message); process.exitCode = 75; }
}
