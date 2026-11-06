/** Staged receiver controls; no installed supervisor or source-trust activation. */
import test from "node:test";
import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { once } from "node:events";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";
import { NativeInspectionReceiver, sameIdentity } from "./native_inspection_receiver.mjs";

const SCRIPTS = path.dirname(fileURLToPath(import.meta.url));
const retain = process.env.PATAMAPS_TEST_RETAIN_ROOT;
assert.ok(retain && path.isAbsolute(retain), "canonical retained test root required");
const ROOT = fs.mkdtempSync(path.join(retain, "global-receiver-"));
fs.chmodSync(ROOT, 0o700);
const rootIdentity = { pid: 100, parentPid: 90, pgid: 100, startSeconds: 10, startMicroseconds: 1 };
const guardianIdentity = { pid: 200, parentPid: 100, pgid: 200, startSeconds: 11, startMicroseconds: 2 };
const nativeIdentity = { pid: 300, parentPid: 200, pgid: 300, startSeconds: 12, startMicroseconds: 3 };
const runId = "a".repeat(32);
const encode = row => Buffer.from(JSON.stringify(row) + "\n");
const copy = value => structuredClone(value);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function fixture(name) {
  const dir = path.join(ROOT, name);
  fs.mkdirSync(dir, { mode: 0o700 });
  return dir;
}
function sink(dir) {
  return (snapshot, frame) => {
    if (frame) {
      const fd = fs.openSync(path.join(dir, "journal.jsonl"), "a", 0o600);
      try { fs.writeSync(fd, JSON.stringify({ frame, snapshot }) + "\n"); fs.fsyncSync(fd); }
      finally { fs.closeSync(fd); }
    }
    fs.writeFileSync(path.join(dir, "status.json"), JSON.stringify(snapshot, null, 2), { mode: 0o600 });
  };
}
function frames() {
  const common = (event, sequence) => ({ event, runId, controllerPid: 100, sequence });
  const inner = (event, sequence) => ({ runId, guardianPid: 200, parentPid: 100, sequence, event });
  return [
    { ...common("guardian-launch-pending", 0), descriptorDigest: "b".repeat(64) },
    { ...common("guardian-started", 1), guardianPid: 200, guardianIdentity: copy(guardianIdentity) },
    { ...common("guardian-record", 2), record: inner("launch-pending", 0),
      nativeIdentity: null, registrationKnown: false, nativeAlreadyStopped: false },
    { ...common("guardian-record", 3), record: { ...inner("payload-started", 1), pid: 300, pgid: 300 },
      nativeIdentity: copy(nativeIdentity), registrationKnown: true, nativeAlreadyStopped: false },
    { ...common("guardian-record", 4), record: { ...inner("payload-stopped", 2), pid: 300, pgid: 300,
      returncode: 0, stdoutClosed: true, stderrClosed: true, bindingsUnchanged: true },
      nativeIdentity: copy(nativeIdentity), registrationKnown: true, nativeAlreadyStopped: false },
    { ...common("inspection-finished", 5), guardianPid: 200, controlComplete: true,
      cleanup: { confirmed: true, reason: "completed" } },
  ];
}
function mock(name, options = {}) {
  const dir = fixture(name);
  let stopped = false;
  const identities = new Map([rootIdentity, guardianIdentity, nativeIdentity].map(v => [v.pid, copy(v)]));
  const probe = async ids => ({
    identities: Object.fromEntries(ids.map(id => [id, stopped ? null : identities.get(id) ?? null])),
    groupsStopped: Object.fromEntries(ids.map(id => [id, stopped])),
  });
  const receiver = new NativeInspectionReceiver({
    controllerIdentity: rootIdentity, probe, persist: sink(dir), ...options,
  });
  return { dir, receiver, identities, stop() { stopped = true; } };
}
async function feed(receiver, rows = frames()) {
  for (const row of rows) await receiver.write(encode(row));
}

test("live registration persists before controller exit and independently confirms stop", async () => {
  const f = mock("live-and-stop");
  await feed(f.receiver, frames().slice(0, 4));
  const live = JSON.parse(fs.readFileSync(path.join(f.dir, "status.json")));
  assert.equal(live.calls[0].registrationKnown, true);
  assert.equal(live.channelClosed, false);
  assert.equal((await f.receiver.assessStopped()).allRegisteredStopped, false);
  await feed(f.receiver, frames().slice(4));
  f.receiver.end(); f.stop();
  const assessment = await f.receiver.assessStopped();
  assert.equal(assessment.ownershipKnown, true);
  assert.equal(assessment.allRegisteredStopped, true);
  assert.equal(assessment.automaticReservationReleaseQualified, false);
});

