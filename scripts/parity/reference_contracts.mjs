/** Freeze original identifier/path/URI observations before native comparison. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  appendFileSync,
} from "node:fs";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
function verifyTree() {
  for (const item of supplement.referenceTree) {
    const raw = readFileSync(join(oracle, item.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${raw.length}\0`)
        .update(raw)
        .digest("hex"),
      item.gitBlob,
      item.path,
    );
  }
}
verifyTree();
const corpusPath = join(root, "fixtures/parity/reference-controls.json");
function guardValue(input) {
  switch (input.kind) {
    case "undefined":
      return undefined;
    case "symbol":
      return Symbol("x");
    case "bigint":
      return 1n;
    case "function":
      return () => {};
    case "string-object":
      return new String("urn:x");
    case "null-prototype":
      return Object.create(null);
    case "getter-object":
      return Object.defineProperty({}, "toJSON", {
        get() {
          throw new Error("Type guard touched getter");
        },
      });
    default:
      return input.value;
  }
}
function observe(action, api) {
  const input = JSON.parse(action.input);
  try {
    let value;
    switch (action.operation) {
      case "reference-identifier":
        value = api.isReferenceIdentifier(guardValue(input));
        break;
      case "relation-identifier":
        value = api.isRelationIdentifier(guardValue(input));
        break;
      case "urn":
        value = api.makeUrn(input.namespace, input.kind, input.value);
        break;
      case "repository-uri":
        value = api.makeRepositoryUri(input.path, input.repository);
        break;
      case "ambiguous-path":
        value = api.hasAmbiguousPathLanguage(input.path);
        break;
      case "path-pattern":
        value = api.isPathPattern(input.path);
        break;
      default:
        throw new Error("Unknown control");
    }
    return { status: "observed", value };
  } catch (error) {
    return {
      status: "threw",
      error: { name: error.name, message: error.message },
    };
  }
}
if (!existsSync(corpusPath)) {
  const api = await import(pathToFileURL(join(oracle, "dist/references.js")));
  const cases = [];
  const add = (name, operation, input) => {
    const action = { operation, input: JSON.stringify(input) };
    cases.push({ name, action, expected: observe(action, api) });
  };
  for (const value of [null, true, false, 0, 17, {}, [], ["urn:x"]])
    for (const operation of ["reference-identifier", "relation-identifier"])
      add(operation + "-nonstring-" + cases.length, operation, { value });
  for (const kind of [
    "undefined",
    "symbol",
    "bigint",
    "function",
    "string-object",
    "null-prototype",
    "getter-object",
  ])
    for (const operation of ["reference-identifier", "relation-identifier"])
      add(operation + "-" + kind, operation, { kind });
  for (const value of [
    "urn:x",
    "urn:",
    "URN:x",
    "x:y:z",
    "a+.-1:thing",
    "1:x",
    ":x",
    "a_b:x",
    "a:b/c#q?x=1",
    "https://example.test/path",
    "a:x y",
    "a:x\n",
    "a:x\r",
    "a:x\r\n",
    "a:x\u2028",
    "a:x\u2029",
    "core:maps",
    "core:a_1.-",
    "Core:maps",
    "core:Maps",
    "co+re:maps",
    "a:b:c",
    "urn:😀",
    "urn:\ud800",
    "urn:\udfff",
  ])
    for (const operation of ["reference-identifier", "relation-identifier"])
      add(operation + "-syntax-" + cases.length, operation, { value });
  const whitespace = [
    9, 10, 11, 12, 13, 32, 160, 0x1680, 0x180e, 0x2000, 0x2001, 0x2002, 0x2003,
    0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x200b, 0x2028,
    0x2029, 0x202f, 0x205f, 0x3000, 0xfeff, 0x85,
  ];
  for (const unit of whitespace) {
    const ch = String.fromCharCode(unit);
    add("identifier-whitespace-" + unit, "reference-identifier", {
      value: "urn:x" + ch + "y",
    });
    add("ambiguous-whitespace-" + unit, "ambiguous-path", {
      path: "a" + ch + "oR" + ch + "b",
    });
  }
  for (const path of [
    "x or y",
    " OR ",
    "x\tor\ny",
    "xor y",
    "x ory",
    "or",
    "x or ",
    " x OR y ",
    "x otherwise y",
    "x or or y",
    "x\u200bor\u200by",
    "[x]",
    "{x}",
    "x*",
    "x?",
    "x]",
    "x}",
    "x\\y",
    "x\ud800",
    "./a/b",
  ]) {
    add("ambiguous-syntax-" + cases.length, "ambiguous-path", { path });
    add("pattern-syntax-" + cases.length, "path-pattern", { path });
  }
  for (const value of [
    "",
    "AZaz09-_.!~*'()",
    "a b/c?d#e&f=g%h",
    "é é 😀",
    "\u0000\b\t\n\r",
    "\ue000\ue001",
    "日Ω한",
    "\ud800",
    "\udfff",
    "a\ud800b",
    "\ud800\udc00",
  ])
    add("urn-encoding-" + cases.length, "urn", {
      namespace: "n:space\ud800",
      kind: "mapping",
      value,
    });
  for (const path of [
    "./a\\b/../c",
    "././a",
    "/absolute//path",
    "../a/b",
    "a b/[x]/{y}/*.ts",
    "a%2Fb?x=1#y",
    "é/😀/日",
    "a\n\r\t",
    "\ud800/path",
    "a/\udfff",
    "",
  ])
    for (const repository of [
      undefined,
      "workspace",
      "repository/name",
      "a b",
      "é",
      "\ud800",
    ])
      add("repository-uri-" + cases.length, "repository-uri", {
        path,
        ...(repository === undefined ? {} : { repository }),
      });
  verifyTree();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        originalRuntime: process.version,
        originalArtifacts: ["dist/references.js"].map((path) => ({
          path,
          digest: sha(readFileSync(join(oracle, path))),
        })),
        scope:
          "Original reference/locator public functions over typed strings and complete nonstring type-guard categories, including ECMAScript whitespace, normalization, percent encoding and URIError. Untyped method-coercion/accessor/error details, resources, package and platform obligations remain open.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpus = JSON.parse(readFileSync(corpusPath));
for (const item of corpus.originalArtifacts)
  assert.equal(sha(readFileSync(join(oracle, item.path))), item.digest);
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
if (process.argv.includes("--freeze-only")) {
  console.log(
    JSON.stringify({
      status: "original-observations-frozen",
      cases: corpus.cases.length,
      corpusDigest: sha(readFileSync(corpusPath)),
    }),
  );
  process.exit(0);
}
assert.equal(process.argv.length, 2);
const output = join(
  root,
  "docs/acceptance/parity",
  `reference-controls-${new Date().toISOString().replaceAll(":", "-")}`,
);
mkdirSync(output, { recursive: true });
const trace = join(output, "native-executions.ndjson");
const cli = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
let caseName;
const facade = createLegacyValidationApi(cli, (e) =>
  appendFileSync(trace, JSON.stringify({ caseName, ...e }) + "\n"),
);
const api = {
  isReferenceIdentifier: facade.isLegacyReferenceIdentifier,
  isRelationIdentifier: facade.isLegacyRelationIdentifier,
  makeUrn: facade.makeLegacyUrn,
  makeRepositoryUri: facade.makeLegacyRepositoryUri,
  hasAmbiguousPathLanguage: facade.hasLegacyAmbiguousPathLanguage,
  isPathPattern: facade.isLegacyPathPattern,
};
const results = corpus.cases.map((test) => {
  caseName = test.name;
  const observed = observe(test.action, api);
  let matched = true;
  try {
    assert.deepEqual(observed, test.expected);
  } catch {
    matched = false;
  }
  return { name: test.name, matched, observed };
});
verifyTree();
const executions = readFileSync(trace, "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
assert.equal(executions.length, corpus.cases.length);
assert(
  executions.every(
    (call) =>
      call.command[0] === cli &&
      call.command.slice(1).join(" ") === "legacy references json" &&
      !call.processError &&
      !call.signal,
  ),
);
const matched = results.filter((r) => r.matched).length;
const receipt = {
  schemaVersion: "1.0.0",
  status: matched === results.length ? "matched" : "differences",
  supervision,
  referenceEngine: corpus.referenceEngine,
  corpus: {
    path: relative(root, corpusPath),
    digest: sha(readFileSync(corpusPath)),
  },
  candidate: {
    binaryDigest: sha(readFileSync(cli)),
    engine: JSON.parse(execFileSync(cli, ["engine"])),
    sdkSourceInventory: [
      "legacy-validation.mjs",
      "legacy-validation.d.ts",
      "legacy-references.mjs",
      "legacy-references.d.ts",
      "canonical.mjs",
    ].map((name) => ({
      path: `sdk/typescript/${name}`,
      digest: sha(readFileSync(join(root, "sdk/typescript", name))),
    })),
  },
  counts: {
    cases: results.length,
    matched,
    differences: results.length - matched,
    nativeExecutions: executions.length,
  },
  originalGitBlobsVerifiedBeforeAndAfter: supplement.referenceTree.length,
  scope:
    corpus.scope +
    " Error stacks and supplemental error.report are outside this comparison.",
  results,
  traceDigest: sha(readFileSync(trace)),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(root, ".tools/parity/current-reference-controls.json"),
  JSON.stringify(
    { receipt: relative(root, join(output, "receipt.json")) },
    null,
    2,
  ) + "\n",
);
console.log(
  JSON.stringify({
    receipt: relative(root, join(output, "receipt.json")),
    counts: receipt.counts,
  }),
);
process.exitCode = matched === results.length ? 0 : 1;
