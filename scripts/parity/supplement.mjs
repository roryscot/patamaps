/** Add reviewed inventory omissions without rewriting the first frozen baseline. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const reference = resolve(process.argv[2] ?? "/Users/admin/dev/SEEDZ/metamap");
const baseline = readFileSync(join(root, "fixtures/parity/manifest.json"));
const manifest = JSON.parse(baseline);
const engine = manifest.reference.engine;
const ts = createRequire(join(reference, "package.json"))("typescript");
const sha = (data) =>
  "sha256:" + createHash("sha256").update(data).digest("hex");
const git = (args) =>
  execFileSync("git", ["-C", reference, ...args], {
    maxBuffer: 64 * 1024 * 1024,
  });
assert.equal(git(["status", "--porcelain"]).length, 0);
const original = (path) => git(["show", `${engine}:${path}`]);
const obligations = [];
const assigned = new Set(manifest.obligations.map((row) => row.origin.path));
for (const file of [...manifest.schemas, ...manifest.relationPacks]) {
  if (assigned.has(file.path)) continue;
  const identity = `auxiliary-data:${file.path}`;
  obligations.push({
    id: `parity:${sha(identity).slice(7, 27)}`,
    identity,
    kind: "contract-data",
    name: file.path,
    origin: { path: file.path, digest: file.digest },
    status: "unclassified",
    candidateEvidence: [],
    workstream: "P2",
    candidateEntryPoint: { kind: "legacy-contract-import", path: file.path },
    verificationStrategy:
      "Preserve the original contract bytes and exercise the public scientific workflows that depend on the slot vocabulary or scientific relation pack.",
    expectation: { kind: "exact-source-bytes", digest: file.digest },
    inventoryCorrection:
      "Referenced public contract data was listed but had no obligation row in the first freeze.",
  });
}
for (const parent of manifest.obligations.filter(
  (row) => row.kind === "exported-symbol" && row.category === "value",
)) {
  const raw = original(parent.origin.path);
  const file = ts.createSourceFile(
    parent.origin.path,
    raw.toString(),
    ts.ScriptTarget.Latest,
    true,
  );
  for (const node of file.statements) {
    if (!ts.isClassDeclaration(node) || node.name?.text !== parent.name)
      continue;
    for (const member of node.members) {
      if (!ts.isConstructorDeclaration(member)) continue;
      for (const parameter of member.parameters) {
        const mods =
          parameter.modifiers?.map((modifier) => modifier.kind) ?? [];
        if (
          !mods.some(
            (kind) =>
              kind === ts.SyntaxKind.PublicKeyword ||
              kind === ts.SyntaxKind.ReadonlyKeyword,
          ) ||
          mods.some(
            (kind) =>
              kind === ts.SyntaxKind.PrivateKeyword ||
              kind === ts.SyntaxKind.ProtectedKeyword,
          )
        )
          continue;
        const name = parameter.name.getText(file);
        const identity = `member:${parent.origin.path}:${parent.name}.${name}:instance`;
        if (manifest.obligations.some((row) => row.identity === identity))
          continue;
        obligations.push({
          id: `parity:${sha(identity).slice(7, 27)}`,
          identity,
          kind: "class-member",
          name: `${parent.name}.${name}`,
          origin: {
            path: parent.origin.path,
            digest: sha(raw),
            line:
              file.getLineAndCharacterOfPosition(parameter.getStart(file))
                .line + 1,
          },
          parent: parent.id,
          status: "unclassified",
          candidateEvidence: [],
          workstream: "P6",
          candidateEntryPoint: {
            kind: "mapped-public-api",
            referenceModule: parent.origin.path,
            symbol: `${parent.name}.${name}`,
          },
          verificationStrategy:
            "Compile and execute a consumer that inspects the public error property through the Rust-backed compatibility facade.",
          expectation: {
            kind: "pinned-declaration",
            declarationDigest: sha(parameter.getText(file)),
            declaration: parameter.getText(file),
          },
          inventoryCorrection:
            "A public constructor parameter property is part of the class API, even though it is not a separate class-member declaration.",
        });
      }
    }
  }
}
obligations.sort((a, b) =>
  a.identity < b.identity ? -1 : a.identity > b.identity ? 1 : 0,
);
const referenceTree = git(["ls-tree", "-r", engine])
  .toString()
  .trim()
  .split("\n")
  .map((line) => {
    const [record, path] = line.split("\t");
    const [mode, type, object] = record.split(" ");
    assert.equal(type, "blob", `Unsupported pinned tree entry ${path}`);
    return { path, mode, gitBlob: object };
  });
const supplement = {
  schemaVersion: "1.0.0",
  referenceEngine: engine,
  baselineDigest: sha(baseline),
  purpose:
    "Append omissions discovered during inventory review. The original denominator and assertions remain untouched; completion includes both files.",
  obligations,
  referenceTree,
  expandedObligationCount: manifest.obligations.length + obligations.length,
  ownerApprovedDeviations: [],
};
const target = join(root, "fixtures/parity/supplement.json");
const output = JSON.stringify(supplement, null, 2) + "\n";
if (process.argv.includes("--check"))
  assert.equal(readFileSync(target, "utf8"), output, "Supplement drift");
else {
  assert(!existsSync(target), "Refusing to overwrite the frozen supplement");
  writeFileSync(target, output);
}
console.log(
  JSON.stringify(
    {
      status: process.argv.includes("--check")
        ? "supplement-exact"
        : "supplement-frozen",
      added: obligations.length,
      total: supplement.expandedObligationCount,
      pinnedTreeFiles: referenceTree.length,
      omissions: obligations.map((row) => row.name),
    },
    null,
    2,
  ),
);