test("fragmentation and multiple complete records in one chunk", async () => {
  const f = mock("fragmented");
  const bytes = Buffer.concat(frames().map(encode));
  for (let i = 0; i < bytes.length; i += 7) await f.receiver.write(bytes.subarray(i, i + 7));
  f.receiver.end();
  assert.equal(f.receiver.snapshot().frames, 6);
  assert.equal(f.receiver.snapshot().failure, null);
  const g = mock("combined");
  await g.receiver.write(bytes); g.receiver.end();
  assert.equal(g.receiver.snapshot().frames, 6);
});

test("pending ownership stays unknown after zero exit and all known processes stop", async () => {
  const f = mock("pending-normal-zero");
  await feed(f.receiver, frames().slice(0, 3));
  f.receiver.noteControllerExit(0, null); f.receiver.end(); f.stop();
  const status = await f.receiver.assessStopped();
  assert.equal(status.ownershipKnown, false);
  assert.equal(status.allRegisteredStopped, true);
  assert.equal(status.automaticReservationReleaseQualified, false);
});

test("registered crash needs OS confirmation even without a terminal record", async () => {
  const f = mock("registered-crash");
  await feed(f.receiver, frames().slice(0, 4));
  f.receiver.noteControllerExit(null, "SIGKILL"); f.receiver.end();
  assert.equal((await f.receiver.assessStopped()).allRegisteredStopped, false);
  f.stop();
  assert.equal((await f.receiver.assessStopped()).ownershipKnown, true);
  assert.equal((await f.receiver.assessStopped()).allRegisteredStopped, true);
  assert.equal(f.receiver.snapshot().calls[0].controlComplete, false);
});

for (const [name, mutate] of [
  ["duplicate", rows => rows.splice(2, 0, copy(rows[1]))],
  ["wrong-controller", rows => { rows[0].controllerPid = 999; }],
  ["changed-run", rows => { rows[2].record.runId = "c".repeat(32); }],
  ["changed-guardian", rows => { rows[3].record.guardianPid = 999; }],
  ["wrong-parent", rows => { rows[3].nativeIdentity.parentPid = 999; }],
  ["wrong-group", rows => { rows[3].nativeIdentity.pgid = 999; }],
  ["missing-identity", rows => { rows[1].guardianIdentity = null; }],
  ["changed-identity", rows => { rows[4].nativeIdentity.startMicroseconds++; }],
  ["unknown-field", rows => { rows[2].claimedTrusted = true; }],
  ["false-completion", rows => { rows[4].record.bindingsUnchanged = false; }],
  ["early-completion", rows => { rows.splice(3, 2); rows[3].sequence = 3; }],
  ["overlapping-calls", rows => { rows[1] = { ...rows[0], runId: "d".repeat(32) }; }],
]) {
  test(name + " permanently refuses even after zero exit", async () => {
    const f = mock(name); const rows = frames(); mutate(rows);
    await feed(f.receiver, rows); f.receiver.noteControllerExit(0, null); f.receiver.end(); f.stop();
    assert.ok(f.receiver.snapshot().failure);
    await feed(f.receiver); // Refusal cannot be erased.
    assert.equal((await f.receiver.assessStopped()).ownershipKnown, false);
  });
}

test("PID microsecond mismatch refuses independent registration", async () => {
  const f = mock("microsecond-mismatch");
  f.identities.get(300).startMicroseconds++;
  await feed(f.receiver);
  assert.match(f.receiver.snapshot().failure, /identity-mismatch/);
});

test("absent registered leader with a surviving group refuses", async () => {
  const f = mock("gone-leader-live-group");
  f.identities.delete(300);
  await feed(f.receiver);
  assert.match(f.receiver.snapshot().failure, /group-survives/);
});

test("already-stopped payload requires an independent absent identity and group", async () => {
  const f = mock("early-stop-independent");
  const rows = frames();
  f.identities.delete(300);
  const probe = f.receiver.probe;
  f.receiver.probe = async ids => {
    const value = await probe(ids);
    if (ids.includes(300)) value.groupsStopped[300] = true;
    return value;
  };
  for (const row of rows.slice(3, 5)) {
    row.nativeIdentity = null; row.nativeAlreadyStopped = true;
  }
  await feed(f.receiver, rows); f.receiver.end(); f.stop();
  assert.equal(f.receiver.snapshot().failure, null);
  assert.equal((await f.receiver.assessStopped()).ownershipKnown, true);
});

