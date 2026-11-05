/**
 * Staged collector for the existing InspectionRunner private channel.
 *
 * This is NOT a source/runtime registry or an installed release authority.
 * Kernel probes are supplied by the containing trusted supervisor. Nothing in
 * stdout, a token, a digest declaration, or this module authorizes a workload.
 * It never signals processes or releases reservations.
 */
import { TextDecoder } from "node:util";

const MAX_RECORD = 4096;
const MAX_CALLS = 16;
const EVENTS = new Set(["guardian-launch-pending", "guardian-started",
  "guardian-record", "inspection-finished"]);
const identityKeys = ["pid", "parentPid", "pgid", "startSeconds", "startMicroseconds"];
const commonKeys = ["event", "runId", "controllerPid", "sequence"];
const extraKeys = {
  "guardian-launch-pending": ["descriptorDigest"],
  "guardian-started": ["guardianPid", "guardianIdentity"],
  "guardian-record": ["record", "nativeIdentity", "registrationKnown", "nativeAlreadyStopped"],
  "inspection-finished": ["guardianPid", "controlComplete", "cleanup"],
};
const clone = value => structuredClone(value);
const integer = value => Number.isSafeInteger(value);
const pid = value => integer(value) && value > 1;
const boolean = value => typeof value === "boolean";
function need(condition, reason) {
  if (!condition) throw new Error(reason);
}
function exact(value, keys) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
export function validIdentity(value) {
  return exact(value, identityKeys) && pid(value.pid) && integer(value.parentPid) && value.parentPid >= 1 &&
    pid(value.pgid) && integer(value.startSeconds) && value.startSeconds > 0 &&
    integer(value.startMicroseconds) && value.startMicroseconds >= 0 &&
    value.startMicroseconds < 1000000;
}
export function sameIdentity(left, right) {
  // A process can legitimately be reparented after its owner dies.
  return validIdentity(left) && validIdentity(right) &&
    ["pid", "pgid", "startSeconds", "startMicroseconds"].every(key => left[key] === right[key]);
}

export class NativeInspectionReceiver {
  constructor({ controllerIdentity, probe, persist }) {
    need(validIdentity(controllerIdentity) &&
      controllerIdentity.pid === controllerIdentity.pgid, "controller-identity-unconfirmed");
    need(typeof probe === "function" && typeof persist === "function", "receiver-services-required");
    this.controller = clone(controllerIdentity);
    this.probe = probe;
    this.persist = persist;
    this.calls = new Map();
    this.buffer = Buffer.alloc(0);
    this.bytes = 0;
    this.frames = 0;
    this.closed = false;
    this.failure = null;
    this.busy = false;
    this.controllerOutcome = null;
    this.publish(null);
  }

  snapshot() {
    return clone({
      version: 1, controllerIdentity: this.controller,
      channelClosed: this.closed, failure: this.failure,
      bytes: this.bytes, frames: this.frames, controllerOutcome: this.controllerOutcome,
      calls: [...this.calls.values()],
      // The receiver cannot manufacture source trust from a caller declaration.
      sourceRuntimeRegistration: "unqualified",
      automaticReservationReleaseQualified: false,
    });
  }

  publish(frame) {
    this.persist(this.snapshot(), frame === null ? null : clone(frame));
  }

  refuse(reason) {
    // A later complete-looking record must never erase uncertainty.
    this.failure ??= String(reason).slice(0, 240);
    this.buffer = Buffer.alloc(0);
    try { this.publish(null); } catch { /* Caller still receives permanent refusal. */ }
  }

  async observed(identity, expectedParent) {
    need(validIdentity(identity) && identity.pid === identity.pgid &&
      identity.parentPid === expectedParent, "claimed-process-relationship-invalid");
    const observed = await this.probe([identity.pid]);
    need(exact(observed, ["identities", "groupsStopped"]) &&
      exact(observed.identities, [String(identity.pid)]) &&
      exact(observed.groupsStopped, [String(identity.pid)]), "kernel-probe-incomplete");
    const current = observed.identities[identity.pid];
    need(boolean(observed.groupsStopped[identity.pid]), "kernel-group-state-unconfirmed");
    if (current === null) {
      need(observed.groupsStopped[identity.pid], "registered-leader-gone-group-survives");
    } else {
      need(sameIdentity(identity, current) && current.parentPid === expectedParent,
        "registered-process-identity-mismatch");
    }
  }

