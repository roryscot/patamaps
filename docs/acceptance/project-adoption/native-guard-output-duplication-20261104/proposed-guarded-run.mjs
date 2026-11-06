import {consumeRegisteredGuardInvocation} from './native_registered_guard_candidate.mjs';
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  statfsSync,
  writeFileSync,
} from "node:fs";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
export const controlDirectory =
  process.env.WARGAME_STORAGE_CONTROL_DIR ??
  path.join(os.homedir(), "Documents", "Codex", ".storage-control", "wargame");
export const sharedLeaseDirectory =
  process.env.WARGAME_STORAGE_LEASE_DIR ??
  path.join(
    os.homedir(),
    "Documents",
    "Codex",
    ".storage-control",
    "heavy-builds",
  );
const schedulerFile = existsSync(new URL("./buildctl.mjs", import.meta.url)) ? fileURLToPath(new URL("./buildctl.mjs", import.meta.url)) : path.join(os.homedir(), "Documents", "Codex", "storage-safeguards", "buildctl.mjs");
const scheduler = existsSync(schedulerFile) ? await import(pathToFileURL(schedulerFile)) : null;
const policyFile = path.join(projectRoot, "storage-policy.json");
const stateFile = (directory) => path.join(directory, "state.json");
const lockDirectory = (directory) => path.join(directory, "active-run");
const now = () => new Date().toISOString();

export function loadPolicy(file = policyFile) {
  const policy = JSON.parse(readFileSync(file, "utf8"));
  if (policy.version !== 1) throw new Error("Unsupported storage policy");
  for (const key of [
    "minimumFreeBytes",
    "reserveFreeBytes",
    "maximumRunGrowthBytes",
    "maximumRetainedBytes",
    "monitorIntervalMs",
    "terminationGraceMs",
  ])
    if (
      !Number.isSafeInteger(policy[key]) ||
      (key === "minimumFreeBytes" ? policy[key] < 0 : policy[key] <= 0)
    )
      throw new Error(`Invalid storage policy: ${key}`);
  if (
    policy.minimumFreeBytes !== 0 &&
    policy.minimumFreeBytes <= policy.reserveFreeBytes
  )
    throw new Error("Starting headroom must exceed the reserve");
  return policy;
}

function json(file, fallback) {
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT" && fallback !== undefined) return fallback;
    throw error;
  }
}

function save(file, value) {
  // Control records belong to this guard, not to application or research data.
  const staging = `${file}.${randomUUID()}.staging`;
  writeFileSync(staging, JSON.stringify(value, null, 2) + "\n", {
    flag: "wx",
    mode: 0o600,
  });
  renameSync(staging, file);
}

export function setPaused(paused, reason, directory = controlDirectory) {
  mkdirSync(path.join(directory, "events"), { recursive: true });
  const record = { paused, reason, recordedAt: now() };
  save(path.join(directory, "events", `${randomUUID()}.json`), record);
  save(stateFile(directory), record);
  return record;
}

export function assertUnpaused(directory = controlDirectory) {
  if (json(stateFile(directory), { paused: false }).paused)
    throw new Error(
      "Wargame verification is paused. Resume explicitly after storage review; no files were removed.",
    );
}

export function availableBytes(location) {
  let existing = path.resolve(location);
  while (!existsSync(existing)) existing = path.dirname(existing);
  const result = statfsSync(existing, { bigint: true });
  return Number(result.bavail * result.bsize);
}

export function checkCapacity(policy, current, starting = null) {
  const threshold =
    starting === null ? policy.minimumFreeBytes : policy.reserveFreeBytes;
  if (current < threshold)
    throw new Error(
      `Storage guard: ${(current / 1e9).toFixed(2)} GB free; ${(threshold / 1e9).toFixed(2)} GB required. Review an exact cleanup list; nothing is purged automatically.`,
    );
  if (starting !== null && starting - current > policy.maximumRunGrowthBytes)
    throw new Error("Storage guard: the run's disk-growth budget was exceeded");
}

