import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createHash } from "node:crypto";
import { stageInspectionRegistration, verifyInspectionRegistration, qualifiedInspectionHost,
  startRegisteredInspection, finishRegisteredInspection, registeredInspectionStatus,
  probeRegisteredInspection } from "./native_inspection_registration.mjs";

const root = process.env.PATAMAPS_TEST_RETAIN_ROOT;
assert.ok(root && path.isAbsolute(root));
assert.equal(os.platform(), "darwin", "Intel-qualified registration controls require Darwin");
const ROOT = fs.mkdtempSync(path.join(root, "registered-inspection-"));
fs.chmodSync(ROOT, 0o700);
const supplied = JSON.parse(fs.readFileSync(process.env.PATAMAPS_REGISTERED_INPUTS, "utf8"));
const sha = file => createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + "\n");
const fixture = name => { const p = path.join(ROOT, name);fs.mkdirSync(p, { mode: 0o700 });return p; };
const stageOptions = directory => ({ directory, archive: supplied.archive, native: supplied.native });
let registration, proof;
function beforeState() {
  return { files: Object.fromEntries(supplied.protectedFiles.map(file => [file, sha(file)])),
    attempts: fs.readdirSync(path.join(supplied.inputs.state, "attempts")).sort(),
    lock: (() => { const s = fs.lstatSync(path.join(supplied.inputs.state, "driver.lock"));
      return { dev: s.dev, ino: s.ino, mode: s.mode & 0o777, nlink: s.nlink,
        size: s.size, sha256: sha(path.join(supplied.inputs.state, "driver.lock")) }; })() };
}
const original = beforeState();
assert.deepEqual(original.attempts, ["1793122875791456000-6699"]);
assert.deepEqual(original.files, supplied.expectedState);
write(path.join(ROOT, "original-state.json"), original);

test("qualified host is exact and unknown host declarations refuse", () => {
  const good = { platform: "darwin", architecture: "x64", productVersion: "15.8.1",
    buildVersion: "24H32", kernel: "24.6.0" };
  assert.equal(qualifiedInspectionHost(good), true);
  for (const field of Object.keys(good)) assert.equal(qualifiedInspectionHost({ ...good, [field]: "unknown" }), false);
  assert.equal(qualifiedInspectionHost({ ...good, claimed: true }), false);
});

test("pinned archive builds complete read-only runtime and source snapshot", () => {
  registration = stageInspectionRegistration(stageOptions(path.join(ROOT, "registration")));
  proof = verifyInspectionRegistration(registration);
  assert.ok(proof.runtimeEntries > 1000);
  assert.equal(proof.privateMachOObjects, 10);
  assert.equal(proof.automaticReservationReleaseQualified, false);
  const manifest = JSON.parse(fs.readFileSync(path.join(registration.directory, "registration.json")));
  assert.ok(manifest.inventory.runtime.some(row => row.path.includes("lib-dynload") && row.kind === "file"));
  assert.ok(manifest.inventory.runtime.some(row => row.kind === "symlink"));
  const bareIDs = manifest.dependencies.filter(row => row.installName &&
    !row.installName.startsWith("/") && !row.installName.startsWith("@"));
  assert.deepEqual(bareIDs.map(row => row.installName).sort(),
    ["libitcl4.3.8.dylib", "libtcl9itcl4.3.8.dylib", "libtcl9thread3.0.6.dylib", "libthread3.0.6.dylib"]);
  assert.ok(manifest.dependencies.every(row => row.references.every(ref =>
    Object.hasOwn(ref, "system") || Object.hasOwn(ref, "private"))));
  for (const row of Object.values(manifest.inventory).flat())
    if (row.kind !== "symlink") assert.equal(row.mode & 0o222, 0);
  write(path.join(ROOT, "binding-proof.json"), proof);
});