  async accept(frame) {
    need(exact(frame, [...commonKeys, ...(extraKeys[frame?.event] ?? [])]) &&
      EVENTS.has(frame.event) && typeof frame.runId === "string" &&
      /^[0-9a-f]{32}$/.test(frame.runId) &&
      frame.controllerPid === this.controller.pid && integer(frame.sequence) &&
      frame.sequence >= 0 && frame.sequence < 6, "outer-frame-schema");
    let call = this.calls.get(frame.runId);
    if (!call) {
      need(this.calls.size < MAX_CALLS && frame.event === "guardian-launch-pending" &&
        frame.sequence === 0 && [...this.calls.values()].every(value => value.finished),
        "unexpected-launch-or-call-limit");
      need(typeof frame.descriptorDigest === "string" &&
        /^[0-9a-f]{64}$/.test(frame.descriptorDigest), "descriptor-digest-schema");
      call = { runId: frame.runId, nextSequence: 0, phase: "guardian-launch-pending",
        declaredDescriptorDigest: frame.descriptorDigest, guardianPid: null,
        guardianIdentity: null, nativePid: null, nativeIdentity: null,
        nativeAlreadyStopped: false, registrationKnown: false, innerCount: 0,
        finished: false, controlComplete: false, terminalFlags: null };
      this.calls.set(frame.runId, call);
    }
    need(!call.finished && frame.sequence === call.nextSequence, "outer-frame-order");
    if (frame.event === "guardian-launch-pending") {
      need(call.nextSequence === 0, "duplicate-launch");
    } else if (frame.event === "guardian-started") {
      need(call.nextSequence === 1 && pid(frame.guardianPid), "guardian-start-order");
      // An absent identity cannot prove which process instance was launched.
      await this.observed(frame.guardianIdentity, this.controller.pid);
      need(frame.guardianIdentity.pid === frame.guardianPid, "guardian-pid-mismatch");
      call.guardianPid = frame.guardianPid;
      call.guardianIdentity = clone(frame.guardianIdentity);
    } else if (frame.event === "guardian-record") {
      need(call.guardianIdentity !== null && call.innerCount < 3 &&
        call.nextSequence === call.innerCount + 2, "inner-frame-order");
      const row = frame.record;
      const innerCommon = ["event", "runId", "guardianPid", "parentPid", "sequence"];
      const schemas = [innerCommon, [...innerCommon, "pid", "pgid"],
        [...innerCommon, "pid", "pgid", "returncode", "stdoutClosed", "stderrClosed",
          "bindingsUnchanged"]];
      need(exact(row, schemas[call.innerCount]) &&
        row.event === ["launch-pending", "payload-started", "payload-stopped"][call.innerCount] &&
        row.runId === call.runId && row.guardianPid === call.guardianPid &&
        row.parentPid === this.controller.pid && row.sequence === call.innerCount &&
        boolean(frame.registrationKnown) && boolean(frame.nativeAlreadyStopped), "inner-frame-schema");
      if (call.innerCount === 0) {
        need(frame.nativeIdentity === null && !frame.registrationKnown &&
          !frame.nativeAlreadyStopped, "premature-registration");
      } else if (call.innerCount === 1) {
        need(pid(row.pid) && row.pgid === row.pid && frame.registrationKnown,
          "payload-group-schema");
        if (frame.nativeAlreadyStopped) {
          need(frame.nativeIdentity === null, "stopped-payload-identity");
          const observed = await this.probe([row.pid]);
          need(exact(observed, ["identities", "groupsStopped"]) &&
            exact(observed.identities, [String(row.pid)]) &&
            exact(observed.groupsStopped, [String(row.pid)]) &&
            observed.identities[row.pid] === null && observed.groupsStopped[row.pid] === true,
            "early-payload-stop-unconfirmed");
        } else {
          await this.observed(frame.nativeIdentity, call.guardianPid);
          need(frame.nativeIdentity.pid === row.pid, "payload-pid-mismatch");
        }
        call.nativePid = row.pid;
        call.nativeIdentity = clone(frame.nativeIdentity);
        call.nativeAlreadyStopped = frame.nativeAlreadyStopped;
        call.registrationKnown = true;
      } else {
        need(row.pid === call.nativePid && row.pgid === call.nativePid &&
          integer(row.returncode) &&
          ["stdoutClosed", "stderrClosed", "bindingsUnchanged"].every(k => boolean(row[k])) &&
          frame.registrationKnown === call.registrationKnown &&
          frame.nativeAlreadyStopped === call.nativeAlreadyStopped &&
          JSON.stringify(frame.nativeIdentity) === JSON.stringify(call.nativeIdentity),
          "payload-terminal-schema");
        call.terminalFlags = Object.fromEntries(
          ["stdoutClosed", "stderrClosed", "bindingsUnchanged"].map(k => [k, row[k]]));
      }
      call.innerCount++;
    } else {
      need(frame.guardianPid === call.guardianPid && boolean(frame.controlComplete) &&
        exact(frame.cleanup, ["confirmed", "reason"]) && boolean(frame.cleanup.confirmed) &&
        typeof frame.cleanup.reason === "string" && frame.cleanup.reason.length <= 1024,
        "inspection-finish-schema");
      if (frame.controlComplete) {
        need(call.innerCount === 3 && call.registrationKnown && frame.cleanup.confirmed &&
          Object.values(call.terminalFlags).every(value => value === true),
          "false-completion");
      }
      call.finished = true;
      call.controlComplete = frame.controlComplete;
      // Cleanup is a controller claim, never an independent OS stop proof.
      call.declaredCleanup = clone(frame.cleanup);
    }
    call.phase = frame.event === "guardian-record" ? frame.record.event : frame.event;
    call.nextSequence++;
    this.frames++;
    this.publish(frame);
  }

