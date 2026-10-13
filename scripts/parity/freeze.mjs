/** Freeze the pinned public surface and expanded reference cases, without running tests. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, relative, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const ENGINE = "399747a4ad05a37cd8db1cedd53048fad2175be4";
const reference = resolve(process.argv[2] ?? "/Users/admin/dev/SEEDZ/metamap");
const check = process.argv.includes("--check");
const inspect = process.argv.includes("--inspect");
const require = createRequire(join(reference, "package.json"));
const ts = require("typescript");
const digest = (raw) =>
  "sha256:" + createHash("sha256").update(raw).digest("hex");
const git = (args) =>
  execFileSync("git", ["-C", reference, ...args], {
    maxBuffer: 32 * 1024 * 1024,
  });
const paths = git(["ls-tree", "-r", "--name-only", ENGINE])
  .toString()
  .trim()
  .split("\n");
const rawCache = new Map();
function original(path) {
  if (!rawCache.has(path))
    rawCache.set(path, git(["show", `${ENGINE}:${path}`]));
  return rawCache.get(path);
}
assert.equal(
  git(["status", "--porcelain"]).length,
  0,
  "Reference checkout must remain clean",
);
const pkg = JSON.parse(original("package.json"));
assert.equal(pkg.name, "@roryscot/metamap");
assert.equal(pkg.version, "0.7.1");
assert.equal(Object.keys(pkg.exports).length, 92);
const sourcePaths = paths.filter(
  (p) =>
    p.startsWith("src/") && p.endsWith(".ts") && !p.includes("/__tests__/"),
);
for (const p of sourcePaths)
  assert.deepEqual(
    readFileSync(join(reference, p)),
    original(p),
    `Local production source differs: ${p}`,
  );
const program = ts.createProgram(
  sourcePaths.map((p) => join(reference, p)),
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
const obligations = new Map();
const exported = [];
const surfaceFiles = new Set([
  "package.json",
  "src/index.ts",
  "src/cli.ts",
  ".github/workflows/ci.yml",
]);
function workstream(path) {
  const name = path.split("/").at(-1);
  if (/counterfactual|replay|provenance/.test(name)) return "P1";
  if (/sssom|scientific/.test(name) && !path.includes("/adapters/"))
    return "P2";
  if (path.includes("/adapters/")) return "P4";
  if (
    /workspace|config|correspondence|report|legacy|source-cli|current-sources/.test(
      name,
    )
  )
    return "P3";
  if (/projection|path-tree|typed-native|consumer-bindings/.test(name))
    return "P5";
  return "P7";
}
function strategy(path, category) {
  if (category === "type")
    return "Compile an external TypeScript/Rust consumer against the mapped public types; parsed wire values cannot construct checked capability states.";
  if (
    /native\.test|protected-activation|governed-activation|activation\.test/.test(
      path,
    )
  )
    return "Execute the original generated-consumer or actual Linux filesystem/UID/transaction obligations on the required host with assertions retained.";
  if (
    /adapter|workspace|current-sources|source-cli|scientific-source/.test(path)
  )
    return "Execute discovery/configuration/drift operations in a retained isolated fixture tree; compare exact facts, diagnostics, receipts and filesystem effects.";
  return "Invoke the Rust-backed mapped operation on the frozen original inputs; compare complete results, refusals and unknown states under the explicit compatibility rules.";
}
function add(identity, item) {
  const id = `parity:${digest(identity).slice(7, 27)}`;
  assert(!obligations.has(id), `Duplicate identity ${identity}`);
  const row = {
    id,
    identity,
    status: "unclassified",
    candidateEvidence: [],
    ...item,
  };
  obligations.set(id, row);
  return id;
}
function location(node) {
  const file = node.getSourceFile();
  const path = relative(reference, file.fileName).replaceAll("\\", "/");
  const start = file.getLineAndCharacterOfPosition(node.getStart(file));
  surfaceFiles.add(path);
  return {
    path,
    digest: digest(original(path)),
    line: start.line + 1,
    column: start.character + 1,
  };
}
function exportedSymbol(symbol, exportPath) {
  if (symbol.flags & ts.SymbolFlags.Alias)
    symbol = checker.getAliasedSymbol(symbol);
  const declarations =
    symbol.declarations?.filter((d) =>
      d.getSourceFile().fileName.startsWith(join(reference, "src/")),
    ) ?? [];
  if (!declarations.length) return null;
  const declaration = declarations[0];
  const loc = location(declaration);
  const name = symbol.getName();
  const category = symbol.flags & ts.SymbolFlags.Value ? "value" : "type";
  const identity = `symbol:${loc.path}:${name}:${category}`;
  let id = [...obligations.values()].find((o) => o.identity === identity)?.id;
  if (!id) {
    id = add(identity, {
      kind: "exported-symbol",
      name,
      category,
      origin: loc,
      signature: checker.typeToString(
        checker.getTypeOfSymbolAtLocation(symbol, declaration),
        undefined,
        ts.TypeFormatFlags.NoTruncation,
      ),
      exportPaths: [],
      workstream: category === "type" ? "P6" : workstream(loc.path),
      verificationStrategy: strategy(loc.path, category),
      candidateEntryPoint: {
        kind: "mapped-public-api",
        referenceModule: loc.path,
        symbol: name,
      },
      expectation: {
        kind: "pinned-declaration",
        declarationDigest: digest(declaration.getText()),
        description:
          "Public behavior and type obligations are frozen by the original declaration and associated reference cases; no candidate pass is inferred.",
      },
    });
    if (ts.isClassDeclaration(declaration)) {
      for (const member of declaration.members) {
        if (
          member.modifiers?.some(
            (m) =>
              m.kind === ts.SyntaxKind.PrivateKeyword ||
              m.kind === ts.SyntaxKind.ProtectedKeyword,
          )
        )
          continue;
        if (member.name && ts.isPrivateIdentifier(member.name)) continue;
        const memberName = ts.isConstructorDeclaration(member)
          ? "constructor"
          : member.name?.getText();
        if (!memberName) continue;
        const memberIdentity = `member:${loc.path}:${name}.${memberName}:${member.modifiers?.some((m) => m.kind === ts.SyntaxKind.StaticKeyword) ? "static" : "instance"}`;
        if (
          [...obligations.values()].some((o) => o.identity === memberIdentity)
        )
          continue;
        add(memberIdentity, {
          kind: "class-member",
          name: `${name}.${memberName}`,
          origin: location(member),
          parent: id,
          workstream: workstream(loc.path),
          verificationStrategy: strategy(loc.path, "value"),
          candidateEntryPoint: {
            kind: "mapped-public-api",
            referenceModule: loc.path,
            symbol: `${name}.${memberName}`,
          },
          expectation: {
            kind: "pinned-declaration",
            declarationDigest: digest(member.getText()),
            description:
              "Preserve observable public member behavior through a documented Rust/API mapping.",
          },
        });
      }
    }
  }
  const row = obligations.get(id);
  if (!row.exportPaths.includes(exportPath)) row.exportPaths.push(exportPath);
  return id;
}
for (const [name, target] of Object.entries(pkg.exports)) {
  const file =
    typeof target === "string"
      ? target.replace(/^\.\//, "")
      : target.import.replace(/^\.\/dist\//, "src/").replace(/\.js$/, ".ts");
  assert(paths.includes(file), `Unresolved published path: ${file}`);
  surfaceFiles.add(file);
  const row = { path: name, file, digest: digest(original(file)), symbols: [] };
  if (file.endsWith(".ts")) {
    const module = checker.getSymbolAtLocation(
      program.getSourceFile(join(reference, file)),
    );
    assert(module, file);
    row.symbols = checker
      .getExportsOfModule(module)
      .map((s) => exportedSymbol(s, name))
      .filter(Boolean)
      .sort();
  } else {
    row.obligation = add(`published:${name}`, {
      kind: "published-data",
      name,
      origin: { path: file, digest: row.digest },
      workstream: file.startsWith("schemas/") ? "P3" : "P7",
      verificationStrategy:
        "Validate valid/invalid legacy inputs and preserve the original published bytes and digest convention in the compatibility profile.",
      candidateEntryPoint: { kind: "legacy-contract-import", path: file },
      expectation: { kind: "exact-source-bytes", digest: row.digest },
    });
  }
  exported.push(row);
}
const cli = original("src/cli.ts").toString();
const commands = [...cli.matchAll(/^  metamap ([a-z-]+)([^\n]*)$/gm)].map(
  (m) => ({
    command: m[1],
    usage: m[0].trim(),
    flags: [...new Set(m[2].match(/--[a-z-]+/g) ?? [])].sort(),
  }),
);
assert(commands.length > 15, "CLI inventory is unexpectedly incomplete");
for (const command of commands) {
  command.obligation = add(`cli:${command.command}`, {
    kind: "cli-command",
    name: command.command,
    origin: { path: "src/cli.ts", digest: digest(original("src/cli.ts")) },
    workstream: "P3",
    verificationStrategy:
      "Execute the mapped native command with each documented argument/format/flag and compare status, complete output and filesystem effects.",
    candidateEntryPoint: {
      kind: "native-cli",
      referenceCommand: command.command,
    },
    expectation: {
      kind: "pinned-cli-contract",
      usage: command.usage,
      flags: command.flags,
    },
  });
  command.flagObligations = command.flags.map((flag) =>
    add(`cli:${command.command}:${flag}`, {
      kind: "cli-option",
      name: `${command.command} ${flag}`,
      parent: command.obligation,
      origin: { path: "src/cli.ts", digest: digest(original("src/cli.ts")) },
      workstream: "P3",
      verificationStrategy:
        "Exercise valid, invalid, repeated and omitted arguments for this option against the actual native command.",
      candidateEntryPoint: {
        kind: "native-cli-option",
        referenceCommand: command.command,
        option: flag,
      },
      expectation: { kind: "pinned-cli-contract", usage: command.usage },
    }),
  );
}
const caseReportPath = "docs/acceptance/full-reference/reference-vitest.json";
const reportRaw = readFileSync(join(ROOT, caseReportPath));
const report = JSON.parse(reportRaw);
assert(
  report.success && report.numFailedTests === 0,
  "Require the identified successful reference report",
);
const corpus = JSON.parse(
  readFileSync(join(ROOT, "fixtures/conformance.json")),
);
const suitePins = new Map(corpus.suites.map((s) => [s.path, s.sha256]));
assert.equal(suitePins.size, 53);
const suites = [];
const unmatched = [];
for (const suite of report.testResults) {
  const path = suite.name.slice(suite.name.lastIndexOf("/src/__tests__/") + 1);
  assert(suitePins.has(path), `Unexpected reference suite ${path}`);
  const raw = original(path),
    source = ts.createSourceFile(
      path,
      raw.toString(),
      ts.ScriptTarget.Latest,
      true,
    );
  assert.equal(
    digest(raw).slice(7),
    suitePins.get(path),
    `Original suite hash drift: ${path}`,
  );
  surfaceFiles.add(path);
  const declarations = [];
  function walk(node) {
    if (
      ts.isCallExpression(node) &&
      node.arguments.length >= 2 &&
      ts.isStringLiteralLike(node.arguments[0])
    ) {
      const callee = node.expression.getText(source);
      if (/^(it|test)(\.|\(|$)/.test(callee)) {
        const title = node.arguments[0].text;
        const callback = node.arguments.find(
          (n) => ts.isArrowFunction(n) || ts.isFunctionExpression(n),
        );
        if (callback) {
          const assertions = [];
          function findAssertion(n) {
            if (
              ts.isCallExpression(n) &&
              /^(expect\(|assert\.)/.test(n.getText(source))
            ) {
              const parentIsAssertion =
                ts.isCallExpression(n.parent) &&
                /^(expect\(|assert\.)/.test(n.parent.getText(source));
              if (!parentIsAssertion) assertions.push(n.getText(source));
            }
            ts.forEachChild(n, findAssertion);
          }
          findAssertion(callback);
          declarations.push({
            title,
            line:
              source.getLineAndCharacterOfPosition(node.getStart(source)).line +
              1,
            invocation: node.getText(source),
            invocationDigest: digest(node.getText(source)),
            assertions,
            callbackDigest: digest(callback.getText(source)),
            parameterExpression: ts.isCallExpression(node.expression)
              ? node.expression.arguments.map((x) => x.getText(source))
              : [],
          });
        }
      }
    }
    ts.forEachChild(node, walk);
  }
  walk(source);
  const occurrences = new Map();
  const cases = [];
  for (const [index, result] of suite.assertionResults.entries()) {
    const title = result.title;
    const titlePattern = (rawTitle) =>
      new RegExp(
        "^" +
          rawTitle
            .split(/(%[a-zA-Z#]|\$[A-Za-z_][\w.]*)/)
            .map((piece) =>
              /^(%[a-zA-Z#]|\$[A-Za-z_][\w.]*)$/.test(piece)
                ? "[\\s\\S]*"
                : piece.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
            )
            .join("") +
          "$",
      );
    const exactMatches = declarations.filter((d) => d.title === title);
    const matches = exactMatches.length
      ? exactMatches
      : declarations.filter((d) => titlePattern(d.title).test(title));
    const occurrence = occurrences.get(result.fullName) ?? 0;
    occurrences.set(result.fullName, occurrence + 1);
    if (matches.length !== 1)
      unmatched.push({ path, title, matches: matches.map((d) => d.line) });
    const reference = matches.length === 1 ? matches[0] : null;
    const caseId = add(`case:${path}:${result.fullName}:${occurrence}`, {
      kind: "reference-test-case",
      name: result.fullName,
      origin: { path, digest: digest(raw), line: reference?.line ?? null },
      workstream: workstream(path),
      verificationStrategy: strategy(path, "value"),
      candidateEntryPoint: {
        kind: "original-case-through-rust",
        path,
        fullName: result.fullName,
        occurrence,
      },
      status: "unclassified",
      inputIdentity: {
        sourceDigest: digest(raw),
        ordinal: index,
        expandedTitle: title,
        occurrence,
        invocationDigest: reference?.invocationDigest ?? null,
        parameterExpression: reference?.parameterExpression ?? null,
      },
      expectation: {
        kind: "original-test-assertions",
        expressions: reference?.assertions ?? [],
        callbackDigest: reference?.callbackDigest ?? null,
        scope:
          "Original assertion source and parameter expression; runtime inputs/results must be recorded when the actual candidate case executes.",
      },
      referenceObservation: {
        report: caseReportPath,
        reportDigest: digest(reportRaw),
        status: result.status,
        rerun: false,
      },
      hostRequirements: /protected-activation/.test(path)
        ? [
            "Linux",
            "independent UIDs",
            "protected local filesystem",
            "SIGKILL phases",
          ]
        : [
            "portable unless individual original case specifies a host requirement",
          ],
    });
    cases.push(caseId);
  }
  suites.push({
    path,
    digest: digest(raw),
    declarations: declarations.map((d) => ({
      title: d.title,
      line: d.line,
      invocationDigest: d.invocationDigest,
    })),
    cases,
  });
}
assert.equal(suites.length, 53);
assert.equal(
  suites.reduce((n, s) => n + s.cases.length, 0),
  report.numTotalTests,
);
const adapterFiles = paths.filter(
  (p) => p.startsWith("src/adapters/") && p.endsWith(".ts"),
);
const registrySource = original("src/adapters/registry.ts").toString();
const builtInAdapters = [
  ...registrySource.matchAll(/\.register\(new (\w+)\(\)\)/g),
].map((m) => m[1]);
assert.equal(builtInAdapters.length, 7);
const examples = paths.filter(
  (p) => p.startsWith("examples/") && /\.(mjs|ts)$/.test(p),
);
for (const path of examples) {
  surfaceFiles.add(path);
  add(`example:${path}`, {
    kind: "example-consumer",
    name: path,
    origin: { path, digest: digest(original(path)) },
    workstream: "P9",
    verificationStrategy:
      "Build and execute the independently owned example/consumer using the packaged Rust-backed candidate; preserve existing expected outcomes.",
    candidateEntryPoint: { kind: "installed-example", path },
    expectation: {
      kind: "pinned-consumer-source",
      digest: digest(original(path)),
    },
  });
}
const schemaPaths = paths.filter(
  (p) => p.startsWith("schemas/") && p.endsWith(".json"),
);
const packPaths = paths.filter(
  (p) => p.startsWith("relation-packs/") && p.endsWith(".json"),
);
for (const path of [...schemaPaths, ...packPaths]) surfaceFiles.add(path);
const manifest = {
  schemaVersion: "1.0.0",
  purpose:
    "Frozen public/reference obligation denominator; no candidate pass is inferred from inventory or historical reference results.",
  reference: {
    repository: "https://github.com/roryscot/metamap",
    package: pkg.name,
    version: pkg.version,
    engine: ENGINE,
    buildRecord: "6a6a9d2415df85504a83fce4fd7291d0391c0d17",
  },
  candidateBaseline: "d519705664f95d8a614f870868faf0b311eb6953",
  statusValues: [
    "unclassified",
    "missing",
    "implemented-unverified",
    "verified-equivalent",
    "proposed-deviation",
    "owner-accepted-deviation",
  ],
  inventoryMethod: {
    exports:
      "TypeScript compiler symbol graph, aliases, public class members and package exports",
    tests:
      "Previously executed expanded Vitest cases linked to pinned original AST invocations/assertions; not rerun",
    limitations: [
      "Source assertions are frozen, not replaced with candidate-generated expected values.",
      "Ambiguous/unmatched AST case origins remain unclassified and block P0.",
      "Host requirements and runnable candidate adapters require obligation-level review.",
    ],
  },
  packageExports: exported,
  cli: commands,
  builtInAdapters,
  adapterSourceFiles: adapterFiles,
  examples,
  schemas: schemaPaths.map((path) => ({
    path,
    digest: digest(original(path)),
  })),
  relationPacks: packPaths.map((path) => ({
    path,
    digest: digest(original(path)),
  })),
  referenceSourceFiles: [...surfaceFiles]
    .sort()
    .map((path) => ({ path, digest: digest(original(path)) })),
  suites: suites.sort((a, b) =>
    a.path < b.path ? -1 : a.path > b.path ? 1 : 0,
  ),
  obligations: [...obligations.values()].sort((a, b) =>
    a.identity < b.identity ? -1 : a.identity > b.identity ? 1 : 0,
  ),
  unresolvedCaseOrigins: unmatched,
};
const output = join(ROOT, "fixtures/parity/manifest.json");
const serialized = JSON.stringify(manifest, null, 2) + "\n";
if (inspect) {
  console.log(JSON.stringify({ unresolvedCaseOrigins: unmatched }, null, 2));
} else if (check)
  assert.equal(
    readFileSync(output, "utf8"),
    serialized,
    "Frozen parity denominator changed; review the source/classification change explicitly",
  );
else {
  assert(
    !existsSync(output),
    "Preserve the frozen inventory; use --check or an explicitly reviewed new snapshot",
  );
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, serialized);
}
console.log(
  JSON.stringify(
    {
      status: unmatched.length
        ? "inventory-with-unclassified-case-origins"
        : "inventory-frozen",
      output: relative(ROOT, output),
      exportPaths: exported.length,
      exportedSymbolObligations: [...obligations.values()].filter(
        (x) => x.kind === "exported-symbol",
      ).length,
      publicClassMembers: [...obligations.values()].filter(
        (x) => x.kind === "class-member",
      ).length,
      cliCommands: commands.length,
      suites: suites.length,
      expandedCases: report.numTotalTests,
      obligations: obligations.size,
      unresolvedCaseOrigins: unmatched.length,
      candidatePasses: 0,
    },
    null,
    2,
  ),
);
