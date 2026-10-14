/** @internal Transport worker: deliver bytes, enforce limits, reap the child. */
import { spawn } from "node:child_process";
import { workerData } from "node:worker_threads";

const { executable, arguments_, options, deadline, port } = workerData;
const state = new Int32Array(workerData.state);
const remaining = Math.max(
  1,
  Math.floor(Number(deadline - process.hrtime.bigint()) / 1_000_000),
);
const child = spawn(executable, arguments_, {
  env: options.env,
  stdio: ["pipe", "pipe", "pipe"],
});
let bytes = 0,
  failure,
  stopped;
const timer = setTimeout(() => {
  stopped ??= "ETIMEDOUT";
  child.kill("SIGTERM");
}, remaining);
port.on("message", () => {
  stopped ??= "ETIMEDOUT";
  child.kill("SIGTERM");
});
function collect(stream, chunk) {
  port.postMessage({ stream, data: chunk });
  Atomics.add(state, 0, 1);
  Atomics.notify(state, 0);
  bytes += chunk.length;
  if (bytes > options.maxBuffer) {
    stopped = "ENOBUFS";
    child.kill("SIGTERM");
  }
}
child.stdout.on("data", (chunk) => collect("stdout", chunk));
child.stderr.on("data", (chunk) => collect("stderr", chunk));
child.on("error", (error) => {
  failure = { code: error.code, message: error.message };
});
child.stdin.on("error", (error) => {
  failure ??= { code: error.code, message: error.message };
});
child.on("close", (status, signal) => {
  clearTimeout(timer);
  // The limit that stopped the process takes precedence over an incidental
  // broken stdin pipe, as the synchronous process API does.
  if (stopped) failure = { code: stopped };
  port.postMessage({
    pid: child.pid,
    status,
    signal,
    error: failure,
  });
  Atomics.add(state, 0, 1);
  Atomics.notify(state, 0);
  port.close();
});
child.stdin.end(options.input);