export function retainedRoots(root = projectRoot, temporary = os.tmpdir()) {
  const roots = [];
  const artifacts = path.join(root, ".artifacts");
  if (existsSync(artifacts)) roots.push(artifacts);
  for (const entry of readdirSync(temporary, { withFileTypes: true }))
    if (
      entry.isDirectory() &&
      entry.name !== "wargame-storage-control" &&
      /^(wargame-|\.retained-wargame-)/.test(entry.name)
    )
      roots.push(path.join(temporary, entry.name));
  return roots.sort();
}

export function retainedBytes(roots) {
  let total = 0;
  const seen = new Set();
  const pending = [...roots];
  while (pending.length) {
    const file = pending.pop();
    let info;
    try {
      info = lstatSync(file);
    } catch (error) {
      if (error.code === "ENOENT") continue;
      throw error; // An incomplete inventory cannot establish available budget.
    }
    if (info.isSymbolicLink()) continue;
    if (info.isDirectory()) {
      for (const entry of readdirSync(file))
        pending.push(path.join(file, entry));
    } else if (info.isFile()) {
      const identity = `${info.dev}:${info.ino}`;
      if (seen.has(identity)) continue;
      seen.add(identity);
      total += info.blocks === undefined ? info.size : info.blocks * 512;
    }
  }
  return total; // APFS clone sharing is not visible here: conservative upper bound.
}

function alive(pid) {
  if (!Number.isSafeInteger(pid) || pid <= 0) return true;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code !== "ESRCH";
  }
}

function owner(directory) {
  return json(path.join(lockDirectory(directory), "owner.json"), null);
}

export function inheritedLease(
  environment = process.env,
  directory = environment.WARGAME_STORAGE_LEASE_DIR ?? controlDirectory,
) {
  if (!environment.WARGAME_STORAGE_RUN_TOKEN) return null;
  const current = owner(directory);
  return current &&
    current.token === environment.WARGAME_STORAGE_RUN_TOKEN &&
    String(current.pid) === environment.WARGAME_STORAGE_OWNER_PID &&
    alive(current.pid)
    ? current
    : null;
}

export function acquireLease(
  directory = controlDirectory,
  label = "verification",
) {
  mkdirSync(path.join(directory, "runs"), { recursive: true });
  const lock = lockDirectory(directory);
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      mkdirSync(lock);
      const lease = {
        token: randomUUID(),
        pid: process.pid,
        label,
        startedAt: now(),
      };
      save(path.join(lock, "owner.json"), lease);
      return lease;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      const previous = owner(directory);
      if (!previous || alive(previous.pid))
        throw new Error(
          "Storage guard: another heavy run holds the shared lease",
        );
      throw new Error(
        "Storage guard: owner stopped but workload ownership is unconfirmed; retain lease for explicit recovery review",
      );
    }
  }
  throw new Error("Storage guard: could not acquire the verification lease");
}

export function releaseLease(lease, directory = controlDirectory) {
  if (owner(directory)?.token !== lease.token)
    throw new Error("Storage lease ownership changed");
  const destination = path.join(directory, "runs", lease.token);
  mkdirSync(destination);
  renameSync(lockDirectory(directory), path.join(destination, "lease"));
  return destination;
}

export function compilationEnvironment(environment = process.env) {
  return {
    CARGO_INCREMENTAL: "0",
    CARGO_PROFILE_DEV_DEBUG: "line-tables-only",
    CARGO_PROFILE_TEST_DEBUG: "line-tables-only",
    ...environment,
    // npm's normal log rotation deletes files before a project hook executes.
    // Retain logs for separately approved cleanup, including nested installs.
    npm_config_logs_max: "2147483647",
    NPM_CONFIG_LOGS_MAX: "2147483647",
  };
}

export function assertCompilationCapacity(environment = process.env) {
  assertUnpaused();
  const free = Math.min(
    availableBytes(projectRoot),
    availableBytes(os.tmpdir()),
    availableBytes(environment.CARGO_TARGET_DIR ?? projectRoot),
  );
  checkCapacity(loadPolicy(), free, inheritedLease(environment) ? free : null);
}

