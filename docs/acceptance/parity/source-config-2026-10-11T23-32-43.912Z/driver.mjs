/** Observe the complete pinned source-config function against the native API. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve, join, dirname, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { platform, arch } from "node:os";
import {
  createSssomApi,
  SSSOM_BUILTIN_PREFIXES,
  SSSOM_PROPAGATABLE_SLOTS,
} from "../../sdk/typescript/sssom.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const cli = join(root, "target/debug/patamaps");
const oracle = join(
  root,
  JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")))
    .source,
);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
function verifyTree() {
  for (const file of supplement.referenceTree) {
    const raw = readFileSync(join(oracle, file.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${raw.length}\0`)
        .update(raw)
        .digest("hex"),
      file.gitBlob,
    );
  }
}
verifyTree();
const reference = await import(pathToFileURL(join(oracle, "dist/sssom.js")));
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(root, "docs/acceptance/parity", `source-config-${stamp}`);
mkdirSync(output, { recursive: true });
const vectorsPath = join(
  root,
  "fixtures/parity/sssom-source-config-cases.json",
);
const vectors = JSON.parse(readFileSync(vectorsPath));
const executions = [];
const api = createSssomApi(cli, (execution) => executions.push(execution));
function frozen(value) {
  return (
    value === null ||
    typeof value !== "object" ||
    (Object.isFrozen(value) && Object.values(value).every(frozen))
  );
}
function observe(fn, value) {
  try {
    const result = fn(value);
    return {
      status: "accepted",
      value: result,
      recursivelyFrozen: frozen(result),
      fresh: result !== value,
    };
  } catch (error) {
    return {
      status: "refused",
      error: {
        name: error.name,
        code: error.code ?? null,
        message: error.message,
      },
    };
  }
}
const results = vectors.cases.map(({ name, value }) => ({
  name,
  input: value,
  reference: observe(reference.parseSssomSourceConfig, value),
  candidate: observe(api.parseSssomSourceConfig, value),
}));

// These JavaScript values cannot survive JSON transport. The marshaller must
// reproduce their original refusal without evaluating accessors or hooks.
const unsafe = [];
const base = vectors.cases[0].value;
unsafe.push(
  ["undefined", undefined],
  ["nan", NaN],
  ["infinity", Infinity],
  ["bigint", 1n],
  ["unpaired-surrogate", { ...base, id: "\ud800" }],
  ["sparse-array", [, 1]],
  ["prototype", new Date(0)],
);
const cycle = { ...base };
cycle.provenance = cycle;
unsafe.push(["cycle", cycle]);
const symbol = { ...base };
symbol[Symbol("hidden")] = true;
unsafe.push(["symbol", symbol]);
const hidden = { ...base };
Object.defineProperty(hidden, "hidden", { value: true });
unsafe.push(["nonenumerable", hidden]);
let accessorCalls = 0;
const accessor = { ...base };
Object.defineProperty(accessor, "path", {
  get() {
    accessorCalls++;
    return "input";
  },
  enumerable: true,
});
unsafe.push(
  ["accessor", accessor],
  [
    "to-json-hook",
    {
      ...base,
      toJSON() {
        accessorCalls++;
        return base;
      },
    },
  ],
);
for (const [name, value] of unsafe) {
  results.push({
    name,
    input: "JavaScript-only value; constructed in the retained driver",
    reference: observe(reference.parseSssomSourceConfig, value),
    candidate: observe(api.parseSssomSourceConfig, value),
  });
}
const differences = results.filter((row) => {
  try {
    assert.deepEqual(row.candidate, row.reference);
    return false;
  } catch {
    return true;
  }
});
let profileEqual = true;
try {
  assert.deepEqual(SSSOM_BUILTIN_PREFIXES, reference.SSSOM_BUILTIN_PREFIXES);
  assert.deepEqual(
    Object.keys(SSSOM_BUILTIN_PREFIXES),
    Object.keys(reference.SSSOM_BUILTIN_PREFIXES),
  );
  assert.deepEqual(
    SSSOM_PROPAGATABLE_SLOTS,
    reference.SSSOM_PROPAGATABLE_SLOTS,
  );
  assert(
    Object.isFrozen(SSSOM_BUILTIN_PREFIXES) &&
      Object.isFrozen(SSSOM_PROPAGATABLE_SLOTS),
  );
} catch {
  profileEqual = false;
}
verifyTree();
const engine = JSON.parse(execFileSync(cli, ["engine"], { encoding: "utf8" }));
writeFileSync(
  join(output, "observations.json"),
  JSON.stringify({ results, profileEqual, accessorCalls }, null, 2) + "\n",
);
writeFileSync(
  join(output, "native-executions.ndjson"),
  executions.map((row) => JSON.stringify(row)).join("\n") + "\n",
);
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
);
writeFileSync(join(output, "inputs.json"), readFileSync(vectorsPath));
const sdk = [
  "sssom.mjs",
  "sssom.d.ts",
  "sssom-profile.mjs",
  "canonical.mjs",
  "canonical.d.ts",
];
const receipt = {
  schemaVersion: "1.0.0",
  status:
    differences.length === 0 && profileEqual && accessorCalls === 0
      ? "passed"
      : "failed",
  reference: {
    engine: supplement.referenceEngine,
    originalTreeFilesVerified: supplement.referenceTree.length,
    compiledModuleDigest: sha(readFileSync(join(oracle, "dist/sssom.js"))),
  },
  candidate: {
    binaryDigest: sha(readFileSync(cli)),
    engine,
    sdkSourceInventory: sdk.map((name) => ({
      path: `sdk/typescript/${name}`,
      digest: sha(readFileSync(join(root, "sdk/typescript", name))),
    })),
  },
  host: { platform: platform(), architecture: arch() },
  counts: {
    declaredSchemaInputs: vectors.cases.length,
    javascriptOnlyInputs: unsafe.length,
    nativeExecutions: executions.length,
    differences: differences.length,
  },
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
  inputsDigest: sha(readFileSync(vectorsPath)),
  artifacts: [
    "driver.mjs",
    "inputs.json",
    "observations.json",
    "native-executions.ndjson",
  ].map((name) => ({
    path: name,
    digest: sha(readFileSync(join(output, name))),
  })),
  scope:
    "Source-config component return values, fresh immutable results, complete refusal diagnostics, unsafe-JavaScript marshalling and public constant values/order. This closes zero original cases and does not establish full workspace config or adapter parity.",
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
      ...receipt.counts,
      profileEqual,
      accessorCalls,
      differences: differences.map(({ name, reference, candidate }) => ({
        name,
        reference,
        candidate,
      })),
    },
    null,
    2,
  ),
);
process.exitCode = receipt.status === "passed" ? 0 : 1;