for (const [name, bytes] of [
  ["malformed-json", Buffer.from("{broken}\n")],
  ["duplicate-json-key", Buffer.from('{"event":"x","event":"y"}\n')],
  ["oversized-record", Buffer.alloc(500000, 120)],
  ["invalid-utf8", Buffer.from([255, 10])],
  ["partial-record", Buffer.from('{"event":')],
  ["empty-channel", Buffer.alloc(0)],
]) {
  test(name + " is bounded and unconfirmed", async () => {
    const f = mock(name); await f.receiver.write(bytes); f.receiver.end();
    assert.ok(f.receiver.snapshot().failure);
    assert.ok(f.receiver.buffer.length <= 4096);
    assert.equal((await f.receiver.assessStopped()).ownershipKnown, false);
  });
}

test("byte/call limits and reuse after EOF refuse", async () => {
  const f = mock("call-limit");
  for (let i = 0; i < 17; i++) {
    const rows = frames();
    for (const row of rows) {
      row.runId = i.toString(16).padStart(32, "0");
      if (row.record) row.record.runId = row.runId;
    }
    await feed(f.receiver, rows);
  }
  assert.match(f.receiver.snapshot().failure, /call-limit/);
  const g = mock("after-close"); await feed(g.receiver); g.receiver.end();
  await g.receiver.write(encode(frames()[0]));
  assert.ok(g.receiver.snapshot().failure);
});

test("probe and persistence failures cannot produce confirmed ownership", async () => {
  const f = mock("probe-error", { probe: async () => { throw new Error("probe unavailable"); } });
  await feed(f.receiver); f.receiver.end();
  assert.ok(f.receiver.snapshot().failure);
  assert.equal((await f.receiver.assessStopped()).allRegisteredStopped, false);
  let publications = 0;
  const g = mock("persistence-error", {
    persist() { if (++publications > 1) throw new Error("journal unavailable"); },
  });
  await feed(g.receiver); g.receiver.end();
  assert.match(g.receiver.snapshot().failure, /journal unavailable/);
});

test("parent reparenting preserves identity but microsecond reuse does not", () => {
  assert.equal(sameIdentity(rootIdentity, { ...rootIdentity, parentPid: 1 }), true);
  assert.equal(sameIdentity(rootIdentity, { ...rootIdentity, startMicroseconds: 9 }), false);
});

