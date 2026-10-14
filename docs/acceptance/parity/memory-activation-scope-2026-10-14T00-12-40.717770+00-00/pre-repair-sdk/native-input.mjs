/** @internal Bounded input delivery; all product decisions execute in Rust. */
import { spawnSync } from "node:child_process";
import {
  MessageChannel,
  Worker,
  receiveMessageOnPort,
} from "node:worker_threads";
import { getSystemErrorMap } from "node:util";

function processError(executable, arguments_, code) {
  const error = new Error(`spawnSync ${executable} ${code}`);
  error.errno = [...getSystemErrorMap()].find(
    ([, value]) => value[0] === code,
  )?.[0];
  error.code = code;
  error.syscall = `spawnSync ${executable}`;
  error.path = executable;
  error.spawnargs = arguments_;
  return error;
}

export function spawnWithInputSync(executable, arguments_, options) {
  if (process.platform !== "darwin")
    return spawnSync(executable, arguments_, options);
  // Node 22's synchronous pipe loop can leave a macOS reader waiting. A worker
  // closes the async input stream while the calling API stays synchronous.
  // No files, shell, semantic interpreter or timeout extension are involved.
  const deadline =
    process.hrtime.bigint() + BigInt(options.timeout) * 1_000_000n;
  const state = new Int32Array(new SharedArrayBuffer(4));
  const { port1, port2 } = new MessageChannel();
  const worker = new Worker(
    new URL("./native-input-worker.mjs", import.meta.url),
    {
      workerData: {
        executable,
        arguments_,
        options,
        deadline,
        state: state.buffer,
        port: port2,
      },
      transferList: [port2],
      execArgv: [],
    },
  );
  worker.unref();
  port1.unref();
  // Keep exceptional bootstrap errors from becoming an unhandled event after
  // this synchronous call returns; ordinary process failures arrive by port.
  worker.on("error", () => {});
  const stdoutChunks = [],
    stderrChunks = [];
  let packet;
  function drain() {
    let queued;
    while ((queued = receiveMessageOnPort(port1)?.message)) {
      if (queued.stream)
        (queued.stream === "stdout" ? stdoutChunks : stderrChunks).push(
          Buffer.from(queued.data),
        );
      else packet = queued;
    }
  }
  while (!packet) {
    const sequence = Atomics.load(state, 0);
    drain();
    if (packet) break;
    const remaining = Number(deadline - process.hrtime.bigint()) / 1_000_000;
    if (remaining <= 0) break;
    Atomics.wait(state, 0, sequence, remaining);
  }
  drain();
  const stdout = Buffer.concat(stdoutChunks),
    stderr = Buffer.concat(stderrChunks);
  const streams = {
    stdout: options.encoding ? stdout.toString(options.encoding) : stdout,
    stderr: options.encoding ? stderr.toString(options.encoding) : stderr,
  };
  if (!packet) {
    port1.postMessage("cancel");
    port1.close();
    return {
      status: null,
      signal: "SIGTERM",
      ...streams,
      error: processError(executable, arguments_, "ETIMEDOUT"),
    };
  }
  port1.close();
  const result = {
    pid: packet.pid,
    status: packet.status,
    signal: packet.signal,
    ...streams,
  };
  if (packet.error) {
    result.error = processError(executable, arguments_, packet.error.code);
    if (packet.error.message)
      result.error.message = packet.error.message.replace(
        /^spawn /,
        "spawnSync ",
      );
  }
  return result;
}