  async write(chunk) {
    if (this.failure) return;
    if (this.busy) { this.refuse("concurrent-receiver-write"); return; }
    this.busy = true;
    try {
      need(!this.closed && Buffer.isBuffer(chunk), "closed-or-invalid-channel");
      this.bytes += chunk.length;
      need(this.bytes <= MAX_CALLS * 6 * MAX_RECORD, "outer-channel-byte-limit");
      // Bound retention even for a producer delivering one oversized chunk.
      let offset = 0;
      while (offset < chunk.length) {
        const newline = chunk.indexOf(10, offset);
        const end = newline < 0 ? chunk.length : newline;
        need(this.buffer.length + end - offset <= MAX_RECORD, "outer-record-byte-limit");
        this.buffer = Buffer.concat([this.buffer, chunk.subarray(offset, end)]);
        offset = end + (newline < 0 ? 0 : 1);
        if (newline < 0) break;
        const text = new TextDecoder("utf-8", { fatal: true }).decode(this.buffer);
        this.buffer = Buffer.alloc(0);
        const frame = JSON.parse(text);
        // InspectionRunner emits compact JSON. Re-encoding rejects duplicate
        // keys and alternate numeric encodings instead of silently normalizing
        // ambiguous records. Noncanonical input conservatively holds.
        need(JSON.stringify(frame) === text, "noncanonical-control-record");
        await this.accept(frame);
      }
    } catch (error) {
      this.refuse(error.message);
    } finally {
      this.busy = false;
    }
  }

  end() {
    if (this.closed) { this.refuse("duplicate-channel-close"); return; }
    if (this.busy) { this.refuse("channel-closed-during-write"); return; }
    this.closed = true;
    if (this.buffer.length) this.refuse("partial-control-record");
    else if (!this.calls.size) this.refuse("missing-launch-records");
    try { this.publish(null); } catch (error) { this.refuse(error.message); }
  }

  async consume(stream) {
    try {
      for await (const chunk of stream) {
        await this.write(chunk);
        if (this.failure) {
          // Continue draining a bounded? No: close only the private read end;
          // the containing supervisor must stop the owned controller. A bad
          // producer cannot make us accumulate or log unbounded output.
          stream.destroy();
          break;
        }
      }
      this.end();
    } catch (error) {
      this.refuse("control-channel-error: " + error.message);
    }
  }

  noteControllerExit(code, signal) {
    this.controllerOutcome = { code, signal };
    try { this.publish(null); } catch (error) { this.refuse(error.message); }
  }

  async assessStopped() {
    const calls = [...this.calls.values()];
    const ownershipKnown = !this.failure && calls.length > 0 &&
      calls.every(call => call.guardianIdentity !== null && call.registrationKnown);
    const identities = [this.controller, ...calls.flatMap(call =>
      [call.guardianIdentity, call.nativeIdentity].filter(Boolean))];
    const ids = [...new Set([...identities.map(value => value.pid),
      ...calls.map(call => call.nativePid).filter(value => value !== null)])];
    let allRegisteredStopped = false;
    let probeError = null;
    try {
      const observed = await this.probe(ids);
      need(exact(observed, ["identities", "groupsStopped"]) &&
        exact(observed.identities, ids.map(String)) &&
        exact(observed.groupsStopped, ids.map(String)), "stop-probe-incomplete");
      allRegisteredStopped = ids.every(id => observed.identities[id] === null &&
        observed.groupsStopped[id] === true);
    } catch (error) {
      probeError = String(error.message).slice(0, 240);
    }
    return { ownershipKnown, allRegisteredStopped, channelClosed: this.closed,
      protocolFailure: this.failure, probeError,
      sourceRuntimeRegistration: "unqualified",
      automaticReservationReleaseQualified: false };
  }
}
