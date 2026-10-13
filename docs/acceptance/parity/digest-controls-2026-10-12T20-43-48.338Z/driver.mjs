/** Freeze unchecked original digests before comparing the Rust transport. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync, appendFileSync } from "node:fs";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";

const supervision = await ensureGuarded();
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
const pointer = JSON.parse(readFileSync(join(root, ".tools/parity/oracles/current.json")));
const oracle = join(root, pointer.source);
const supplement = JSON.parse(readFileSync(join(root, "fixtures/parity/supplement.json")));
function verifyTree() {
  for (const item of supplement.referenceTree) {
    const raw = readFileSync(join(oracle, item.path));
    assert.equal(createHash("sha1").update(`blob ${raw.length}\0`).update(raw).digest("hex"), item.gitBlob, item.path);
  }
}
verifyTree();
const corpusPath = join(root, "fixtures/parity/digest-controls.json");
function observe(callback) {
  try { return { status: "observed", digest: callback() }; }
  catch (error) { return { status: "threw", error: { name: error.name, message: error.message } }; }
}
if (!existsSync(corpusPath)) {
  const original = await import(pathToFileURL(join(oracle, "dist/relation-pack.js")));
  const stable = await import(pathToFileURL(join(oracle, "dist/stable.js")));
  const cases = [];
  function add(name, text) {
    const value = JSON.parse(text);
    const expected = observe(() => original.relationPackDigest(value));
    const stableJson = value !== null && value.schemaVersion !== "2.0.0" ? stable.stableJson(value) : undefined;
    cases.push({ name, text, expected, ...(stableJson !== undefined ? { stableJson } : {}) });
  }
  add("null-dispatch", "null");
  for (const [name, text] of [
    ["empty-unchecked", "{}"], ["boolean", "true"], ["number", "42"], ["string", '"hello"'],
    ["array", '[3,{"z":1,"A":2,"a":3},null]'],
    ["case-order", '{"schemaVersion":"1.0.0","Z":1,"a":2,"A":3,"z":4}'],
    ["numeric-keys", '{"20":1,"3":2,"10":3,"2":4,"01":5,"4294967295":6,"4294967294":7,"-0":8}'],
    ["nested", '{"schemaVersion":"1.0.0","payload":{"z":[],"A":{"b":1,"a":2},"a":[{"B":true,"b":false}]}}'],
    ["duplicate-retains-first-key-position", '{"é":1,"é":2,"é":3}'],
    ["escaped-duplicate-retains-position", '{"é":1,"é":2,"\\u00e9":3}'],
    ["prototype-names", '{"__proto__":{"z":1,"a":2},"constructor":3,"toString":4}'],
    ["unknown-version", '{"schemaVersion":"99.0.0","Z":1,"a":2}'],
    ["invalid-executable-shape", '{"schemaVersion":"2.0.0","Z":1,"a":2}'],
    ["executable-jcs-order", '{"schemaVersion":"2.0.0","20":1,"3":2,"Z":3,"a":4,"é":5}'],
    ["executable-last-version", '{"schemaVersion":"1.0.0","schemaVersion":"2.0.0","z":1}'],
    ["legacy-last-version", '{"schemaVersion":"2.0.0","schemaVersion":"1.0.0","Z":1,"a":2}'],
  ]) add(name, text);
  for (const [name, keys] of [
    ["accent", ["é", "e", "E", "é", "è", "ê"]],
    ["canonical-tie", ["é", "é"]], ["ignorable-tie", ["a", "a\u0000", "a\u200d"]],
    ["punctuation", ["a-b", "ab", "a_b", "a b", "a.b"]],
    ["turkish", ["I", "ı", "İ", "i"]], ["swedish", ["ä", "å", "z", "ö", "a"]],
    ["nonlatin", ["日", "あ", "ア", "Ω", "ж", "한", "中"]],
    ["astral", ["😀", "𝒜", "𐀀", "A"]],
    ["unpaired", ["\ud800", "\udfff", "\ufffd", "\ue000", "\ue000\ue001"]],
  ]) for (const reverse of [false, true]) {
    const ordered = reverse ? [...keys].reverse() : keys;
    add(`${name}-${reverse ? "reverse" : "forward"}`, JSON.stringify(Object.fromEntries(ordered.map((key) => [key, keys.indexOf(key)]))));
  }
  for (const [name, text] of [
    ["negative-zero", '{"z":-0,"a":0}'],
    ["number-thresholds", '{"a":1e-7,"b":1e-6,"c":1e20,"d":1e21,"e":5e-324,"f":1.7976931348623157e308}'],
    ["rounded-integer", '{"n":9007199254740993,"m":18446744073709551615}'],
    ["strings", '{"z":"\\ud800\\udc00\\udfff\\ue000\\ue001","a":"\\b\\t\\n\\r\\f\\u0000\\\"\\\\/"}'],
    ["values-not-normalized", '{"é":"é","é":"é"}'],
  ]) add(name, text);
  verifyTree();
  writeFileSync(corpusPath, JSON.stringify({ schemaVersion: "1.0.0", referenceEngine: supplement.referenceEngine,
    originalRuntime: process.version, originalIcu: process.versions.icu, originalCollation: new Intl.Collator().resolvedOptions(),
    originalArtifacts: ["dist/relation-pack.js", "dist/stable.js", "dist/canonical.js"].map((path) => ({ path, digest: sha(readFileSync(join(oracle, path))) })),
    scope: "Finite unchecked JSON digest observations. No arbitrary JavaScript, exhaustive collation/version, resource, package or platform obligation is closed.", cases }, null, 2) + "\n", { flag: "wx" });
}
const corpus = JSON.parse(readFileSync(corpusPath));
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
assert.equal(corpus.originalCollation.locale, new Intl.Collator().resolvedOptions().locale);
const output = join(root, "docs/acceptance/parity", `digest-controls-${new Date().toISOString().replaceAll(":", "-")}`);
mkdirSync(output, { recursive: true });
const trace = join(output, "native-executions.ndjson");
const cli = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs")));
let caseName;
const api = createLegacyValidationApi(cli, (execution) => appendFileSync(trace, JSON.stringify({ caseName, ...execution }) + "\n"));
const results = corpus.cases.map((test) => {
  caseName = test.name;
  const observed = observe(() => api.digestLegacyRelationPack(JSON.parse(test.text)));
  let matched = true;
  try { assert.deepEqual(observed, test.expected); } catch { matched = false; }
  return { name: test.name, matched, observed, expected: test.expected };
});
verifyTree();
const executions = readFileSync(trace, "utf8").trim().split("\n").map(JSON.parse);
assert(executions.every((call) => call.command[0] === cli && call.command[2] === "pack" && call.command[3] === "digest" && !call.processError && !call.signal));
assert.equal(executions.length, corpus.cases.length);
const matched = results.filter((row) => row.matched).length;
const receipt = { schemaVersion: "1.0.0", status: matched === results.length ? "matched" : "differences", supervision,
  referenceEngine: corpus.referenceEngine, corpus: { path: relative(root, corpusPath), digest: sha(readFileSync(corpusPath)) },
  candidate: { binaryDigest: sha(readFileSync(cli)), engine: JSON.parse(execFileSync(cli, ["engine"])), sdkSourceInventory: ["legacy-validation.mjs", "canonical.mjs"].map((name) => ({ path: `sdk/typescript/${name}`, digest: sha(readFileSync(join(root, "sdk/typescript", name))) })) },
  counts: { cases: results.length, matched, differences: results.length - matched, nativeExecutions: executions.length },
  scope: corpus.scope + " Error stack and supplemental error.report are outside this comparison.", originalGitBlobsVerifiedBeforeAndAfter: supplement.referenceTree.length,
  results, traceDigest: sha(readFileSync(trace)), driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))) };
writeFileSync(join(output, "receipt.json"), JSON.stringify(receipt, null, 2) + "\n", { flag: "wx" });
writeFileSync(join(output, "driver.mjs"), readFileSync(fileURLToPath(import.meta.url)), { flag: "wx" });
console.log(JSON.stringify({ status: receipt.status, receipt: relative(root, join(output, "receipt.json")), ...receipt.counts }, null, 2));
process.exitCode = matched === results.length ? 0 : 1;
