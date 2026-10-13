import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync } from "node:fs";
import { createHash } from "node:crypto";
import { spawnSync, execFileSync } from "node:child_process";
import { join, resolve, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createCanonicalApi } from "../../sdk/typescript/canonical.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const cli = resolve(process.argv[2] ?? join(root, "target/debug/patamaps"));
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const rules = readFileSync(
  join(root, "fixtures/parity/json-observable-rules.json"),
);
const base = join(root, ".tools/parity/runs");
mkdirSync(base, { recursive: true });
const retained = mkdtempSync(join(base, "json-observables-"));
const output = join(
  root,
  "docs/acceptance/parity",
  `json-observables-${new Date().toISOString().replaceAll(":", "-")}`,
);
mkdirSync(output, { recursive: true });
const cases = [
  ["property-order", '{"z":1,"a":2}'],
  ["prototype-property", '{"__proto__":{"admin":true},"a":0}'],
  ["decoded-duplicate", '{"a":1,"\\u0061":2}'],
  ["syntax-before-duplicate", '{"a":1,"a":2,}'],
  ["duplicate-before-nonfinite", '{"a":1e999,"a":2}'],
  ["duplicate-before-unicode", '{"a":"\\ud800","a":2}'],
  ["surrogate-key-duplicate", '{"\\ud800":1,"\\ud800":2}'],
  ["escaped-nonbmp-duplicate", '{"😀":1,"\\ud83d\\ude00":2}'],
  ["literal-unpaired-surrogate", '"\ud800"'],
  ["syntax-before-literal-unicode", '["\ud800",]'],
  ["nonfinite-number", '{"n":1e999}'],
  ...[65, 512, 513].map((depth) => [
    `depth-${depth}`,
    "[".repeat(depth) + "0" + "]".repeat(depth),
  ]),
];
const records = [];
for (const [name, text] of cases) {
  const input = join(retained, `${name}.json`);
  const inputBytes = JSON.stringify({ text });
  writeFileSync(input, inputBytes);
  writeFileSync(join(output, `${name}.input.json`), inputBytes);
  const command = [
    process.execPath,
    join(root, "scripts/parity/reference_json.mjs"),
    join(root, pointer.source),
    input,
  ];
  const reference = spawnSync(command[0], command.slice(1), {
    encoding: "utf8",
    timeout: 30_000,
    maxBuffer: 2 * 1024 * 1024,
  });
  assert.equal(reference.status, 0, reference.stderr);
  const old = JSON.parse(reference.stdout);
  const executions = [];
  const api = createCanonicalApi(cli, (execution) =>
    executions.push(execution),
  );
  let candidate;
  try {
    const value = api.parseStrictJson(text);
    candidate = {
      status: "accepted",
      canonical: api.canonicalJson(value),
      ownKeys:
        value !== null && typeof value === "object" ? Object.keys(value) : null,
    };
  } catch (error) {
    candidate = {
      status: "refused",
      error: {
        name: error.name,
        code: error.code ?? null,
        message: error.message,
      },
    };
  }
  const equal = JSON.stringify(old) === JSON.stringify(candidate);
  writeFileSync(join(output, `${name}.reference.stdout`), reference.stdout);
  writeFileSync(join(output, `${name}.reference.stderr`), reference.stderr);
  writeFileSync(
    join(output, `${name}.candidate-native.json`),
    JSON.stringify(executions, null, 2) + "\n",
  );
  records.push({
    name,
    inputDigest: sha(inputBytes),
    referenceCommand: command,
    referenceExitCode: reference.status,
    reference: old,
    candidate,
    equal,
  });
}
const receipt = {
  schemaVersion: "1.0.0",
  status: records.every((row) => row.equal) ? "passed" : "differences-observed",
  rulesDigest: sha(rules),
  referenceEngine: "399747a4ad05a37cd8db1cedd53048fad2175be4",
  candidate: {
    binaryDigest: sha(readFileSync(cli)),
    engine: JSON.parse(execFileSync(cli, ["engine"])),
    facadeDigest: sha(readFileSync(join(root, "sdk/typescript/canonical.mjs"))),
  },
  records,
  originalCasesClosed: 0,
  retainedRun: relative(root, retained),
  cleanup: "No deletion",
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
console.log(
  JSON.stringify(
    {
      status: receipt.status,
      receipt: relative(root, join(output, "receipt.json")),
      total: records.length,
      differences: records
        .filter((row) => !row.equal)
        .map((row) => ({
          name: row.name,
          reference: row.reference,
          candidate: row.candidate,
        })),
    },
    null,
    2,
  ),
);
process.exitCode = records.every((row) => row.equal) ? 0 : 1;