test("forged serialized handles and unapproved source/program fields refuse", async () => {
  assert.throws(() => verifyInspectionRegistration({ ...registration }), /unregistered-inspection-capability/);
  assert.throws(() => stageInspectionRegistration({ ...stageOptions(path.join(ROOT, "forged")), sourceHash: "caller" }), /closed-registration-options/);
  const dir = fixture("forged-launch");
  for (const extra of [{ argv: ["/bin/sh"] }, { profile: "(allow default)" }, { environment: { PYTHONPATH: "/tmp" } }]) {
    await assert.rejects(startRegisteredInspection(registration, { operation: "engine", runRoot: dir, inputs: {}, ...extra }), /closed-inspection-operation/);
    assert.deepEqual(fs.readdirSync(dir), []);
  }
});

test("unapproved archive or native bytes refuse before creating a snapshot", () => {
  const wrong = path.join(ROOT, "unapproved-input");fs.writeFileSync(wrong, "not a runtime");
  for (const key of ["archive", "native"]) {
    const dir = path.join(ROOT, "unapproved-" + key);
    assert.throws(() => stageInspectionRegistration({ ...stageOptions(dir), [key]: wrong }), /unapproved-runtime-or-native/);
    assert.equal(fs.existsSync(dir), false);
  }
});

for (const operation of ["engine", "input-key", "unchanged-build"]) {
  test("actual accepted CLI through closed registered " + operation, { timeout: 180000 }, async () => {
    const dir = fixture("real-" + operation);
    const inputs = operation === "engine" ? {} : { ...supplied.inputs };
    if (operation === "input-key") delete inputs.state;
    const run = await startRegisteredInspection(registration, { operation, runRoot: dir, inputs });
    const initial = registeredInspectionStatus(run);
    assert.ok(initial.controllerIdentity.pid > 1);
    // The controller is observed before acknowledgement; normal fast operations
    // may have finished by the next event-loop turn, so do not invent a live
    // payload observation here. I3d separately qualified live registration.
    write(path.join(dir, "controller-bound.json"), initial);
    const result = await finishRegisteredInspection(run);
    assert.equal(result.exit.code, 0, result.stderr.toString());
    assert.equal(result.outputError, null);
    assert.equal(result.dataStreamsClosed, true);
    assert.equal(result.ownership.ownershipKnown, true);
    assert.equal(result.ownership.allRegisteredStopped, true);
    assert.equal(result.ownership.channelClosed, true);
    assert.equal(result.automaticReservationReleaseQualified, false);
    const output = JSON.parse(result.stdout);
    if (operation === "engine") assert.deepEqual(output, supplied.engine);
    if (operation === "input-key") {
      assert.equal(output.status, "observed-project-build-inputs");
      assert.equal(output.commandsExecuted, false);
      assert.equal(output.inputKey, supplied.inputKey);
    }
    if (operation === "unchanged-build") {
      assert.equal(output.status, "unchanged-project-build");
      assert.equal(output.inputKey, supplied.inputKey);
      assert.equal(output.verification, "not-repeated");
      assert.equal(output.activation, "not-performed");
    }
    assert.deepEqual(beforeState(), original);
    write(path.join(dir, "result.json"), { exit: result.exit, binding: result.binding,
      ownership: result.ownership, dataStreamsClosed: result.dataStreamsClosed,
      automaticReservationReleaseQualified: false, output, protectedStateUnchanged: true });
    const status = registeredInspectionStatus(run);
    write(path.join(dir, "terminal.json"), status);
    const ids = [status.controllerIdentity.pid, ...status.calls.flatMap(c => [c.guardianPid, c.nativePid])];
    const stopped = probeRegisteredInspection(registration, ids);
    assert.ok(Object.values(stopped.identities).every(value => value === null));
    assert.ok(Object.values(stopped.groupsStopped).every(value => value === true));
    write(path.join(dir, "independent-stop.json"), stopped);
  });
}