const WORKER = `
from pathlib import Path
import json,os,signal,subprocess,sys,time
sys.path.insert(0,SCRIPTS)
import native_inspection_guard as live
case=Path(sys.argv[1]);mode=sys.argv[2]
if mode=="unsealed":
 def spawn(descriptor,values,control_write,*,stdout=subprocess.PIPE,stderr=subprocess.PIPE):
  return subprocess.Popen([sys.executable,"-I","-S","-B",str(case/"fake.py"),str(descriptor),str(control_write),str(case)],
   stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,pass_fds=(control_write,),close_fds=True,start_new_session=True)
 live.InspectionRunner.spawn=staticmethod(spawn)
run=live.InspectionRunner(case/"jobs",case,strict=True,stop_grace=.2,lifecycle_fd=3)
payload="from pathlib import Path\\nimport json,os,signal,time\\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\\nclosed=True\\nfor fd in range(3,96):\\n try:os.write(fd,b'forged');closed=False\\n except OSError:pass\\nPath('ready').write_text('ready')\\nwhile not Path('go').exists():time.sleep(.02)\\nprint(json.dumps(dict(extraDescriptorsClosed=closed)))"
code=1
try:
 result=run([str(Path(sys.executable).resolve()),"-I","-S","-B","-c",payload],
  stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,check=False)
 (case/"result.json").write_text(json.dumps(dict(code=result.returncode,stdout=result.stdout.decode(),calls=run.calls)))
 code=result.returncode
except BaseException as error:
 (case/"result.json").write_text(json.dumps(dict(error=str(error),calls=run.calls)))
finally:os.close(3)
sys.exit(code)
`;
const FAKE = `
from pathlib import Path
import json,os,subprocess,sys,time
sys.path.insert(0,SCRIPTS)
import native_inspection_guard as live
d=json.loads(Path(sys.argv[1]).read_text());fd=int(sys.argv[2]);case=Path(sys.argv[3])
os.write(fd,(json.dumps(dict(runId=d["runId"],guardianPid=os.getpid(),parentPid=os.getppid(),sequence=0,event="launch-pending"))+"\\n").encode())
child=subprocess.Popen(["/bin/sleep","60"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True)
(case/"unregistered.json").write_text(json.dumps(live.process_identity(child.pid)))
time.sleep(60)
`;
const PROBE = `
import json,sys
sys.path.insert(0,SCRIPTS)
import native_inspection_guard as live
ids=json.loads(sys.argv[1])
assert isinstance(ids,list) and len(ids)<=64 and all(type(x)is int and x>1 for x in ids)
print(json.dumps(dict(identities={str(x):live.process_identity(x) for x in ids},groupsStopped={str(x):not live.group_live(x) for x in ids})))
`;
const STOP = `
import json,sys
sys.path.insert(0,SCRIPTS)
import native_inspection_guard as live
identity=json.loads(sys.argv[1])
assert live.stop_registered(identity,.2)
`;
const python = process.env.PATAMAPS_QUALIFIED_PYTHON;
const realOptions = { skip: os.platform() !== "darwin", timeout: 45000 };
for (const mode of ["normal", "controller-crash", "guardian-crash", "unsealed"]) {
  test("real private channel: " + mode, realOptions, async () => {
    assert.ok(python && path.isAbsolute(python));
    const dir = fixture("real-" + mode);
    fs.mkdirSync(path.join(dir, "jobs"), { mode: 0o700 });
    const withScripts = source => source.replaceAll("SCRIPTS", JSON.stringify(SCRIPTS));
    for (const [name, source] of Object.entries({ "worker.py": WORKER, "fake.py": FAKE, "probe.py": PROBE, "stop.py": STOP })) {
      fs.writeFileSync(path.join(dir, name), withScripts(source), { mode: 0o600 });
    }
    const env = { PATH: "/usr/bin:/bin", LANG: "C", PYTHONDONTWRITEBYTECODE: "1" };
    const command = (file, arg) => execFileSync(python, ["-I", "-S", "-B", path.join(dir, file), JSON.stringify(arg)],
      { env, encoding: "utf8", timeout: 5000, maxBuffer: 65536 });
    const probe = async ids => JSON.parse(command("probe.py", ids));
    const stop = identity => command("stop.py", identity);
    const sentinel = spawn("/bin/sleep", ["60"], { detached: true, stdio: "ignore", env });
    const sentinelClosed = once(sentinel, "close");
    const sentinelIdentity = (await probe([sentinel.pid])).identities[sentinel.pid];
    assert.ok(sentinelIdentity);
    const child = spawn(python, ["-I", "-S", "-B", path.join(dir, "worker.py"), dir, mode],
      { detached: true, stdio: ["ignore", "pipe", "pipe", "pipe"], env });
    const closed = once(child, "close");
    child.stdout.pipe(fs.createWriteStream(path.join(dir, "controller.stdout")));
    child.stderr.pipe(fs.createWriteStream(path.join(dir, "controller.stderr")));
    const identity = (await probe([child.pid])).identities[child.pid];
    assert.ok(identity);
    const receiver = new NativeInspectionReceiver({ controllerIdentity: identity, probe, persist: sink(dir) });
    const consuming = receiver.consume(child.stdio[3]);
    child.once("exit", (code, signal) => receiver.noteControllerExit(code, signal));
    let unregistered = null;
    async function until(predicate, ms = 12000) {
      const deadline = Date.now() + ms;
      while (Date.now() < deadline) {
        if (await predicate()) return;
        assert.equal(receiver.snapshot().failure, null, JSON.stringify(receiver.snapshot()));
        await pause(30);
      }
      assert.fail("timed out: " + JSON.stringify(receiver.snapshot()));
    }
    async function killExact(expected) {
      const current = (await probe([expected.pid])).identities[expected.pid];
      assert.ok(sameIdentity(expected, current), "refuse signalling replacement instance");
      process.kill(-expected.pid, "SIGKILL");
    }
    try {
      if (mode === "unsealed") {
        await until(() => receiver.snapshot().frames >= 3 && fs.existsSync(path.join(dir, "unregistered.json")));
        unregistered = JSON.parse(fs.readFileSync(path.join(dir, "unregistered.json")));
        assert.ok((await probe([unregistered.pid])).identities[unregistered.pid]);
        await killExact(identity);
        await killExact(receiver.snapshot().calls[0].guardianIdentity);
      } else {
        await until(() => receiver.snapshot().calls.some(c => c.registrationKnown));
        const snapshot = receiver.snapshot();
        const call = snapshot.calls[0];
        fs.writeFileSync(path.join(dir, "observed-live.json"), JSON.stringify({
          snapshot, probe: await probe([child.pid, call.guardianPid, call.nativePid]),
        }, null, 2));
        const jobs = fs.readdirSync(path.join(dir, "jobs"));
        assert.equal(jobs.length, 1);
        const work = path.join(dir, "jobs", jobs[0], "work");
        await until(() => fs.existsSync(path.join(work, "ready")));
        if (mode === "normal") fs.writeFileSync(path.join(work, "go"), "go");
        if (mode === "controller-crash") await killExact(identity);
        if (mode === "guardian-crash") await killExact(call.guardianIdentity);
      }
      await closed; await consuming;
      let assessment;
      await until(async () => {
        assessment = await receiver.assessStopped();
        return assessment.allRegisteredStopped;
      });
      assert.equal(assessment.ownershipKnown, mode !== "unsealed");
      assert.equal(assessment.channelClosed, true);
      assert.equal(assessment.automaticReservationReleaseQualified, false);
      if (mode === "normal") {
        assert.equal(receiver.snapshot().calls[0].controlComplete, true);
        const result = JSON.parse(fs.readFileSync(path.join(dir, "result.json")));
        assert.equal(JSON.parse(result.stdout).extraDescriptorsClosed, true);
      } else assert.equal(receiver.snapshot().calls[0].controlComplete, false);
      if (unregistered) {
        const surviving = await probe([unregistered.pid]);
        assert.ok(sameIdentity(unregistered, surviving.identities[unregistered.pid]));
        fs.writeFileSync(path.join(dir, "survivor-before-cleanup.json"), JSON.stringify(surviving, null, 2));
      }
      assert.ok(sameIdentity(sentinelIdentity, (await probe([sentinel.pid])).identities[sentinel.pid]));
      fs.writeFileSync(path.join(dir, "assessment.json"), JSON.stringify({
        ...assessment, sentinelUnchanged: true, unregisteredSurvivorObserved: unregistered !== null,
      }, null, 2));
    } finally {
      // Independent test harness cleanup, never the receiver's release proof.
      if (!unregistered && fs.existsSync(path.join(dir, "unregistered.json")))
        unregistered = JSON.parse(fs.readFileSync(path.join(dir, "unregistered.json")));
      const candidates = [identity, ...receiver.snapshot().calls.flatMap(c =>
        [c.guardianIdentity, c.nativeIdentity]).filter(Boolean), unregistered, sentinelIdentity].filter(Boolean);
      const stopped = [];
      for (const known of candidates) {
        const current = (await probe([known.pid])).identities[known.pid];
        if (current !== null) {
          assert.ok(sameIdentity(known, current));
          stop(known);
        }
        stopped.push(known);
      }
      await closed; await sentinelClosed;
      const finalProbe = await probe(stopped.map(v => v.pid));
      fs.writeFileSync(path.join(dir, "cleanup.json"), JSON.stringify({ identities: stopped, finalProbe }, null, 2));
      assert.ok(Object.values(finalProbe.groupsStopped).every(Boolean));
      assert.ok(Object.values(finalProbe.identities).every(v => v === null));
    }
  });
}

