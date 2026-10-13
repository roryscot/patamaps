/** Read-only source audit; no native build, dependency install or test execution.
 * Reconcile exports and actual CLI parser branches against frozen obligations.
 * A successful audit verifies inventory only, never candidate functionality. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { resolve, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";

const supervision = await ensureGuarded();

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const manifestRaw = readFileSync(join(root, "fixtures/parity/manifest.json"));
const manifest = JSON.parse(manifestRaw);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const source = join(root, pointer.source);
const sha = (raw) => "sha256:" + createHash("sha256").update(raw).digest("hex");
function verifyTree() {
  for (const file of supplement.referenceTree) {
    const raw = readFileSync(join(source, file.path));
    assert.equal(
      createHash("sha1")
        .update(`blob ${raw.length}\0`)
        .update(raw)
        .digest("hex"),
      file.gitBlob,
      file.path,
    );
  }
}
verifyTree();
const ts = createRequire(join(source, "package.json"))("typescript");
const pkg = JSON.parse(readFileSync(join(source, "package.json")));
const production = supplement.referenceTree
  .map((file) => file.path)
  .filter(
    (path) =>
      path.startsWith("src/") &&
      path.endsWith(".ts") &&
      !path.includes("/__tests__/"),
  );
const program = ts.createProgram(
  production.map((path) => join(source, path)),
  {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.NodeNext,
    moduleResolution: ts.ModuleResolutionKind.NodeNext,
    strict: true,
    skipLibCheck: true,
    resolveJsonModule: true,
    esModuleInterop: true,
    noEmit: true,
  },
);
const checker = program.getTypeChecker();
const parserSupplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement-cli-parser.json")),
);
assert.equal(
  parserSupplement.previousSupplementDigest,
  sha(readFileSync(join(root, "fixtures/parity/supplement.json"))),
);
const baseline = [
  ...manifest.obligations,
  ...supplement.obligations,
  ...parserSupplement.obligations,
];
const byIdentity = new Map(baseline.map((row) => [row.identity, row]));
const bindings = [],
  members = new Map(),
  targets = new Set(),
  omissions = [],
  unresolved = [];
for (const [exportPath, target] of Object.entries(pkg.exports)) {
  const file =
    typeof target === "string"
      ? target.replace(/^\.\//, "")
      : target.import.replace(/^\.\/dist\//, "src/").replace(/\.js$/, ".ts");
  assert.equal(
    sha(readFileSync(join(source, file))),
    manifest.packageExports.find((row) => row.path === exportPath)?.digest,
  );
  if (!file.endsWith(".ts")) continue;
  const module = checker.getSymbolAtLocation(
    program.getSourceFile(join(source, file)),
  );
  assert(module, file);
  for (const publicSymbol of checker.getExportsOfModule(module)) {
    const symbol =
      publicSymbol.flags & ts.SymbolFlags.Alias
        ? checker.getAliasedSymbol(publicSymbol)
        : publicSymbol;
    const declarations =
      symbol.declarations?.filter((node) =>
        node.getSourceFile().fileName.startsWith(join(source, "src/")),
      ) ?? [];
    if (!declarations.length) {
      unresolved.push({ exportPath, publicName: publicSymbol.getName() });
      continue;
    }
    const declaration = declarations[0];
    const path = relative(
      source,
      declaration.getSourceFile().fileName,
    ).replaceAll("\\", "/");
    const category = symbol.flags & ts.SymbolFlags.Value ? "value" : "type";
    const identity = `symbol:${path}:${symbol.getName()}:${category}`;
    const row = byIdentity.get(identity);
    if (!row) omissions.push({ identity, exportPath });
    else {
      assert.equal(
        row.expectation.declarationDigest,
        sha(declaration.getText()),
      );
      assert(
        row.exportPaths.includes(exportPath),
        `${identity} has an uninventoried export path ${exportPath}`,
      );
      targets.add(row.id);
    }
    const type =
      category === "type"
        ? checker.getDeclaredTypeOfSymbol(symbol)
        : checker.getTypeOfSymbolAtLocation(symbol, declaration);
    bindings.push({
      exportPath,
      publicName: publicSymbol.getName(),
      targetName: symbol.getName(),
      target: row?.id ?? null,
      category,
      signature: checker.typeToString(
        type,
        declaration,
        ts.TypeFormatFlags.NoTruncation,
      ),
      originalSignature: row?.signature ?? null,
      sourceDeclarationDigests: declarations.map((node) => sha(node.getText())),
    });
    if (!ts.isClassDeclaration(declaration)) continue;
    const addMember = (name, node, isStatic = false) => {
      const identity = `member:${path}:${symbol.getName()}.${name}:${isStatic ? "static" : "instance"}`;
      const row = byIdentity.get(identity);
      if (!row) omissions.push({ identity });
      const entry = members.get(identity) ?? {
        identity,
        obligation: row?.id ?? null,
        declarations: [],
      };
      const digest = sha(node.getText());
      if (!entry.declarations.includes(digest)) entry.declarations.push(digest);
      members.set(identity, entry);
    };
    for (const member of declaration.members) {
      const modifiers = member.modifiers?.map((item) => item.kind) ?? [];
      if (
        modifiers.includes(ts.SyntaxKind.PrivateKeyword) ||
        modifiers.includes(ts.SyntaxKind.ProtectedKeyword) ||
        (member.name && ts.isPrivateIdentifier(member.name))
      )
        continue;
      const name = ts.isConstructorDeclaration(member)
        ? "constructor"
        : member.name?.getText();
      if (name)
        addMember(
          name,
          member,
          modifiers.includes(ts.SyntaxKind.StaticKeyword),
        );
      if (!ts.isConstructorDeclaration(member)) continue;
      for (const parameter of member.parameters) {
        const mods = parameter.modifiers?.map((item) => item.kind) ?? [];
        if (
          (mods.includes(ts.SyntaxKind.PublicKeyword) ||
            mods.includes(ts.SyntaxKind.ReadonlyKeyword)) &&
          !mods.includes(ts.SyntaxKind.PrivateKeyword) &&
          !mods.includes(ts.SyntaxKind.ProtectedKeyword)
        )
          addMember(parameter.name.getText(), parameter);
      }
    }
  }
}
assert.equal(
  targets.size,
  baseline.filter((row) => row.kind === "exported-symbol").length,
);
assert.equal(
  members.size,
  baseline.filter((row) => row.kind === "class-member").length,
);
const cli = program.getSourceFile(join(source, "src/cli.ts"));
const main = cli.statements.find(
  (node) => ts.isFunctionDeclaration(node) && node.name?.text === "main",
);
assert(main?.body);
const parserCommands = [];
function commandNames(condition) {
  if (!ts.isBinaryExpression(condition)) return [];
  if (condition.operatorToken.kind === ts.SyntaxKind.BarBarToken)
    return [...commandNames(condition.left), ...commandNames(condition.right)];
  if (
    condition.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken &&
    ts.isIdentifier(condition.left) &&
    condition.left.text === "command" &&
    ts.isStringLiteral(condition.right)
  )
    return [condition.right.text];
  return [];
}
for (const branch of main.body.statements.filter(ts.isIfStatement)) {
  const names = commandNames(branch.expression);
  if (!names.length) continue;
  const options = new Set();
  function walk(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "parseArguments"
    ) {
      const optionSet = node.arguments[1];
      assert(
        ts.isNewExpression(optionSet) &&
          optionSet.expression.getText(cli) === "Set",
        "Unresolved option-set expression",
      );
      const values = optionSet.arguments?.[0];
      if (values) {
        assert(ts.isArrayLiteralExpression(values));
        for (const item of values.elements) {
          assert(ts.isStringLiteral(item));
          options.add(item.text);
        }
      }
    }
    if (ts.isStringLiteral(node) && node.text === "--no-cache")
      options.add(node.text);
    ts.forEachChild(node, walk);
  }
  walk(branch.thenStatement);
  for (const command of names)
    parserCommands.push({
      command,
      options: [...options].sort(),
      line: cli.getLineAndCharacterOfPosition(branch.getStart(cli)).line + 1,
    });
}
assert.deepEqual(
  parserCommands.map((row) => row.command).sort(),
  manifest.cli.map((row) => row.command).sort(),
);
for (const branch of parserCommands) {
  const documented = manifest.cli.find(
    (row) => row.command === branch.command,
  ).flags;
  for (const option of documented)
    assert(
      branch.options.includes(option),
      `Help advertises an unrecognized option ${branch.command} ${option}`,
    );
  for (const option of branch.options)
    if (!byIdentity.has(`cli:${branch.command}:${option}`))
      omissions.push({
        identity: `cli:${branch.command}:${option}`,
        kind: "cli-option",
        command: branch.command,
        option,
        line: branch.line,
        reason:
          "The executable parser accepts this option although the help-derived frozen manifest omitted it.",
      });
}
for (const file of [...manifest.schemas, ...manifest.relationPacks])
  assert(
    baseline.some(
      (row) =>
        row.origin.path === file.path && row.origin.digest === file.digest,
    ),
    `Uninventoried contract data ${file.path}`,
  );
const examples = supplement.referenceTree
  .map((file) => file.path)
  .filter((path) => path.startsWith("examples/") && /\.(mjs|ts)$/.test(path));
assert.deepEqual(examples.sort(), manifest.examples.toSorted());
verifyTree();
const stamp = new Date().toISOString().replaceAll(":", "-");
const output = join(
  root,
  "docs/acceptance/parity",
  `surface-reconciliation-${stamp}`,
);
mkdirSync(output, { recursive: true });
const receipt = {
  schemaVersion: "1.0.0",
  status:
    omissions.length || unresolved.length
      ? "inventory-incomplete"
      : "inventory-reconciled",
  timestamp: stamp,
  supervision,
  referenceEngine: manifest.reference.engine,
  manifestDigest: sha(manifestRaw),
  auditorDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
  referenceTreeFilesVerified: supplement.referenceTree.length,
  counts: {
    exportPaths: Object.keys(pkg.exports).length,
    exportedSymbols: targets.size,
    publicBindings: bindings.length,
    publicClassMembers: members.size,
    cliCommands: parserCommands.length,
    actualCliOptions: parserCommands.reduce(
      (n, row) => n + row.options.length,
      0,
    ),
    examples: examples.length,
    obligationsBeforeReview: baseline.length,
  },
  bindings,
  members: [...members.values()],
  parserCommands,
  omissions,
  unresolved,
  scope:
    "Independent static inventory reconciliation only. Complete declarations remain preserved even where the first frozen type signature was any. This does not verify implementations, consumer compilation or operational equivalence; omissions require an additive frozen supplement and candidate classification.",
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
      omissions,
      unresolved,
    },
    null,
    2,
  ),
);
assert.equal(unresolved.length, 0);