export async function guardedCommand(
  label,
  command,
  args,
  {
    directory = controlDirectory,
    policy = loadPolicy(),
    root = projectRoot,
    temporary = os.tmpdir(),
    environment = process.env,
    leaseDirectory = environment.WARGAME_STORAGE_LEASE_DIR ?? directory,
    childControlDirectory = directory,
    capacity = availableBytes,
    inventory = retainedBytes,
    retentionRoots = retainedRoots,
    cwd = process.cwd(),
    queueAdmission = true,
    nativeInspection = null,
    containerSnapshot = scheduler?.containerSnapshot ?? (() => ({ known: false, ids: [] })),
  } = {},
) {
  const registered = nativeInspection === null ? null : consumeRegisteredGuardInvocation(nativeInspection);
  const nativeCommandOwner = registered ? { pid: process.ppid, identity: scheduler?.processIdentity(process.ppid) } : null;
  const nativeOwnerPresent = () => !registered || (nativeCommandOwner.pid > 1 && nativeCommandOwner.identity != null &&
    process.ppid === nativeCommandOwner.pid && JSON.stringify(scheduler?.processIdentity(nativeCommandOwner.pid)) === JSON.stringify(nativeCommandOwner.identity));
  if (!nativeOwnerPresent()) throw new Error("Native command owner identity is unconfirmed before admission");
  assertUnpaused(directory);
  const locations = [
    ...new Set(
      [root, cwd, temporary, environment.CARGO_TARGET_DIR].filter(Boolean),
    ),
  ];
  const free = () => Math.min(...locations.map(capacity));
  const inherited = inheritedLease(environment, leaseDirectory);
  if (inherited && environment.BUILDCTL_PHASE === "benchmark" && inherited.phase !== "benchmark")
    throw new Error("Benchmark phase must queue independently; a functional or legacy lease cannot be promoted");
  checkCapacity(policy, free(), inherited ? free() : null);
  const queued = !inherited && queueAdmission && scheduler;
  const queuedAbort = new AbortController();
  const abortQueue = () => queuedAbort.abort();
  let lease;
  if (queued) {
    const nativeParentQueueTimer = registered ? setInterval(() => { if (!nativeOwnerPresent()) abortQueue(); }, policy.monitorIntervalMs) : null;
    for (const name of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(name, abortQueue);
    try {
      lease = await scheduler.queueLease(leaseDirectory, scheduler.nativeRequest({
        project: root, root, command: [command, ...args], label,
        diskBytes: policy.maximumRunGrowthBytes,
        phase: environment.BUILDCTL_PHASE ?? "functional",
      }), () => acquireLease(leaseDirectory, label), {
        signal: queuedAbort.signal,
        onQueued: id => console.error(`Build reservation queued: ${id}; inspect with buildctl status`),
      });
    } finally {
      clearInterval(nativeParentQueueTimer);
      for (const name of ["SIGINT", "SIGTERM", "SIGHUP"]) process.off(name, abortQueue);
    }
  } else lease = inherited ?? acquireLease(leaseDirectory, label);
  const reservation = lease.buildctlRequest && new scheduler.Scheduler(leaseDirectory);
  let safeToRelease = true;
  let outputBytes = 0;
  let lastOutputAt = null;
  let containersBefore;
  let reportDirectory;
  const buildEnvironment = compilationEnvironment(environment);
  const record = {
    label,
    startedAt: now(),
    root,
    controlDirectory: directory,
    childControlDirectory,
    leaseDirectory,
    completed: false,
    filesDeleted: 0,
    ...(registered ? { nativeCommandOwner } : {}),
    initialCompilationEnvironment: Object.fromEntries(
      [
        "CARGO_INCREMENTAL",
        "CARGO_PROFILE_DEV_DEBUG",
        "CARGO_PROFILE_TEST_DEBUG",
      ].map((key) => [key, buildEnvironment[key]]),
    ),
  };
  try {
    assertUnpaused(directory);
    record.freeBytesAtStart = free();
    checkCapacity(
      policy,
      record.freeBytesAtStart,
      inherited ? record.freeBytesAtStart : null,
    );
    if (!inherited) {
      record.retainedRootsAtStart = retentionRoots(root, temporary);
      record.retainedAllocatedBytesAtStart = inventory(
        record.retainedRootsAtStart,
      );
      if (record.retainedAllocatedBytesAtStart > policy.maximumRetainedBytes)
        throw new Error(
          "Storage guard: retained outputs exceed the storage budget; an exact cleanup proposal and approval are required",
        );
    }
    checkCapacity(policy, free(), inherited ? record.freeBytesAtStart : null);
    assertUnpaused(directory);
    const ownsProcessGroup = !inherited && process.platform !== "win32";
    if (!inherited) {
      containersBefore = containerSnapshot();
      record.containersAtStart = containersBefore;
      if (!containersBefore.known) throw new Error("Container ownership is uncertain; workload was not started");
      if (environment.BUILDCTL_PHASE === "benchmark" && containersBefore.ids.length)
        throw new Error("Benchmark phase requires an isolated runtime; existing containers are unreserved");
    }
    if (!nativeOwnerPresent()) throw new Error("Native command owner stopped before launch");
    // A launch attempt is conservatively held until concrete registered stop proof.
    if (registered) safeToRelease = false;
    const child = registered ? await registered.start(snapshot => {
      record.nativeInspection = snapshot;
      if (reservation) reservation.update(lease.buildctlRequest, {
        progress: snapshot.calls.some(call => call.nativePid > 1) ? 'native inspection registered' :
          snapshot.calls.length ? 'native inspection launch pending' : 'native controller registered'
      });
    }) : spawn(command, args, {
      cwd,
      stdio: ["inherit", "pipe", "pipe"],
      // Nested supervisors stay in the parent's group so its emergency stop
      // also reaches their children, even if a nested leader exits first.
      detached: ownsProcessGroup,
      env: {
        ...buildEnvironment,
        WARGAME_STORAGE_CONTROL_DIR: childControlDirectory,
        WARGAME_STORAGE_LEASE_DIR: leaseDirectory,
        WARGAME_STORAGE_RUN_TOKEN: lease.token,
        WARGAME_STORAGE_OWNER_PID: String(lease.pid),
      },
    });
    const childClosed = registered ? registered.result().then(() => {}) : new Promise(resolve => child.once("close", resolve));
    if (child.pid && ownsProcessGroup) safeToRelease = false;
    if (reservation && child.pid) reservation.update(lease.buildctlRequest, {
      processGroup: ownsProcessGroup ? child.pid : null,
      ownershipSealed: ownsProcessGroup,
      progress: `Child started; pid ${child.pid}`,
    });
    for (const [source, target] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) {
      source.on("data", chunk => {
        outputBytes += chunk.length; lastOutputAt = now();
        // Registered streams are bounded by the registrar and emitted once from\n        // their final capture below. Ordinary commands still forward live output.\n        if (!registered && !target.write(chunk)) { source.pause(); target.once("drain", () => source.resume()); }
      });
    }
    let stopped = false;
    let leakedChildren = false;
    let forceTimer;
    const signal = (name) => {
      try {
        if (child.pid && ownsProcessGroup) process.kill(-child.pid, name);
        else child.kill(name);
      } catch (error) {
        if (error.code !== "ESRCH") throw error;
      }
    };
    const stop = (reason) => {
      if (stopped) return;
      stopped = true;
      record.stopReason = reason;
      console.error(reason);
      if (registered) {
        // Only the registered controller can select the exact owned identities.
        // Generic group signaling is redundant and can fail after that stop.
        void registered.stop().catch(error => {
          record.nativeInspectionStopFailure = String(error.message).slice(0,240);
        });
        return;
      }
      signal("SIGTERM");
      forceTimer = setTimeout(
        () => signal("SIGKILL"),
        policy.terminationGraceMs,
      );
    };
    const watch = () => {
      try {
        if (!nativeOwnerPresent()) throw new Error("Storage guard: native command owner parent stopped; stopping registered inspection");
        if (reservation) {
          try { reservation.update(lease.buildctlRequest, {
            heartbeat: now(), progress: `Child pid ${child.pid}; output bytes ${outputBytes}; last output ${lastOutputAt ?? "none"}`,
          }); } catch (error) { if (error.code !== "BUSY") throw error; }
        }
        assertUnpaused(directory);
        record.minimumFreeBytesObserved = Math.min(
          record.minimumFreeBytesObserved ?? record.freeBytesAtStart,
          free(),
        );
        checkCapacity(
          policy,
          record.minimumFreeBytesObserved,
          record.freeBytesAtStart,
        );
      } catch (error) {
        stop(error.message);
      }
    };
    const interrupted = (name) => () =>
      stop(
        `Storage guard: received ${name}; run interrupted and outputs retained`,
      );
    const handlers = new Map(
      ["SIGINT", "SIGTERM", "SIGHUP"].map((name) => [name, interrupted(name)]),
    );
    for (const [name, handler] of handlers) process.on(name, handler);
    const timer = setInterval(watch, policy.monitorIntervalMs);
    try {
      const result = registered ? await registered.result() : await new Promise((resolve, reject) => {
        child.once("error", reject);
        child.once("exit", (code, childSignal) =>
          resolve({ code, childSignal }),
        );
      });
      if (registered) {
        if (result.stdout?.length) process.stdout.write(result.stdout);
        if (result.stderr?.length) process.stderr.write(result.stderr);
      }
      record.exitCode = stopped ? 75 : (result.code ?? 1);
      record.signal = result.childSignal;
      record.completed = !stopped && result.code === 0;
      return record.exitCode;
    } finally {
      clearInterval(timer);
      if (registered && stopped) {
        try { await registered.stop(); }
        catch (error) { record.nativeInspectionStopFailure = String(error.message).slice(0,240); }
      }
      if (child.pid && ownsProcessGroup && scheduler && !scheduler.workloadStopped(child.pid) && !stopped) {
        leakedChildren = true;
        stop("Storage guard: child leader exited with surviving owned processes; stopping group before release");
      }
      // A leader can exit before its allocating children. Keep the lease until
      // the owned process group has stopped, including the grace-period kill.
      if (stopped && child.pid && ownsProcessGroup && !registered) {
        const deadline = Date.now() + policy.terminationGraceMs + 1000;
        while (Date.now() < deadline) {
          try {
            process.kill(-child.pid, 0);
          } catch (error) {
            if (error.code === "ESRCH") break;
            throw error;
          }
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
      }
      if (child.pid && ownsProcessGroup) {
        if (scheduler) safeToRelease = scheduler.workloadStopped(child.pid);
        else { try { process.kill(-child.pid, 0); safeToRelease = false; }
          catch (error) { safeToRelease = error.code === "ESRCH"; } }
      }
      const streamsClosed = await Promise.race([
        childClosed.then(() => true),
        new Promise(resolve => { const deadline = setTimeout(() => resolve(false), policy.terminationGraceMs); deadline.unref(); }),
      ]);
      safeToRelease = safeToRelease && streamsClosed;
      const registeredComplete = registered ? await registered.closed() : false;
      if (registered) {
        record.registeredNativeStop = registered.status();
        safeToRelease = safeToRelease && registeredComplete;
      }
      clearTimeout(forceTimer);
      for (const [name, handler] of handlers) process.off(name, handler);
      if (!inherited && child.pid) {
        const after = containerSnapshot();
        record.containersAtEnd = after;
        const survivors = after.ids.filter(id => !containersBefore.ids.includes(id));
        record.newSurvivingContainers = survivors;
        // A killed native wrapper may have left exec work inside a container
        // that already existed at admission. PID/group exit cannot disprove it.
        const existingContainerUncertainty = stopped && containersBefore.ids.length > 0 && !registeredComplete;
        record.existingContainerUncertainty = existingContainerUncertainty;
        safeToRelease = safeToRelease && after.known && survivors.length === 0 && !existingContainerUncertainty;
      }
      if (!safeToRelease) throw new Error("Owned workload stop unconfirmed (processes or containers); reservation retained");
      if (leakedChildren) throw new Error("Child leader exited with surviving processes; owned group stopped, command failed");
    }
  } catch (error) {
    record.completed = false;
    record.exitCode = 75;
    record.stopReason = error.message;
    throw error;
  } finally {
    if (registered) safeToRelease = safeToRelease && (await registered.closed().catch(() => false));
    record.finishedAt = now();
    record.freeBytesAtEnd = free();
    record.retainedRootsAtEnd = retentionRoots(root, temporary);
    if (!inherited) {
      if (reservation) reservation.finish(lease.buildctlRequest, safeToRelease,
        safeToRelease ? () => { reportDirectory = releaseLease(lease, leaseDirectory); } : null);
      if (!safeToRelease) {
        record.stopReason = "Owned workload stop unconfirmed; shared lease retained";
        save(path.join(lockDirectory(leaseDirectory), "retained-run.json"), record);
        console.error(record.stopReason);
      } else {
      if (!reservation) reportDirectory = releaseLease(lease, leaseDirectory);
      save(path.join(reportDirectory, "run.json"), record);
      console.log(
        `Storage guard record: ${path.join(reportDirectory, "run.json")}`,
      );
      }
    }
  }
}

export async function guardEntrypoint(url, label) {
  if (
    !process.argv[1] ||
    pathToFileURL(path.resolve(process.argv[1])).href !== url
  )
    return;
  if (inheritedLease()) {
    if (process.env.BUILDCTL_PHASE === "benchmark" && inheritedLease().phase !== "benchmark")
      throw new Error("Benchmark phase must queue independently");
    assertUnpaused();
    checkCapacity(
      loadPolicy(),
      availableBytes(projectRoot),
      availableBytes(projectRoot),
    );
    return;
  }
  try {
    process.exitCode = await guardedCommand(
      label,
      process.execPath,
      [fileURLToPath(url), ...process.argv.slice(2)],
      { leaseDirectory: sharedLeaseDirectory },
    );
  } catch (error) {
    console.error(error.message);
    process.exitCode = 75;
  }
  process.exit(process.exitCode);
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const [action, label, separator, ...command] = process.argv.slice(2);
    if (action === "pause") {
      console.log(
        JSON.stringify(
          setPaused(
            true,
            process.argv.slice(3).join(" ") || "Explicit user pause",
          ),
        ),
      );
    } else if (action === "status") {
      console.log(
        JSON.stringify(
          {
            state: json(stateFile(controlDirectory), { paused: false }),
            activeRun: (() => { const current = owner(sharedLeaseDirectory); return current && {
              pid: current.pid, label: current.label, startedAt: current.startedAt,
            }; })(),
            reservations: scheduler ? new scheduler.Scheduler(sharedLeaseDirectory).status() : null,
            policy: loadPolicy(),
            availableBytes: availableBytes(projectRoot),
            controlDirectory,
            leaseDirectory: sharedLeaseDirectory,
          },
          null,
          2,
        ),
      );
    } else if (action === "resume") {
      const policy = loadPolicy();
      checkCapacity(
        policy,
        Math.min(availableBytes(projectRoot), availableBytes(os.tmpdir())),
      );
      if (retainedBytes(retainedRoots()) > policy.maximumRetainedBytes)
        throw new Error(
          "Retained output budget exceeded; keep verification paused pending cleanup review",
        );
      console.log(
        JSON.stringify(setPaused(false, "Explicit storage:resume command")),
      );
    } else if (
      action === "run" &&
      label &&
      separator === "--" &&
      command.length
    ) {
      process.exitCode = await guardedCommand(
        label,
        command[0],
        command.slice(1),
        { leaseDirectory: sharedLeaseDirectory },
      );
    } else {
      throw new Error(
        "Use status, pause <reason>, resume, or run <label> -- <command> [args]",
      );
    }
  } catch (error) {
    console.error(error.message);
    process.exitCode = 75;
  }
}
