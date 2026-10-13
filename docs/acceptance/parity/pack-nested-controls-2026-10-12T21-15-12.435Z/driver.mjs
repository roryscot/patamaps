/** Freeze original JSON pack observations before comparing the native API.
 * This component probe cannot close the full JavaScript/file/registry contract.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  appendFileSync,
  symlinkSync,
  lstatSync,
  readlinkSync,
} from "node:fs";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";

const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
function verifyTree() {
  for (const entry of supplement.referenceTree) {
    const raw = readFileSync(join(oracle, entry.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${raw.length}\0`)
        .update(raw)
        .digest("hex"),
      entry.gitBlob,
      entry.path,
    );
  }
}
verifyTree();
assert.ok(
  process.argv
    .slice(2)
    .every((argument) => ["--nested", "--files"].includes(argument)) &&
    process.argv.slice(2).length <= 1,
  "Supported options: --nested or --files",
);
const nested = process.argv.includes("--nested");
const files = process.argv.includes("--files");
const corpusName = files
  ? "pack-file-controls"
  : nested
    ? "pack-nested-controls"
    : "pack-json-controls";
const corpusPath = join(root, `fixtures/parity/${corpusName}.json`);
function errorOutcome(error) {
  const observed = { name: error.name, message: error.message };
  if (files)
    for (const field of ["code", "path", "errno", "syscall"])
      if (error[field] !== undefined) observed[field] = error[field];
  return { status: "refused", error: observed };
}
if (!existsSync(corpusPath)) {
  const original = await import(
    pathToFileURL(join(oracle, "dist/relation-pack.js"))
  );
  const cases = [];
  function add(name, value) {
    let expected;
    try {
      const parsed = original.parseRelationPack(value);
      assert.equal(parsed, value, "Original parser identity");
      expected = {
        status: "accepted",
        digest: original.relationPackDigest(parsed),
      };
    } catch (error) {
      expected = {
        status: "refused",
        error: { name: error.name, message: error.message },
      };
    }
    cases.push({ name, value, expected });
  }
  const portable = {
    schemaVersion: "1.0.0",
    id: "urn:pack:control",
    version: "1",
    relations: [{ id: "test:edge", cyclePolicy: "allow" }],
  };
  const executable = { ...portable, schemaVersion: "2.0.0", laws: [] };
  if (files) {
    const fixtureRoot = join(
      root,
      ".tools/parity/pack-file-controls",
      new Date().toISOString().replaceAll(":", "-"),
    );
    mkdirSync(fixtureRoot, { recursive: true });
    async function addFile(name, source, kind = "file") {
      const path = join(fixtureRoot, name);
      if (kind === "file") writeFileSync(path, source, { flag: "wx" });
      else if (kind === "directory") mkdirSync(path);
      else if (kind === "loop") symlinkSync(name, path);
      else if (kind === "not-directory") {
        writeFileSync(path, "regular file", { flag: "wx" });
      }
      const requestPath =
        kind === "not-directory" ? join(path, "pack.json") : path;
      let expected;
      try {
        const value = await original.loadRelationPack(requestPath);
        expected = {
          status: "accepted",
          document: value,
          digest: original.relationPackDigest(value),
        };
      } catch (error) {
        expected = errorOutcome(error);
      }
      cases.push({
        name,
        path: requestPath,
        sourcePath: path,
        fixtureKind: kind,
        ...(kind === "file" || kind === "not-directory"
          ? { sourceDigest: sha(readFileSync(path)) }
          : {}),
        expected,
      });
    }
    for (const [name, source] of [
      ["portable.json", JSON.stringify(portable)],
      ["executable.json", JSON.stringify(executable)],
      [
        "portable-unpaired.json",
        JSON.stringify({ ...portable, description: "\ud800" }),
      ],
      [
        "executable-unpaired.json",
        JSON.stringify({ ...executable, description: "\ud800" }),
      ],
      ["empty.json", ""],
      ["whitespace.json", " \n\t "],
      ["truncated-object.json", "{"],
      ["truncated-pack.json", '{"schemaVersion":"1.0.0",'],
      ["trailing-comma.json", JSON.stringify(portable).replace(/}$/, ",}")],
      ["missing-colon.json", '{"schemaVersion" "1.0.0"}'],
      ["bad-literal.json", '{"schemaVersion":"1.0.0","id":truee}'],
      ["bom.json", "\ufeff" + JSON.stringify(portable)],
      ["null.json", "null"],
      ["undefined.json", "undefined"],
      ["extra-value.json", JSON.stringify(portable) + " false"],
      [
        "portable-duplicates.json",
        JSON.stringify(portable).replace(
          '"version":"1"',
          '"version":"old","version":"1"',
        ),
      ],
      [
        "executable-duplicates.json",
        JSON.stringify(executable).replace(
          '"version":"1"',
          '"version":"old","version":"1"',
        ),
      ],
      [
        "replacement.json",
        Buffer.concat([
          Buffer.from(
            JSON.stringify({ ...portable, description: "BEFORE" })
              .replace("BEFORE", "")
              .slice(0, -2),
          ),
          Buffer.from([0xff]),
          Buffer.from('"}'),
        ]),
      ],
    ])
      await addFile(name, source);
    await addFile("missing.json", null, "missing");
    await addFile("directory", null, "directory");
    await addFile("not-directory", null, "not-directory");
    await addFile("loop.json", null, "loop");
  } else if (nested) {
    const handling = {
      lossiness: "conservative",
      uncertainty: "conservative",
      authority: "none",
    };
    const reverse = {
      id: "urn:law:reverse",
      operation: "reverse",
      operands: ["test:edge"],
      resultRelation: "test:edge",
      handling,
    };
    const chain = {
      ...reverse,
      id: "urn:law:chain",
      operation: "chain",
      operands: ["test:edge", "test:edge"],
    };
    const pack = (law) => ({ ...structuredClone(executable), laws: [law] });
    for (const law of [reverse, chain]) {
      add(`${law.operation}-neutral`, pack(structuredClone(law)));
      for (const key of [
        "id",
        "operation",
        "operands",
        "resultRelation",
        "handling",
        "conditions",
      ]) {
        for (const value of [undefined, null, false, 0, "", [], {}]) {
          const changed = structuredClone(law);
          if (value === undefined) delete changed[key];
          else changed[key] = value;
          add(
            `${law.operation}-${key}-${value === undefined ? "absent" : JSON.stringify(value)}`,
            pack(changed),
          );
        }
      }
      for (const patch of [
        { operands: [] },
        { operands: ["test:edge", "test:edge", "test:edge"] },
        { operands: [null, false] },
        { operation: "unknown", operands: [] },
        {
          handling: { authority: "delegate", uncertainty: 0, lossiness: false },
        },
        { handling: { unknownZ: true, unknownA: false } },
        { conditions: { middleKinds: ["x"] } },
        { conditions: { sourceKinds: [], middleKinds: [], targetKinds: [] } },
        { conditions: { middleKinds: ["__proto__", "__proto__"] } },
        { conditions: { sourceKinds: [0, 0], middleKinds: [false, false] } },
        { conditions: { sourceKinds: ["a", "b", "a", "b", "a"] } },
        { conditions: { unknownZ: true, unknownA: false } },
        { id: null, operation: "unknown", operands: [], handling: {} },
      ]) {
        add(
          `${law.operation}-patch-${JSON.stringify(patch)}`,
          pack({ ...law, ...patch }),
        );
      }
    }
    const contexts = [
      null,
      false,
      [],
      {},
      { key: "x", operator: "equals", value: null },
      { key: "x", operator: "not-equals", value: false },
      { key: "x", operator: "in", values: [null, false, 0, ""] },
      { key: "x", operator: "not-in", values: [true] },
      { key: "x", operator: "exists" },
      { key: "x", operator: "exists", value: false },
      { key: "x", operator: "equals" },
      { key: "", operator: "equals", value: [] },
      { key: false, operator: "unknown", value: {} },
      { key: "x", operator: "in", values: [] },
      { key: "x", operator: "in", values: [null, null] },
      { key: "x", operator: "in", values: [0, false, 0, false, 0] },
      { key: "x", operator: "in", values: [[], {}] },
      { key: "x", operator: "exists", value: null },
      { key: "x", operator: "equals", value: true, values: [true] },
      { all: [] },
      { any: false },
      { not: null },
      { all: [{ key: "x", operator: "exists" }] },
      { any: [{ key: "x", operator: "exists", value: true }] },
      { not: { key: "x", operator: "equals", value: 1 } },
      { all: [{ any: [{ not: { key: "x", operator: "exists" } }] }] },
      { all: [{ key: "x", operator: "exists" }, {}] },
      { any: [{ not: { key: 0, operator: "equals", value: [] } }, false] },
      { all: [], any: [], not: {} },
      { unknownZ: true, unknownA: false },
    ];
    for (const context of contexts)
      add(
        `context-${JSON.stringify(context)}`,
        pack({ ...chain, conditions: { context } }),
      );
    const imported = {
      id: "urn:pack:other",
      version: "1",
      digest: "sha256:" + "a".repeat(64),
    };
    for (const imports of [
      null,
      false,
      [],
      [imported],
      [imported, imported],
      [{ id: null, version: "", digest: "wrong", unknown: true }, {}],
      [null, null],
    ])
      add(`imports-${JSON.stringify(imports)}`, { ...executable, imports });
    for (const field of ["disjointWith", "composesWith", "cardinalities"])
      for (const values of [
        [null, null],
        [0, 0],
        ["__proto__", "__proto__"],
        ["test:edge", "test:edge"],
      ]) {
        const changed = structuredClone(executable);
        changed.relations[0][field] = values;
        add(`relation-${field}-${JSON.stringify(values)}`, changed);
      }
  } else {
    for (const base of [portable, executable]) {
      const version = base.schemaVersion;
      add(`neutral-${version}`, structuredClone(base));
      for (const path of [
        ["schemaVersion"],
        ["id"],
        ["version"],
        ["relations"],
        ["relations", 0],
        ["relations", 0, "id"],
        ["relations", 0, "cyclePolicy"],
      ]) {
        for (const value of [undefined, null, false, 0, "", [], {}]) {
          const changed = structuredClone(base);
          let parent = changed;
          for (const key of path.slice(0, -1)) parent = parent[key];
          if (value === undefined && typeof path.at(-1) === "string")
            delete parent[path.at(-1)];
          else parent[path.at(-1)] = value === undefined ? null : value;
          add(
            `${version}-${path.join(".")}-${value === undefined ? "absent" : JSON.stringify(value)}`,
            changed,
          );
        }
      }
      for (const patch of [
        { newMandatoryFeature: true },
        { unknownA: true, unknownB: false },
        { id: null, version: false },
        { $schema: null, description: 0 },
        { $schema: 'relative/"quoted' },
        { $schema: "https://example.test/schema" },
        { $schema: "not a URI" },
        { description: "😀\u{e000}\u{e001}" },
        { description: "\ud800" },
        { version: "\udfff" },
      ])
        add(`${version}-patch-${JSON.stringify(patch)}`, {
          ...structuredClone(base),
          ...patch,
        });
      for (const fields of [
        { sourceKinds: [] },
        { sourceKinds: ["\ud800", "\u{e000}\u{e001}"] },
        { sourceKinds: ["x", "x"] },
        { sourceKinds: ["a", "b", "a", "b", "a"] },
        { sourceKinds: ["__proto__", "__proto__"] },
        { sourceKinds: ["constructor", "constructor"] },
        { sourceKinds: [null, null] },
        { sourceKinds: [0, 0] },
        { targetKinds: "x" },
        { cardinalities: ["invalid"] },
        {
          cardinalities: [
            "one-to-one",
            "many-to-one",
            "one-to-one",
            "many-to-one",
            "one-to-one",
          ],
        },
        { inverse: "INVALID" },
        { cyclePolicy: "unknown" },
        { id: false, cyclePolicy: "unknown" },
        { unknownA: true, unknownB: false },
        { transitive: "yes" },
      ]) {
        const changed = structuredClone(base);
        Object.assign(changed.relations[0], fields);
        add(`${version}-relation-${JSON.stringify(fields)}`, changed);
      }
    }
    for (const value of [
      null,
      false,
      0,
      "",
      [],
      {},
      { schemaVersion: "9.0.0" },
    ])
      add(`root-${JSON.stringify(value)}`, value);
  }
  verifyTree();
  const sourceFiles = [
    "src/relation-pack.ts",
    "src/canonical.ts",
    "src/stable.ts",
    "schemas/relation-pack.schema.json",
    "schemas/relation-pack-v2.schema.json",
  ].map((path) => ({ path, digest: sha(readFileSync(join(oracle, path))) }));
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        sourceFiles,
        ...(files
          ? {
              host: {
                platform: process.platform,
                architecture: process.arch,
                node: process.version,
              },
            }
          : {}),
        scope: files
          ? "Finite Node 22/macOS file-load data/digests and thrown name/message/code/path/errno/syscall. Retained fixture paths and bytes are immutable. Runtime stack locations and added native report metadata are outside this component comparison; the full JS/loader/platform/resource contract remains open."
          : nested
            ? "Finite executable law/conditional/context/import JSON schema controls, parser identity, valid original digests and exact thrown name/message. No arbitrary JS object, unchecked digest, file or resource-bound equivalence."
            : "Finite plain JSON pack shape, parser identity, version-specific valid digests and exact thrown name/message. Does not establish arbitrary JS objects, unchecked digest inputs, file parsing/errors or resource-bound equivalence.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpusBytes = readFileSync(corpusPath);
const corpus = JSON.parse(corpusBytes);
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
function verifyFileFixtures() {
  if (!files) return;
  assert.deepEqual(
    corpus.host,
    {
      platform: process.platform,
      architecture: process.arch,
      node: process.version,
    },
    "Frozen file runtime/host profile",
  );
  for (const row of corpus.cases) {
    if (row.fixtureKind === "missing") {
      assert.throws(() => lstatSync(row.sourcePath), { code: "ENOENT" });
      continue;
    }
    const stat = lstatSync(row.sourcePath);
    if (row.fixtureKind === "directory") assert.ok(stat.isDirectory());
    else if (row.fixtureKind === "loop") {
      assert.ok(stat.isSymbolicLink());
      assert.equal(readlinkSync(row.sourcePath), row.name);
    } else {
      assert.ok(stat.isFile());
      assert.equal(
        sha(readFileSync(row.sourcePath)),
        row.sourceDigest,
        "Frozen file bytes changed",
      );
    }
  }
}
verifyFileFixtures();
for (const entry of corpus.sourceFiles)
  assert.equal(sha(readFileSync(join(oracle, entry.path))), entry.digest);
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(root, "docs/acceptance/parity", `${corpusName}-${stamp}`);
mkdirSync(output);
const binary = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
let currentCase,
  calls = 0;
const api = createLegacyValidationApi(binary, (execution) => {
  calls++;
  appendFileSync(
    join(output, "native-executions.ndjson"),
    JSON.stringify({ caseName: currentCase, ...execution }) + "\n",
  );
  assert.equal(execution.command[0], binary);
  assert.equal(execution.signal, null);
  assert.equal(execution.processError, null);
});
const results = [];
for (const row of corpus.cases) {
  currentCase = row.name;
  const before = JSON.stringify(row.value);
  let observed;
  try {
    const parsed = files
      ? await api.loadLegacyRelationPack(row.path)
      : api.parseLegacyRelationPack(row.value);
    if (!files)
      assert.equal(parsed, row.value, "Native-backed parser identity");
    observed = {
      status: "accepted",
      ...(files ? { document: parsed } : {}),
      digest: api.digestLegacyRelationPack(parsed),
    };
  } catch (error) {
    observed = errorOutcome(error);
  }
  assert.equal(JSON.stringify(row.value), before, "Caller data changed");
  results.push({
    name: row.name,
    expected: row.expected,
    observed,
    equal: JSON.stringify(observed) === JSON.stringify(row.expected),
  });
}
verifyTree();
const differences = results.filter((row) => !row.equal);
verifyFileFixtures();
const receipt = {
  schemaVersion: "1.0.0",
  status: differences.length
    ? "differences-observed"
    : "component-controls-passed",
  supervision,
  reference: {
    engine: corpus.referenceEngine,
    corpus: relative(root, corpusPath),
    corpusDigest: sha(corpusBytes),
    sourceFiles: corpus.sourceFiles,
  },
  candidate: {
    binaryDigest: sha(readFileSync(binary)),
    engine: JSON.parse(execFileSync(binary, ["engine"], { env: {} })),
    sdkSourceInventory: ["canonical.mjs", "legacy-validation.mjs"].map(
      (name) => ({
        path: `sdk/typescript/${name}`,
        digest: sha(readFileSync(join(root, "sdk/typescript", name))),
      }),
    ),
  },
  comparedCases: results.length,
  matchedCases: results.length - differences.length,
  nativeExecutions: calls,
  results,
  differences,
  originalCasesClosed: 0,
  scope: corpus.scope,
  traceDigest: sha(readFileSync(join(output, "native-executions.ndjson"))),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "driver.mjs"),
  readFileSync(fileURLToPath(import.meta.url)),
  { flag: "wx" },
);
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
console.log(
  JSON.stringify({
    status: receipt.status,
    comparedCases: results.length,
    matchedCases: receipt.matchedCases,
    differences: differences.length,
    receipt: relative(root, join(output, "receipt.json")),
  }),
);
// Differences are retained diagnostic findings, never a successful parity gate.
process.exitCode = differences.length ? 1 : 0;