test("caller startup injection refuses before launch effects", async () => {
  const dir = fixture("startup-injection");
  const old = process.env.NODE_OPTIONS;
  process.env.NODE_OPTIONS = "--require=/caller/code";
  try {
    await assert.rejects(startRegisteredInspection(registration, { operation: "engine", runRoot: dir, inputs: {} }), /startup-injection/);
    assert.deepEqual(fs.readdirSync(dir), []);
  } finally {
    if (old === undefined) delete process.env.NODE_OPTIONS;else process.env.NODE_OPTIONS = old;
  }
  verifyInspectionRegistration(registration);
});

async function mutateAndRefuse(file, label, mutation) {
  const mode = fs.statSync(file).mode & 0o777;
  const bytes = fs.readFileSync(file);
  const dir = fixture(label);
  fs.chmodSync(file, 0o600);
  try {
    fs.writeFileSync(file, mutation ? mutation(bytes) : Buffer.concat([bytes, Buffer.from("\nchanged")]));
    fs.chmodSync(file, mode);
    await assert.rejects(startRegisteredInspection(registration, { operation: "engine", runRoot: dir, inputs: {} }), /closure-changed|manifest-changed/);
    assert.deepEqual(fs.readdirSync(dir), []);
    write(path.join(dir, "refusal.json"), { label, originalSha256: createHash("sha256").update(bytes).digest("hex"),
      changedSha256: sha(file), workloadStarted: false, runRootEmpty: true });
  } finally {
    fs.chmodSync(file, 0o600);fs.writeFileSync(file, bytes);fs.chmodSync(file, mode);
  }
  verifyInspectionRegistration(registration);
}

test("changed frozen controller refuses before interpreter startup", async () => {
  await mutateAndRefuse(path.join(registration.directory, "source/native_registered_controller.py"), "changed-controller");
});

test("changed stdlib, native extension and private dylib all refuse", async () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(registration.directory, "registration.json")));
  const rows = manifest.inventory.runtime;
  const names = [
    rows.find(row => row.kind === "file" && row.path.endsWith("/encodings/__init__.py")).path,
    rows.find(row => row.kind === "file" && row.path.includes("/lib-dynload/") && row.path.endsWith(".so")).path,
    rows.find(row => row.kind === "file" && row.path.endsWith("/libpython3.13.dylib")).path,
  ];
  const bytecode = rows.find(row => row.kind === "file" && row.path.endsWith(".pyc"));
  if (bytecode) names.push(bytecode.path);
  for (const [index, name] of names.entries())
    await mutateAndRefuse(path.join(registration.directory, "runtime", name), "changed-runtime-" + index);
  write(path.join(ROOT, "runtime-mutation-summary.json"), { filesChecked: names,
    bytecodePresentInPinnedArchive: Boolean(bytecode), absenceAlsoBoundByWholeTreeInventory: true });
});

test("forged OS/manifest declaration cannot authorize changed content", async () => {
  await mutateAndRefuse(path.join(registration.directory, "registration.json"), "changed-manifest",
    bytes => Buffer.from(JSON.stringify({ ...JSON.parse(bytes), qualifiedHost: { platform: "pretend" } }) + "\n"));
});

test("writable registration alias and unsafe driver lock refuse", async () => {
  await assert.rejects(startRegisteredInspection(registration, { operation: "engine", runRoot: registration.directory, inputs: {} }), /private-empty-inspection-root-required/);
  const state = fixture("unsafe-state");
  fs.writeFileSync(path.join(state, "driver.lock"), "nonempty", { mode: 0o600 });
  const dir = fixture("unsafe-lock-launch");
  await assert.rejects(startRegisteredInspection(registration, { operation: "unchanged-build", runRoot: dir,
    inputs: { ...supplied.inputs, state } }), /unsafe-inspection-driver-lock/);
  assert.deepEqual(fs.readdirSync(dir), []);
  assert.deepEqual(beforeState(), original);
});

