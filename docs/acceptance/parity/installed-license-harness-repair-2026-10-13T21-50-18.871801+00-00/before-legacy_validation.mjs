/** Complete frozen-output checks through a copied native SDK/executable. */
import assert from "node:assert/strict";
import {
  readFileSync,
  writeFileSync,
  appendFileSync,
  mkdirSync,
  mkdtempSync,
  cpSync,
  constants,
  readdirSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { resolve, dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { platform, arch } from "node:os";
import { ensureGuarded } from "./storage_guard.mjs";

const supervision = await ensureGuarded();

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const binary = resolve(process.argv[2] ?? join(root, "target/debug/patamaps"));
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(
  root,
  "docs/acceptance/parity",
  `legacy-validation-${stamp}`,
);
mkdirSync(output, { recursive: true });
const base = join(root, ".tools/parity/runs");
mkdirSync(base, { recursive: true });
const stage = mkdtempSync(join(base, "installed-validation-"));
const copy = {
  recursive: true,
  force: false,
  errorOnExist: true,
  mode: constants.COPYFILE_FICLONE,
};
const sdk = join(stage, "node_modules/patamaps-native-sdk-draft");
cpSync(join(root, "sdk/typescript"), sdk, copy);
cpSync(join(root, "LICENSE"), join(sdk, "LICENSE"), copy);
cpSync(join(root, "NOTICE"), join(sdk, "NOTICE"), copy);
const installed = join(stage, "patamaps");
cpSync(binary, installed, copy);
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const corpusPath = join(
  root,
  "fixtures/parity/legacy-validation-controls.json",
);
const raw = readFileSync(corpusPath);
const corpus = JSON.parse(raw);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
for (const file of corpus.sourceFiles)
  assert.equal(sha(readFileSync(join(oracle, file.path))), file.digest);
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(sdk, "legacy-validation.mjs"))
);
const executions = join(output, "native-executions.ndjson");
let currentCase,
  calls = 0;
const api = createLegacyValidationApi(installed, (execution) => {
  calls++;
  appendFileSync(
    executions,
    JSON.stringify({ caseName: currentCase, ...execution }) + "\n",
  );
  assert.equal(execution.command[0], installed);
  assert.equal(execution.exitCode, 0);
  assert.equal(execution.signal, null);
  assert.equal(execution.processError, null);
});
const results = [];
let failure;
try {
  for (const row of corpus.cases) {
    currentCase = row.name;
    const before = JSON.stringify(row.document);
    const shape = api.validateLegacyDocumentShape(row.document);
    const semantic = api.validateLegacyDocument(
      row.document,
      row.nativePacks === undefined ? {} : { nativePacks: row.nativePacks },
    );
    assert.deepEqual(shape, row.expectedShape, `shape ${row.name}`);
    assert.deepEqual(
      semantic,
      row.expectedValidation,
      `validation ${row.name}`,
    );
    assert.equal(JSON.stringify(row.document), before);
    results.push({
      name: row.name,
      status: "passed",
      shapeDigest: sha(JSON.stringify(shape)),
      validationDigest: sha(JSON.stringify(semantic)),
    });
  }
} catch (error) {
  failure = {
    caseName: currentCase,
    message: error.message,
    stack: error.stack,
  };
}
assert.equal(sha(readFileSync(installed)), sha(readFileSync(binary)));
function files(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) =>
      entry.isDirectory()
        ? files(join(directory, entry.name))
        : [join(directory, entry.name)],
    )
    .sort();
}
const receipt = {
  schemaVersion: "1.0.0",
  status: failure ? "failed" : "passed",
  timestamp: stamp,
  supervision,
  reference: {
    engine: corpus.referenceEngine,
    corpus: relative(root, corpusPath),
    corpusDigest: sha(raw),
    sourceFiles: corpus.sourceFiles,
  },
  candidate: {
    binaryDigest: sha(readFileSync(binary)),
    engine: JSON.parse(execFileSync(installed, ["engine"], { env: {} })),
    sdkSourceInventory: files(join(root, "sdk/typescript")).map((path) => ({
      path: relative(root, path),
      digest: sha(readFileSync(path)),
    })),
  },
  host: { platform: platform(), architecture: arch(), node: process.version },
  retainedStage: relative(root, stage),
  nativeExecutions: calls,
  comparedCases: results.length,
  totalCases: corpus.cases.length,
  results,
  failure: failure ?? null,
  traceDigest: sha(readFileSync(executions)),
  scope:
    corpus.scope +
    " All diagnostic fields, key presence and array ordering are compared through the copied SDK. This component check does not close other public exports, pack import, registry, configuration, Linux or full parity obligations.",
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    receipt: relative(root, join(output, "receipt.json")),
    comparedCases: receipt.comparedCases,
    nativeExecutions: calls,
  }),
);
assert.equal(failure, undefined);
assert.equal(calls, 2 * corpus.cases.length);
