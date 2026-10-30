/**
 * Closed, uninstalled registration for the qualified Intel inspection profile.
 * Stage construction is a trusted supervisor/development operation. Workload
 * requests never choose source hashes, runtime, profiles, executables or env.
 * This is not an installed release authority or a general sandbox attestation.
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createHash, randomUUID } from "node:crypto";
import { execFileSync, spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { NativeInspectionReceiver, validIdentity, sameIdentity } from "./native_inspection_receiver.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ARCHIVE_SHA = "f507ae04eb7747cd97cb484e8c5d83936cbfc52d9b08a1f35c00b47c707b1ae1";
const EXPECTED_RUNTIME_MACHO = Object.freeze(["python/bin/python3.13", "python/lib/itcl4.3.8/libitcl4.3.8.dylib", "python/lib/itcl4.3.8/libtcl9itcl4.3.8.dylib", "python/lib/libpython3.13.dylib", "python/lib/libtcl9.0.dylib", "python/lib/libtcl9tk9.0.dylib", "python/lib/python3.13/lib-dynload/_dbm.cpython-313-darwin.so", "python/lib/python3.13/lib-dynload/_tkinter.cpython-313-darwin.so", "python/lib/thread3.0.6/libtcl9thread3.0.6.dylib", "python/lib/thread3.0.6/libthread3.0.6.dylib"]);
const NATIVE_SHA = "cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355";
const SOURCES = Object.freeze({
  "native_inspection.py": "b8c9db39af73b42bebd888d60dde2dfdaf4bf80f88f193f29a2841c213edea71",
  "native_inspection_guard.py": "a9e1b35e728b38dd8c7746bd6318cb28c10598a0c558b097f51b99c36447f91d",
  "project_watch.py": "94b3b1ccdd936a044fc815772ee72ecbdf2344701e57cd5f7a2fdf9b778ecf85",
  "native_inspection_receiver.mjs": "c0e26d091caec2033db0bc54e0001f804d17cacac443872e46bc37335e1ee04d",
  "native_registered_controller.py": "7e2f0fd53ff04dcbeef623510c2b65862ac99945e7b69af3cdeabed2cba7a627",
});
const ENV = Object.freeze({ PATH: "/usr/bin:/bin", LANG: "C", PYTHONDONTWRITEBYTECODE: "1" });
const SYSTEM = ["/usr/bin/sandbox-exec", "/usr/bin/tar", "/usr/bin/otool",
  "/usr/bin/sw_vers", "/usr/bin/uname", "/bin/ps"];
const registrations = new WeakMap();
const inspections = new WeakMap();
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const digest = file => sha(fs.readFileSync(file));
const serialize = value => JSON.stringify(value);
function need(value, message) { if (!value) throw new Error(message); }
function exact(value, keys) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value, k));
}
function command(program, args, options = {}) {
  return execFileSync(program, args, { env: ENV, encoding: "utf8", timeout: 10000,
    maxBuffer: 4 * 1024 * 1024, ...options });
}
export function qualifiedInspectionHost(value) {
  return exact(value, ["platform", "architecture", "productVersion", "buildVersion", "kernel"]) &&
    value.platform === "darwin" && value.architecture === "x64" &&
    value.productVersion === "15.8.1" && value.buildVersion === "24H32" && value.kernel === "24.6.0";
}
function host() {
  const value = { platform: process.platform, architecture: process.arch,
    productVersion: command("/usr/bin/sw_vers", ["-productVersion"]).trim(),
    buildVersion: command("/usr/bin/sw_vers", ["-buildVersion"]).trim(),
    kernel: command("/usr/bin/uname", ["-r"]).trim() };
  need(qualifiedInspectionHost(value), "unqualified-inspection-host");
  return value;
}
function canonical(value, kind) {
  need(typeof value === "string" && path.isAbsolute(value) &&
    fs.realpathSync(value) === value, "noncanonical-inspection-path");
  const info = fs.lstatSync(value);
  need(info.uid === process.getuid() && (kind === "directory" ? info.isDirectory() : info.isFile()),
    "unowned-or-wrong-inspection-path-type");
  return info;
}
function inside(root, value) {
  const relative = path.relative(root, value);
  return relative === "" || (!relative.startsWith("../") && relative !== ".." && !path.isAbsolute(relative));
}
function privateDirectory(value, empty = false) {
  const info = canonical(value, "directory");
  need((info.mode & 0o777) === 0o700 && (!empty || fs.readdirSync(value).length === 0),
    "private-empty-inspection-root-required");
  return info;
}
function noStartupInjection() {
  need(!Object.keys(process.env).some(k =>
    (k === "NODE_OPTIONS" || k === "NODE_PATH" || k.startsWith("DYLD_") || k.startsWith("LD_")) &&
    process.env[k]), "supervisor-startup-injection");
}
function tree(root) {
  const rows = [];
  function walk(file) {
    const info = fs.lstatSync(file);
    need(info.uid === process.getuid(), "snapshot-owner-changed");
    const relative = path.relative(root, file) || ".";
    const base = { path: relative, mode: info.mode & 0o777, uid: info.uid,
      dev: info.dev, ino: info.ino, nlink: info.nlink };
    need(info.isSymbolicLink() || (base.mode & 0o222) === 0, "snapshot-writable");
    if (info.isSymbolicLink()) {
      // Symlink mode is not an effective write permission on Darwin; its parent
      // and resolved target are separately bound and must stay in this tree.
      need(inside(root, fs.realpathSync(file)), "snapshot-link-escape");
      rows.push({ ...base, kind: "symlink", target: fs.readlinkSync(file) });
    } else if (info.isDirectory()) {
      rows.push({ ...base, kind: "directory" });
      for (const name of fs.readdirSync(file).sort()) walk(path.join(file, name));
    } else {
      need(info.isFile() && info.nlink === 1, "snapshot-special-file-or-hardlink");
      rows.push({ ...base, kind: "file", size: info.size, sha256: digest(file) });
    }
    need(rows.length <= 50000, "snapshot-entry-limit");
  }
  walk(root);
  return rows;
}
function freeze(root) {
  const info = fs.lstatSync(root);
  need(info.uid === process.getuid(), "unowned-snapshot");
  if (info.isSymbolicLink()) {
    need(inside(root.includes("/runtime/") ? root.split("/runtime/")[0] + "/runtime" : path.dirname(root),
      fs.realpathSync(root)), "extracted-link-escape");
    return;
  }
  if (info.isDirectory()) {
    for (const name of fs.readdirSync(root)) freeze(path.join(root, name));
    fs.chmodSync(root, 0o500);
  } else {
    need(info.isFile() && info.nlink === 1, "extracted-special-file-or-hardlink");
    fs.chmodSync(root, info.mode & 0o111 ? 0o500 : 0o400);
  }
}
function dependencyAudit(runtime) {
  const binaries = [];
  function find(file) {
    const info = fs.lstatSync(file);
    if (info.isDirectory()) for (const name of fs.readdirSync(file).sort()) find(path.join(file, name));
    else if (info.isFile()) {
      const fd = fs.openSync(file, "r");const prefix = Buffer.alloc(4);
      try { fs.readSync(fd, prefix, 0, 4, 0); } finally { fs.closeSync(fd); }
      if (["cffaedfe", "cefaedfe", "feedfacf", "feedface", "cafebabe", "bebafeca"].includes(prefix.toString("hex")))
        binaries.push(file);
    }
  }
  find(runtime);
  const executableDirectory = path.join(runtime, "python/bin");
  function resolveRpath(value, owner) {
    if (value.startsWith("@loader_path/")) return path.resolve(path.dirname(owner), value.slice(13));
    if (value.startsWith("@executable_path/")) return path.resolve(executableDirectory, value.slice(17));
    if (path.isAbsolute(value)) return value;
    throw new Error("unknown-runtime-rpath");
  }
  const rpaths = new Map();
  const installNames = new Map();
  for (const file of binaries) {
    const load = command("/usr/bin/otool", ["-l", file]);
    const values = [...load.matchAll(/cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset \d+\)/g)]
      .map(match => resolveRpath(match[1], file));
    need(values.every(value => inside(runtime, value)), "runtime-rpath-escape");
    rpaths.set(file, values);
    const id = load.match(/cmd LC_ID_DYLIB\s+cmdsize \d+\s+name (.*?) \(offset \d+\)/);
    installNames.set(file, id?.[1] ?? null);
  }
  const executableRpaths = rpaths.get(path.join(runtime, "python/bin/python3.13")) ?? [];
  const rows = [];
  for (const file of binaries) {
    const references = command("/usr/bin/otool", ["-L", file]).split("\n").slice(1)
      .map(line => line.trim()).filter(Boolean).map(line => line.split(" (compatibility version ")[0])
      .filter(value => value !== installNames.get(file));
    const resolved = references.map(value => {
      if (value.startsWith("/usr/lib/") || value.startsWith("/System/Library/"))
        return { system: value }; // Qualified OS/SSV trust; not a private-file digest.
      let candidates;
      if (value.startsWith("@rpath/")) candidates = [...rpaths.get(file), ...executableRpaths]
        .map(base => path.resolve(base, value.slice(7)));
      else candidates = [resolveRpath(value, file)];
      const target = candidates.find(candidate => inside(runtime, candidate) && fs.existsSync(candidate));
      need(target && inside(runtime, fs.realpathSync(target)), "unresolved-private-runtime-reference");
      return { private: path.relative(runtime, fs.realpathSync(target)) };
    });
    rows.push({ file: path.relative(runtime, file), installName: installNames.get(file), references: resolved });
  }
  need(serialize(binaries.map(file => path.relative(runtime, file)).sort()) ===
    serialize(EXPECTED_RUNTIME_MACHO), "incomplete-native-runtime-audit");
  return rows;
}
function capsule(handle) {
  const value = registrations.get(handle);
  need(value, "unregistered-inspection-capability");
  return value;
}

export function stageInspectionRegistration(options) {
  need(exact(options, ["directory", "archive", "native"]), "closed-registration-options");
  noStartupInjection();
  const qualifiedHost = host();
  canonical(options.archive, "file");canonical(options.native, "file");
  const archiveBytes = fs.readFileSync(options.archive);
  const nativeBytes = fs.readFileSync(options.native);
  need(sha(archiveBytes) === ARCHIVE_SHA && sha(nativeBytes) === NATIVE_SHA,
    "unapproved-runtime-or-native");
  const parent = path.dirname(options.directory);
  privateDirectory(parent);
  need(path.isAbsolute(options.directory) && !fs.existsSync(options.directory),
    "fresh-registration-directory-required");
  const sourceBytes = Object.fromEntries([...Object.keys(SOURCES), "native_inspection_registration.mjs"]
    .map(name => [name, fs.readFileSync(path.join(HERE, name))]));
  for (const [name, expected] of Object.entries(SOURCES))
    need(sha(sourceBytes[name]) === expected, "unapproved-inspection-source: " + name);
  fs.mkdirSync(options.directory, { mode: 0o700 });
  const root = fs.realpathSync(options.directory);
  need(root === options.directory, "registration-directory-alias");
  const source = path.join(root, "source"), runtime = path.join(root, "runtime"), native = path.join(root, "native");
  for (const directory of [source, runtime, native]) fs.mkdirSync(directory, { mode: 0o700 });
  // The whole archive is pinned before this trusted OS extractor is invoked.
  // No caller-selected archive bytes can reach extraction.
  command("/usr/bin/tar", ["-xzf", "-", "-C", runtime], { input: archiveBytes, timeout: 60000 });
  for (const [name, bytes] of Object.entries(sourceBytes))
    fs.writeFileSync(path.join(source, name), bytes, { mode: 0o400, flag: "wx" });
  fs.writeFileSync(path.join(native, "patamaps"), nativeBytes, { mode: 0o500, flag: "wx" });
  need(Object.entries(sourceBytes).every(([name, bytes]) =>
    digest(path.join(source, name)) === sha(bytes)) && digest(path.join(native, "patamaps")) === NATIVE_SHA,
    "inspection-snapshot-copy-integrity");
  const dependencies = dependencyAudit(runtime);
  const nativeSystemReferences = command("/usr/bin/otool", ["-L", path.join(native, "patamaps")])
    .split("\n").slice(1).map(line => line.trim()).filter(Boolean)
    .map(line => line.split(" (compatibility version ")[0]);
  need(nativeSystemReferences.length > 0 && nativeSystemReferences.every(reference =>
    reference.startsWith("/usr/lib/") || reference.startsWith("/System/Library/")),
    "unbound-native-dynamic-reference");
  for (const directory of [source, runtime, native]) freeze(directory);
  const inventory = { source: tree(source), runtime: tree(runtime), native: tree(native) };
  const manifest = { version: 1, kind: "patamaps-staged-native-registration-v1",
    qualifiedHost, archiveSha256: ARCHIVE_SHA, nativeSha256: NATIVE_SHA,
    controllerSha256: SOURCES["native_registered_controller.py"],
    systemBindings: Object.fromEntries([...SYSTEM, process.execPath].map(file => [file, digest(file)])),
    inventory, dependencies, nativeSystemReferences, automaticReservationReleaseQualified: false };
  const manifestFile = path.join(root, "registration.json");
  fs.writeFileSync(manifestFile, serialize(manifest) + "\n", { mode: 0o400, flag: "wx" });
  fs.chmodSync(root, 0o500);
  const handle = Object.freeze({ kind: manifest.kind, directory: root });
  registrations.set(handle, { root, manifest, manifestSha: digest(manifestFile),
    rootIdentity: fs.lstatSync(root), moduleSha: sha(sourceBytes["native_inspection_registration.mjs"]),
    python: path.join(runtime, "python/bin/python3.13"), controller: path.join(source, "native_registered_controller.py") });
  verifyInspectionRegistration(handle);
  return handle;
}

export function verifyInspectionRegistration(handle) {
  const value = capsule(handle);
  noStartupInjection();
  need(serialize(host()) === serialize(value.manifest.qualifiedHost), "inspection-host-changed");
  need(serialize(fs.readdirSync(value.root).sort()) === serialize(["native", "registration.json", "runtime", "source"]), "registration-root-entries-changed");
  const identity = fs.lstatSync(value.root);
  need(identity.isDirectory() && identity.dev === value.rootIdentity.dev &&
    identity.ino === value.rootIdentity.ino && (identity.mode & 0o777) === 0o500 &&
    fs.realpathSync(value.root) === value.root, "registration-root-changed");
  need(digest(path.join(value.root, "registration.json")) === value.manifestSha,
    "registration-manifest-changed");
  need(digest(fileURLToPath(import.meta.url)) === value.moduleSha, "registration-module-changed");
  for (const [file, expected] of Object.entries(value.manifest.systemBindings))
    need(digest(file) === expected, "inspection-system-binding-changed");
  for (const part of ["source", "runtime", "native"])
    need(serialize(tree(path.join(value.root, part))) === serialize(value.manifest.inventory[part]),
      "inspection-closure-changed: " + part);
  return Object.freeze({ kind: value.manifest.kind, manifestSha256: value.manifestSha,
    runtimeEntries: value.manifest.inventory.runtime.length,
    privateMachOObjects: value.manifest.dependencies.length,
    qualifiedHost: structuredClone(value.manifest.qualifiedHost),
    automaticReservationReleaseQualified: false });
}
export function probeRegisteredInspection(handle, ids) {
  const value = capsule(handle);
  need(Array.isArray(ids) && ids.length > 0 && ids.length <= 64 &&
    new Set(ids).size === ids.length && ids.every(id => Number.isSafeInteger(id) && id > 1),
    "closed-probe-request");
  verifyInspectionRegistration(handle);
  return JSON.parse(command(value.python, ["-I", "-S", "-B", value.controller, "--probe", serialize(ids)]));
}
function privateInvocation(handle, options) {
  const value = capsule(handle);
  need(exact(options, ["operation", "runRoot", "inputs"]) &&
    ["engine", "input-key", "unchanged-build"].includes(options.operation), "closed-inspection-operation");
  privateDirectory(options.runRoot, true);
  need(!inside(value.root, options.runRoot) && !inside(options.runRoot, value.root),
    "inspection-writable-registration-alias");
  const keys = options.operation === "engine" ? [] :
    ["plan", "source", "context", "preparation", ...(options.operation === "unchanged-build" ? ["state"] : [])];
  need(exact(options.inputs, keys), "closed-inspection-inputs");
  for (const [key, file] of Object.entries(options.inputs)) {
    canonical(file, ["source", "state"].includes(key) ? "directory" : "file");
    need(!inside(value.root, file) && !inside(file, value.root), "inspection-input-registration-alias");
  }
  if (options.operation === "unchanged-build") {
    const lock = path.join(options.inputs.state, "driver.lock");
    const info = canonical(lock, "file");
    need((info.mode & 0o777) === 0o600 && info.size === 0 && info.nlink === 1 &&
      (fs.statSync(options.inputs.state).mode & 0o077) === 0, "unsafe-inspection-driver-lock");
    need(!inside(options.inputs.state, options.runRoot) && !inside(options.runRoot, options.inputs.state),
      "inspection-state-work-alias");
  }
  return { version: 1, operation: options.operation, runRoot: options.runRoot,
    inputs: structuredClone(options.inputs), expectedParent: process.pid, manifestSha256: value.manifestSha };
}
function atomic(file, value) {
  const staging = file + "." + randomUUID() + ".staging";
  const fd = fs.openSync(staging, "wx", 0o600);
  try { fs.writeSync(fd, serialize(value) + "\n");fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(staging, file);
}

export async function startRegisteredInspection(handle, options) {
  const value = capsule(handle);
  verifyInspectionRegistration(handle);
  const invocation = privateInvocation(handle, options);
  const descriptor = path.join(options.runRoot, "invocation.json");
  fs.writeFileSync(descriptor, serialize(invocation) + "\n", { mode: 0o400, flag: "wx" });
  const invocationSha = digest(descriptor);
  const child = spawn(value.python, ["-I", "-S", "-B", value.controller,
    "--invocation", descriptor, "--sha", invocationSha], {
    env: ENV, cwd: path.dirname(value.controller), detached: true,
    stdio: ["ignore", "pipe", "pipe", "pipe", "pipe"],
  });
  const outputs = { stdout: [], stderr: [] };
  const sizes = { stdout: 0, stderr: 0 };
  let exit = null, streamError = null;
  const closed = new Promise(resolve => child.once("close", (code, signal) => {
    exit = { code, signal };resolve();
  }));
  child.once("error", error => { streamError = error.message; });
  for (const name of ["stdout", "stderr"]) child[name].on("data", chunk => {
    sizes[name] += chunk.length;
    if (sizes[name] <= 1048576) outputs[name].push(chunk);
    else streamError = "registered-output-limit";
  });
  let receiver;
  try {
    const observed = probeRegisteredInspection(handle, [child.pid]);
    const identity = observed.identities[child.pid];
    need(validIdentity(identity) && identity.parentPid === process.pid &&
      identity.pgid === child.pid, "controller-kernel-registration-unconfirmed");
    receiver = new NativeInspectionReceiver({
      controllerIdentity: identity,
      probe: ids => probeRegisteredInspection(handle, ids),
      persist(snapshot, frame) {
        if (frame) {
          const fd = fs.openSync(path.join(options.runRoot, "supervisor-journal.jsonl"), "a", 0o600);
          try { fs.writeSync(fd, serialize({ frame, snapshot }) + "\n");fs.fsyncSync(fd); }
          finally { fs.closeSync(fd); }
        }
        atomic(path.join(options.runRoot, "supervisor-status.json"), snapshot);
      },
    });
    const consuming = receiver.consume(child.stdio[3]);
    child.once("exit", (code, signal) => receiver.noteControllerExit(code, signal));
    const inspection = Object.freeze({ child, registration: handle, runRoot: options.runRoot });
    inspections.set(inspection, { handle, child, receiver, identity, closed, consuming, outputs,
      sizes, getExit: () => exit, getError: () => streamError, descriptor, invocationSha });
    child.stdio[4].end(Buffer.from("1")); // Receiver/identity exist before any guardian launch.
    child.stdio[4].resume(); // Drain the unused ACK read half so close is observable.
    return inspection;
  } catch (error) {
    // Before ACK the closed controller cannot launch a guardian. End the ACK
    // channel and reap it; never claim a globally complete launch from failure.
    child.stdio[4]?.end();
    await closed;
    throw error;
  }
}
export function registeredInspectionStatus(inspection) {
  const value = inspections.get(inspection);
  need(value, "unregistered-inspection-instance");
  return value.receiver.snapshot();
}
export async function stopRegisteredInspection(inspection) {
  const value = inspections.get(inspection);
  need(value, "unregistered-inspection-instance");
  verifyInspectionRegistration(value.handle);
  const identities = [value.identity, ...value.receiver.snapshot().calls.flatMap(call =>
    [call.guardianIdentity, call.nativeIdentity].filter(Boolean))];
  const binding = capsule(value.handle);
  return JSON.parse(command(binding.python, ["-I", "-S", "-B", binding.controller,
    "--stop", serialize(identities)], { timeout: 30000 }));
}
export async function finishRegisteredInspection(inspection) {
  const value = inspections.get(inspection);
  need(value, "unregistered-inspection-instance");
  await value.closed;await value.consuming;
  const proof = verifyInspectionRegistration(value.handle);
  need(digest(value.descriptor) === value.invocationSha, "registered-invocation-changed");
  const stopped = await value.receiver.assessStopped();
  const outputError = value.getError();
  return { exit: value.getExit(), stdout: Buffer.concat(value.outputs.stdout),
    stderr: Buffer.concat(value.outputs.stderr),
    ownership: stopped, binding: proof,
    dataStreamsClosed: value.child.stdout.destroyed && value.child.stderr.destroyed,
    outputError, registeredStagedSource: true,
    // Only the later qualified guard candidate can consume this evidence.
    automaticReservationReleaseQualified: false };
}