test("hardlink alias in a separate snapshot prevents admission; primary stays exact", { timeout: 120000 }, () => {
  const secondary = stageInspectionRegistration(stageOptions(path.join(ROOT, "alias-registration")));
  const file = path.join(secondary.directory, "source/native_registered_controller.py");
  const alias = path.join(ROOT, "retained-hardlink.py");
  fs.linkSync(file, alias);
  assert.equal(fs.statSync(file).nlink, 2);
  assert.throws(() => verifyInspectionRegistration(secondary), /snapshot-special-file-or-hardlink/);
  // Retain both aliases. Never delete generated fixtures to make this pass.
  verifyInspectionRegistration(registration);
  write(path.join(ROOT, "hardlink-negative.json"), {
    retained: true, secondaryRegistrationIntentionallyInvalid: true,
    secondary: secondary.directory, alias, primaryUnchanged: true });
});

test("archive path changes cannot replace verified bytes; added bytecode refuses", { timeout: 120000 }, async () => {
  const archive = path.join(ROOT, "retained-race-input.tar.gz");
  fs.writeFileSync(archive, fs.readFileSync(supplied.archive), { mode: 0o600 });
  const readFile = fs.readFileSync;
  let changed = false;
  fs.readFileSync = function(file, ...args) {
    const bytes = readFile.call(fs, file, ...args);
    if (file === archive && !changed) {
      changed = true;
      fs.writeFileSync(archive, "controlled path replacement");
    }
    return bytes;
  };
  let race;
  try {
    race = stageInspectionRegistration({ ...stageOptions(path.join(ROOT, "race-registration")), archive });
  } finally { fs.readFileSync = readFile; }
  assert.equal(changed, true);
  assert.equal(verifyInspectionRegistration(race).privateMachOObjects, 10);
  // The pinned archive has no pyc files. Bind absence as well as content:
  // an extra bytecode tree must never enter an already approved closure.
  const encoding = path.join(race.directory, "runtime/python/lib/python3.13/encodings");
  fs.chmodSync(encoding, 0o700);
  const cache = path.join(encoding, "__pycache__");
  fs.mkdirSync(cache, { mode: 0o700 });
  fs.writeFileSync(path.join(cache, "controlled.cpython-313.pyc"), "not executable bytecode", { mode: 0o400 });
  fs.chmodSync(cache, 0o500);fs.chmodSync(encoding, 0o500);
  const dir = fixture("added-bytecode-launch");
  await assert.rejects(startRegisteredInspection(race, { operation: "engine", runRoot: dir, inputs: {} }), /closure-changed/);
  assert.deepEqual(fs.readdirSync(dir), []);
  verifyInspectionRegistration(registration);
  write(path.join(ROOT, "archive-race-and-bytecode.json"), {
    exactVerifiedBytesUsed: true, inputPathChanged: true, addedBytecodeRefused: true,
    secondarySnapshotIntentionallyInvalid: true, primaryUnchanged: true, workloadStartedAfterMutation: false });
});

test("changed destination copy cannot become an approved source snapshot", { timeout: 120000 }, () => {
  const writeFile = fs.writeFileSync;
  let corrupted = false;
  fs.writeFileSync = function(file, bytes, ...args) {
    if (String(file).endsWith("/source/native_registered_controller.py")) {
      corrupted = true;bytes = Buffer.concat([Buffer.from(bytes), Buffer.from("\nchanged destination")]);
    }
    return writeFile.call(fs, file, bytes, ...args);
  };
  const dir = path.join(ROOT, "corrupted-copy-registration");
  try { assert.throws(() => stageInspectionRegistration(stageOptions(dir)), /snapshot-copy-integrity/); }
  finally { fs.writeFileSync = writeFile; }
  assert.equal(corrupted, true);
  assert.equal(fs.existsSync(path.join(dir, "registration.json")), false);
  verifyInspectionRegistration(registration);
  write(path.join(ROOT, "copy-corruption.json"), {
    changedDestinationRefused: true, registrationPublished: false, interpreterStarted: false, primaryUnchanged: true });
});
