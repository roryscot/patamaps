/** Real-process canonical probes, retaining every input and both raw outcomes. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync, execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync } from "node:fs";
import { dirname, resolve, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { hostname, platform, arch } from "node:os";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const cli = resolve(process.argv[2] ?? join(root, "target/release/patamaps"));
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const source = join(root, pointer.source);
const manifestBytes = readFileSync(join(root, "fixtures/parity/manifest.json"));
const manifest = JSON.parse(manifestBytes);
const rulesBytes = readFileSync(
  join(root, "fixtures/parity/comparison-rules.json"),
);
const sha = (data) =>
  "sha256:" + createHash("sha256").update(data).digest("hex");
const path = (file) => relative(root, file);
const timestamp = new Date().toISOString().replaceAll(":", "-");
const base = join(root, ".tools/parity/runs");
mkdirSync(base, { recursive: true });
const retained = mkdtempSync(join(base, "canonical-"));
const out = join(root, "docs/acceptance/parity", `canonical-${timestamp}`);
mkdirSync(out, { recursive: true });
const engine = JSON.parse(execFileSync(cli, ["engine"]));
const canonicalOrigins = (title) =>
  manifest.obligations
    .filter(
      (row) =>
        row.kind === "reference-test-case" &&
        row.origin.path === "src/__tests__/canonical.test.ts" &&
        row.name.includes(title),
    )
    .map((row) => row.id);
const probes = [];
const add = (name, input, title, rule = "canonical-utf8-exact") =>
  probes.push({
    name,
    input,
    originalObligations: canonicalOrigins(title),
    rule,
    coverage:
      "Component probe; original test case is not claimed closed by this probe.",
  });
add(
  "normative-unicode",
  '{"€":1,"\\r":2,"דּ":3,"1":4,"😀":5,"\\u0080":6,"ö":7,"a":[3,2,1]}',
  "normative UTF-16",
);
add("composed-unicode", '{"value":"é"}', "normative UTF-16");
add("decomposed-unicode", '{"value":"e\\u0301"}', "normative UTF-16");
add(
  "normative-numbers",
  "[333333333.33333329,1e30,4.5,2e-3,1e-27,-0]",
  "RFC numerical",
);
for (const bits of [
  "0000000000000001",
  "8000000000000001",
  "7fefffffffffffff",
  "ffefffffffffffff",
  "4340000000000000",
  "4430000000000000",
  "44b52d02c7e14af5",
  "44b52d02c7e14af6",
  "44b52d02c7e14af7",
  "3eb0c6f7a0b5ed8c",
  "3eb0c6f7a0b5ed8d",
]) {
  add(
    `binary64-${bits}`,
    JSON.stringify(Buffer.from(bits, "hex").readDoubleBE()),
    "RFC numerical",
  );
}
add(
  "prototype-key",
  '{"__proto__":{"admin":true},"x":"\\\""}',
  "prototype-like keys",
);
for (const depth of [64, 65, 128, 512, 513, 514]) {
  add(
    `depth-${depth}`,
    "[".repeat(depth) + "0" + "]".repeat(depth),
    "prototype-like keys",
    "accepted-domain-exact",
  );
}
for (const [index, input] of [
  '{"a":1,"a":2}',
  '{"a":1,"\\u0061":2}',
  '{"nested":{"x":1,"x":2}}',
  '[{"x":1,"x":2}]',
].entries()) {
  add(
    `decoded-duplicate-${index}`,
    input,
    "decoded duplicate keys",
    "strict-json-refusal",
  );
}
add(
  "nonfinite-number",
  '{"x":1e999}',
  "prototype-like keys",
  "strict-json-refusal",
);
add("trailing-comma", '{"x":1,}', "prototype-like keys", "strict-json-refusal");

const records = [];
function run(program, args) {
  const result = spawnSync(program, args, {
    cwd: root,
    encoding: null,
    timeout: 30_000,
    maxBuffer: 2 * 1024 * 1024,
  });
  return {
    command: [program, ...args],
    exitCode: result.status,
    signal: result.signal,
    error: result.error?.message ?? null,
    stdout: result.stdout ?? Buffer.alloc(0),
    stderr: result.stderr ?? Buffer.alloc(0),
  };
}
for (const [index, probe] of probes.entries()) {
  const name = `${String(index).padStart(2, "0")}-${probe.name}`;
  const inputPath = join(retained, `${name}.json`);
  writeFileSync(inputPath, probe.input);
  const ref = run(process.execPath, [
    join(root, "scripts/parity/reference_canonical.mjs"),
    source,
    inputPath,
  ]);
  const candidate = run(cli, ["canonical", inputPath]);
  assert.equal(ref.exitCode, 0, `Oracle process failed for ${name}`);
  const expected = JSON.parse(ref.stdout);
  let result;
  if (expected.status === "accepted") {
    if (candidate.exitCode !== 0) result = "missing-capability";
    else {
      assert(
        candidate.stdout.at(-1) === 10,
        "Expected exactly one CLI framing LF",
      );
      const canonical = candidate.stdout.subarray(0, -1);
      result = canonical.equals(Buffer.from(expected.canonical))
        ? "equivalent-bytes"
        : "different-bytes";
      assert.equal(
        sha(Buffer.from(expected.canonical)),
        expected.digest,
        "Oracle digest integrity",
      );
    }
  } else
    result =
      candidate.exitCode === 0
        ? "incorrect-acceptance"
        : "equivalent-refusal-with-unresolved-diagnostics";
  const raw = {};
  for (const [side, outcome] of [
    ["reference", ref],
    ["candidate", candidate],
  ]) {
    for (const channel of ["stdout", "stderr"]) {
      const file = join(out, `${name}.${side}.${channel}`);
      writeFileSync(file, outcome[channel]);
      raw[`${side}.${channel}`] = {
        path: path(file),
        digest: sha(outcome[channel]),
      };
    }
  }
  writeFileSync(join(out, `${name}.input.json`), probe.input);
  const summary = (outcome) => ({
    command: outcome.command,
    exitCode: outcome.exitCode,
    signal: outcome.signal,
    error: outcome.error,
  });
  records.push({
    name: probe.name,
    input: {
      path: path(join(out, `${name}.input.json`)),
      digest: sha(probe.input),
    },
    originalObligations: probe.originalObligations,
    coverage: probe.coverage,
    rule: probe.rule,
    result,
    referenceOutcome: expected,
    candidateOutcome: summary(candidate),
    referenceProcess: summary(ref),
    raw,
  });
}
const failures = records.filter((row) =>
  ["missing-capability", "different-bytes", "incorrect-acceptance"].includes(
    row.result,
  ),
);
const receipt = {
  schemaVersion: "1.0.0",
  timestamp,
  status: failures.length
    ? "capability-gaps-observed"
    : "probe-capabilities-passed",
  reference: {
    engine: manifest.reference.engine,
    preparation: pointer.record,
    testsRerun: false,
    operationsRerun: true,
  },
  candidate: {
    binary: path(cli),
    binaryDigest: sha(readFileSync(cli)),
    engine,
    gitHead: execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: root,
      encoding: "utf8",
    }).trim(),
    dirty: execFileSync("git", ["status", "--porcelain"], {
      cwd: root,
      encoding: "utf8",
    }),
  },
  host: {
    platform: platform(),
    architecture: arch(),
    hostname: hostname(),
    node: process.version,
  },
  manifestDigest: sha(manifestBytes),
  comparisonRulesDigest: sha(rulesBytes),
  records,
  counts: {
    total: records.length,
    capabilityGaps: failures.length,
    unresolvedDiagnosticComparisons: records.filter(
      (row) => row.result === "equivalent-refusal-with-unresolved-diagnostics",
    ).length,
    originalCasesClosed: 0,
  },
  retainedRun: path(retained),
  cleanup:
    "No deletion; original inputs, both process outputs and isolated oracle retained",
};
writeFileSync(
  join(out, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
console.log(
  JSON.stringify(
    {
      status: receipt.status,
      receipt: path(join(out, "receipt.json")),
      ...receipt.counts,
      failures: failures.map((row) => row.name),
    },
    null,
    2,
  ),
);
process.exitCode = failures.length ? 1 : 0;