test("valid-looking duplicate keys cannot silently become an accepted launch", async () => {
  const f = mock("duplicate-valid-launch");
  const raw = JSON.stringify(frames()[0]).replace('"event":', '"event":"guardian-launch-pending","event":') + "\n";
  fs.writeFileSync(path.join(f.dir, "input.jsonl"), raw);
  await f.receiver.write(Buffer.from(raw)); f.receiver.end(); f.stop();
  assert.match(f.receiver.snapshot().failure, /noncanonical/);
  assert.equal(f.receiver.snapshot().frames, 0);
  assert.equal((await f.receiver.assessStopped()).ownershipKnown, false);
});

test("individual record bound refuses before the aggregate channel limit", async () => {
  const f = mock("individual-record-limit");
  const raw = Buffer.alloc(4097, 120);
  fs.writeFileSync(path.join(f.dir, "input.raw"), raw);
  await f.receiver.write(raw); f.receiver.end();
  assert.match(f.receiver.snapshot().failure, /record-byte-limit/);
  assert.ok(f.receiver.snapshot().bytes < 16 * 6 * 4096);
  assert.equal(f.receiver.buffer.length, 0);
});

test("stream errors cannot become ordinary EOF completion", async () => {
  const f = mock("stream-error");
  const stream = (async function* () {
    yield Buffer.concat(frames().slice(0, 4).map(encode));
    throw new Error("controlled transport loss");
  })();
  await f.receiver.consume(stream); f.stop();
  assert.match(f.receiver.snapshot().failure, /control-channel-error/);
  assert.equal((await f.receiver.assessStopped()).ownershipKnown, false);
});
