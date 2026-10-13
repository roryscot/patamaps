/** Execute the unchanged original assertions against the native-backed facade. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  mkdtempSync,
  cpSync,
  constants,
  readdirSync,
} from "node:fs";
import { spawnSync, execFileSync } from "node:child_process";
import { resolve, join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { platform, arch } from "node:os";
import { ensureGuarded } from "./storage_guard.mjs";

const supervision = await ensureGuarded();

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const cli = resolve(
  process.argv.slice(2).find((argument) => !argument.startsWith("--")) ??
    join(root, "target/debug/patamaps"),
);
const mode = process.argv.includes("--validation")
  ? "validation"
  : process.argv.includes("--discovery")
    ? "discovery"
    : process.argv.includes("--sssom-adapter")
      ? "sssom-adapter"
      : process.argv.includes("--sssom")
        ? "sssom"
        : "canonical";
const scientificAdapter = mode === "sssom-adapter";
const scientific = mode === "sssom" || scientificAdapter;
const discovery = mode === "discovery";
const validation = mode === "validation";
const installProviders = discovery || scientificAdapter;
const selectionPath = scientificAdapter
  ? "fixtures/parity/sssom-adapter-selected-cases.json"
  : scientific
    ? "fixtures/parity/sssom-selected-cases.json"
    : discovery
      ? "fixtures/parity/discovery-selected-cases.json"
      : null;
const selection = selectionPath
  ? JSON.parse(readFileSync(join(root, selectionPath)))
  : null;
const suitePath = validation
  ? "src/__tests__/validator.test.ts"
  : (selection?.suite ?? "src/__tests__/canonical.test.ts");
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const manifestRaw = readFileSync(join(root, "fixtures/parity/manifest.json"));
const manifest = JSON.parse(manifestRaw);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const source = join(root, pointer.source);
function verifyTree() {
  for (const file of supplement.referenceTree) {
    const raw = readFileSync(join(source, file.path));
    const blob = createHash("sha1")
      .update(`blob ${raw.length}\0`)
      .update(raw)
      .digest("hex");
    assert.equal(blob, file.gitBlob, `Pinned source changed: ${file.path}`);
  }
}
verifyTree();
const base = join(root, ".tools/parity/runs");
mkdirSync(base, { recursive: true });
const run = mkdtempSync(join(base, `original-${mode}-`));
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(
  root,
  "docs/acceptance/parity",
  `original-${mode}-${stamp}`,
);
mkdirSync(output, { recursive: true });
const traceName = discovery
  ? "fact-executions.ndjson"
  : "native-executions.ndjson";
const trace = join(run, traceName);
const factTrace = discovery ? trace : join(run, "fact-executions.ndjson");
const setup = join(run, "setup.mjs");
const facade = join(root, "sdk/typescript/canonical.mjs");
const science = join(root, "sdk/typescript/sssom.mjs");
const legacy = join(root, "sdk/typescript/legacy-validation.mjs");
function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? sourceFiles(path) : [path];
    })
    .sort();
}
let provider = null;
let providerPlugin = "";
let providerInventory = [];
let toolingRecord = null;
let installedPackages = [];
if (installProviders) {
  provider = join(run, "installed/node_modules/patamaps-discovery-draft");
  const tooling = join(run, "installed/node_modules/typescript");
  const copyOptions = {
    recursive: true,
    force: false,
    errorOnExist: true,
    mode: constants.COPYFILE_FICLONE,
  };
  cpSync(join(root, "adapters/discovery"), provider, copyOptions);
  cpSync(
    join(root, "sdk/typescript"),
    join(run, "installed/node_modules/patamaps-native-sdk-draft"),
    copyOptions,
  );
  const toolingRaw = readFileSync(
    join(root, "fixtures/parity/discovery-tooling.json"),
  );
  const toolingSpec = JSON.parse(toolingRaw);
  assert.equal(
    sha(readFileSync(join(source, "package-lock.json"))),
    toolingSpec.referenceLockDigest,
  );
  for (const item of toolingSpec.packages) {
    const origin = join(source, "node_modules", item.name);
    const target = join(run, "installed/node_modules", item.name);
    assert.equal(
      JSON.parse(readFileSync(join(origin, "package.json"))).version,
      item.version,
    );
    assert.deepEqual(
      sourceFiles(origin).map((path) => relative(origin, path)),
      item.files.map((file) => file.path),
    );
    for (const file of item.files)
      assert.equal(sha(readFileSync(join(origin, file.path))), file.digest);
    cpSync(origin, target, copyOptions);
    assert.deepEqual(
      sourceFiles(target).map((path) => relative(target, path)),
      item.files.map((file) => file.path),
    );
    for (const file of item.files)
      assert.equal(sha(readFileSync(join(target, file.path))), file.digest);
  }
  toolingRecord = {
    manifest: "fixtures/parity/discovery-tooling.json",
    digest: sha(toolingRaw),
    packages: toolingSpec.packages.map(({ name, version }) => ({
      name,
      version,
    })),
  };
  installedPackages = [
    "patamaps-discovery-draft",
    "patamaps-native-sdk-draft",
    ...toolingSpec.packages.map((item) => item.name),
  ].sort();
  assert.equal(
    JSON.parse(readFileSync(join(tooling, "package.json"))).version,
    "5.9.3",
  );
  assert.deepEqual(
    readdirSync(join(run, "installed/node_modules")).sort(),
    installedPackages,
  );
  providerInventory = sourceFiles(join(root, "adapters/discovery"));
  const observerFacade = join(run, "observed-providers.mjs");
  writeFileSync(
    observerFacade,
    `
import * as library from ${JSON.stringify(join(provider, "index.mjs"))};
import {appendFileSync,readFileSync} from 'node:fs';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {expect} from ${JSON.stringify(join(source, "node_modules/vitest/dist/index.js"))};
const sha=raw=>'sha256:'+createHash('sha256').update(raw).digest('hex');
function observed(Adapter,className){return class extends Adapter{async discover(...args){
  const value=await super.discover(...args);
  const inputs=value.inputs.map(input=>{const raw=readFileSync(join(args[1].repositoryRoot,input.path));return {path:input.path,digest:sha(raw),byteLength:raw.length,content:raw.toString('utf8')};});
  appendFileSync(${JSON.stringify(factTrace)},JSON.stringify({caseName:expect.getState().currentTestName,className,method:'discover',arguments:args,inputs,result:value})+'\\n');
  return value;
}};}
export const PrismaAdapter=observed(library.PrismaAdapter,'PrismaAdapter');
export const TypeScriptZodAdapter=observed(library.TypeScriptZodAdapter,'TypeScriptZodAdapter');
export const JsonCollectionsAdapter=observed(library.JsonCollectionsAdapter,'JsonCollectionsAdapter');
export const SssomTsvAdapter=observed(library.SssomTsvAdapter,'SssomTsvAdapter');
`,
  );

  providerPlugin = `{name:'installed-discovery-original-case',enforce:'pre',resolveId(specifier,importer){if(importer?.endsWith('/${selection.suite}') && Object.hasOwn(${JSON.stringify(selection.moduleBindings)},specifier))return ${JSON.stringify(observerFacade)};}}`;
  mkdirSync(join(run, "tmp"));
  writeFileSync(
    join(run, "installed/package.json"),
    JSON.stringify({ type: "module" }),
  );
}
const observer = `execution=>appendFileSync(${JSON.stringify(trace)},JSON.stringify({caseName:expect.getState().currentTestName,...execution})+'\\n')`;
const scienceSetup = scientific
  ? `import {configureSssom} from ${JSON.stringify(science)}; configureSssom(${JSON.stringify(cli)},${observer});\n`
  : "";
const sciencePlugin = scientific
  ? `{name:'native-sssom-original-case',enforce:'pre',resolveId(specifier,importer){if(specifier.endsWith('/sssom.js') && importer?.startsWith(${JSON.stringify(source)}))return ${JSON.stringify(science)};}}`
  : "";
const validationFacade = join(run, "validator-facade.mjs");
if (validation)
  writeFileSync(
    validationFacade,
    `export {validateLegacyDocument as validateMetamapDocument, validateLegacyDocumentShape as validateDocumentShape} from ${JSON.stringify(legacy)};\n`,
  );
const validationPlugin = validation
  ? `{name:'native-validation-original-case',enforce:'pre',resolveId(specifier,importer){if(specifier.endsWith('/validator.js') && importer?.startsWith(${JSON.stringify(source)}))return ${JSON.stringify(validationFacade)};}}`
  : "";
const validationSetup = validation
  ? `import {configureLegacyValidation} from ${JSON.stringify(legacy)}; configureLegacyValidation(${JSON.stringify(cli)},${observer});\n`
  : "";
writeFileSync(
  setup,
  `${scienceSetup}${validationSetup}${scientificAdapter ? `import {configureDiscoveryNative} from ${JSON.stringify(join(provider, "index.mjs"))};configureDiscoveryNative(${JSON.stringify(cli)},${observer});\n` : ""}import { configureCanonical } from ${JSON.stringify(facade)};\nimport { expect } from ${JSON.stringify(join(source, "node_modules/vitest/dist/index.js"))};\nimport { appendFileSync } from 'node:fs';\nconfigureCanonical(${JSON.stringify(cli)},execution=>appendFileSync(${JSON.stringify(trace)},JSON.stringify({caseName:expect.getState().currentTestName,...execution})+'\\n'));\n`,
);
const config = join(run, "vitest.config.mjs");
writeFileSync(
  config,
  `export default { root:${JSON.stringify(source)}, cacheDir:${JSON.stringify(join(run, "vite-cache"))}, plugins:[${[sciencePlugin, providerPlugin, validationPlugin].filter(Boolean).join(",")}], resolve:{alias:[{find:/.*canonical\\.js$/,replacement:${JSON.stringify(facade)}}]}, test:{include:[${JSON.stringify(suitePath)}], setupFiles:[${JSON.stringify(setup)}], maxWorkers:1} };\n`,
);
const reportPath = join(run, "vitest.json");
const command = [
  process.execPath,
  join(source, "node_modules/vitest/vitest.mjs"),
  "run",
  "--config",
  config,
  "--reporter=default",
  "--reporter=json",
  "--outputFile",
  reportPath,
];
if (selection) command.push("--testNamePattern", selection.testNamePattern);
const result = spawnSync(command[0], command.slice(1), {
  cwd: source,
  encoding: "utf8",
  timeout: 120_000,
  maxBuffer: 8 * 1024 * 1024,
  env: {
    ...process.env,
    CI: "true",
    ...(installProviders ? { TMPDIR: join(run, "tmp") } : {}),
    NODE_OPTIONS: `--require ${join(root, "scripts/parity/retain.cjs")}`,
    PATAMAPS_RETAIN_ALLOWED: JSON.stringify([run, source]),
    PATAMAPS_RETAIN_ARCHIVE: join(run, "retained-cleanup"),
  },
});
writeFileSync(join(output, "stdout.log"), result.stdout ?? "");
writeFileSync(join(output, "stderr.log"), result.stderr ?? "");
verifyTree();
const report = JSON.parse(readFileSync(reportPath));
writeFileSync(join(output, "vitest.json"), readFileSync(reportPath));
const executions = readFileSync(trace, "utf8")
  .trim()
  .split("\n")
  .map((line) => JSON.parse(line));
writeFileSync(join(output, traceName), readFileSync(trace));
const cases = manifest.obligations.filter(
  (row) => row.kind === "reference-test-case" && row.origin.path === suitePath,
);
const observed = report.testResults.flatMap((suite) => suite.assertionResults);
assert.equal(
  observed.length,
  cases.length,
  "No original expanded case may be omitted",
);
const occurrences = new Map();
const allOutcomes = observed.map((test) => {
  const occurrence = occurrences.get(test.fullName) ?? 0;
  occurrences.set(test.fullName, occurrence + 1);
  const original = cases.find(
    (row) =>
      row.name === test.fullName && row.inputIdentity.occurrence === occurrence,
  );
  assert(original, `Uninventoried case: ${test.fullName}`);
  return {
    id: original.id,
    scope: "complete-original-case",
    status:
      test.status === "passed"
        ? "verified-equivalent"
        : ["pending", "skipped"].includes(test.status)
          ? "unselected"
          : "failed",
    origin: original.origin,
    expectationDigest: original.expectation.callbackDigest,
    fullName: test.fullName,
    occurrence,
    candidateExecution: discovery
      ? "Original pure fact-discovery assertions; installed licensed provider code and pinned TypeScript tooling, with no MetaMap runtime package. Native admission is verified by the separate installed-host component receipt."
      : validation
        ? "Original JSON graph validation assertions; Rust-native read-only legacy shape and semantic diagnostics using the original core pack identity"
        : scientific
          ? "Original scientific assertions; Rust-native parsing, model validation, interpretation, export and CURIE expansion; host marshalling and immutable results"
          : "Original assertions, Rust-native canonical/parse/digest operations, JavaScript-only marshalling refusals for untransportable values",
  };
});
const selectedIds = new Set(
  selection?.selectedCaseIds ?? cases.map((row) => row.id),
);
const obligations = allOutcomes.filter((row) => selectedIds.has(row.id));
assert.equal(obligations.length, selectedIds.size);
assert(
  allOutcomes
    .filter((row) => !selectedIds.has(row.id))
    .every((row) => row.status === "unselected"),
  "Unselected cases must never be presented as candidate execution",
);
assert(
  obligations.every((row) => row.status !== "unselected"),
  "Every selected original case must execute",
);
if (!discovery) {
  assert(
    executions.some((row) =>
      validation
        ? row.command.slice(1, 4).join(" ") === "legacy json validate"
        : scientific
          ? row.command.slice(1, 3).join(" ") === "sssom json"
          : row.command[2] === "digest",
    ),
    "The tested operation must execute Rust",
  );
  assert(
    executions.every(
      (row) => row.command[0] === cli && !row.processError && !row.signal,
    ),
    "Every recorded operation used the actual selected native executable",
  );
}
const receipt = {
  schemaVersion: "1.0.0",
  driver: mode,
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
  supervision,
  selection: selection
    ? {
        path: selectionPath,
        digest: sha(readFileSync(join(root, selectionPath))),
        ...selection,
      }
    : null,
  timestamp: stamp,
  status: result.status === 0 && report.success ? "passed" : "failed",
  command,
  exitCode: result.status,
  signal: result.signal,
  error: result.error?.message ?? null,
  manifestDigest: sha(manifestRaw),
  comparisonRulesDigest: sha(
    readFileSync(join(root, "fixtures/parity/comparison-rules.json")),
  ),
  reference: {
    engine: manifest.reference.engine,
    caseOrigin: "Unchanged pinned original source/assertions",
    operationsRerun: false,
    testsRerun: false,
    referenceObservation:
      "docs/acceptance/full-reference/reference-vitest.json",
  },
  candidate: {
    binary: relative(root, cli),
    binaryDigest: sha(readFileSync(cli)),
    engine: JSON.parse(execFileSync(cli, ["engine"])),
    sdkSourceInventory: [
      ...(installProviders
        ? providerInventory
        : [facade, join(root, "sdk/typescript/canonical.d.ts")]),
      ...(scientific || installProviders || validation
        ? sourceFiles(join(root, "sdk/typescript"))
        : []),
    ].map((path) => ({
      path: relative(root, path),
      digest: sha(readFileSync(path)),
    })),
    facadeDigest: sha(readFileSync(facade)),
    facadeDeclarationDigest: sha(
      readFileSync(join(root, "sdk/typescript/canonical.d.ts")),
    ),
  },
  host: { platform: platform(), architecture: arch(), node: process.version },
  counts: {
    originalCases: obligations.length,
    passed: report.numPassedTests,
    failed: report.numFailedTests,
    skipped: obligations.filter((row) => row.status === "unselected").length,
    explicitlyUnselected: allOutcomes.length - obligations.length,
    nativeExecutions: discovery ? 0 : executions.length,
    ...(discovery ? { factExecutions: executions.length } : {}),
  },
  assertions: validation
    ? "All seven original callbacks, inputs and expectations remain unchanged. Only validator function imports are mapped to the Rust-backed read-only legacy JSON facade; no reference semantic implementation is executed by the candidate."
    : selection
      ? selection.scope
      : "Original assertions and parameter values are unchanged. Canonical module imports alone are mapped to the Patamaps facade; original stable digest utilities compute independent expected values.",
  obligations,
  originalTreeFilesVerified: supplement.referenceTree.length,
  retainedRun: relative(root, run),
  cleanup:
    "Any explicit Node cleanup within owned roots is retained by rename; deletion outside those roots is refused",
};
if (installProviders) {
  receipt.installedProvider = {
    path: relative(root, provider),
    packages: installedPackages,
    tooling: toolingRecord,
    typescriptVersion: "5.9.3",
    observerPath: relative(root, join(run, "observed-providers.mjs")),
    observerDigest: sha(readFileSync(join(run, "observed-providers.mjs"))),
    inventory: providerInventory.map((path) => ({
      path: relative(join(root, "adapters/discovery"), path),
      digest: sha(readFileSync(path)),
    })),
    sdkInventory: sourceFiles(join(root, "sdk/typescript")).map((path) => ({
      path: relative(join(root, "sdk/typescript"), path),
      digest: sha(readFileSync(path)),
    })),
  };
  if (discovery) {
    assert.equal(executions.length, 3);
    assert.deepEqual(executions.map((row) => row.className).sort(), [
      "JsonCollectionsAdapter",
      "PrismaAdapter",
      "TypeScriptZodAdapter",
    ]);
  }
  if (scientificAdapter) {
    writeFileSync(
      join(output, "fact-executions.ndjson"),
      readFileSync(factTrace),
    );
    receipt.counts.factExecutions = readFileSync(factTrace, "utf8")
      .trim()
      .split("\n").length;
  }
}
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
  { flag: "wx" },
);
console.log(
  JSON.stringify(
    {
      status: receipt.status,
      receipt: relative(root, join(output, "receipt.json")),
      ...receipt.counts,
    },
    null,
    2,
  ),
);
assert.equal(result.status, 0, result.stdout + result.stderr);
assert(report.success);
assert.equal(report.numPendingTests, allOutcomes.length - obligations.length);
