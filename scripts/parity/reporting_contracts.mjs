/** Freeze original read-only diff/report outputs before running the candidate. */
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
const pointer = JSON.parse(
  readFileSync(join(root, ".tools/parity/oracles/current.json")),
);
const oracle = join(root, pointer.source);
const supplement = JSON.parse(
  readFileSync(join(root, "fixtures/parity/supplement.json")),
);
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
const corpusPath = join(root, "fixtures/parity/reporting-controls.json");
function perform(api, action) {
  switch (action.operation) {
    case "diff":
      return api.diffMetamapDocuments(
        JSON.parse(action.before),
        JSON.parse(action.after),
      );
    case "empty-diff":
      return api.emptyGraphDiff();
    case "drift-report":
      return api.renderDriftReport(JSON.parse(action.input));
    case "graph-documentation":
      return api.renderGraphDocumentation(
        JSON.parse(action.graph),
        JSON.parse(action.correspondences),
      );
    default:
      throw new Error("Unknown control");
  }
}
if (!existsSync(corpusPath)) {
  const api = {
    ...(await import(pathToFileURL(join(oracle, "dist/diff.js")))),
    ...(await import(pathToFileURL(join(oracle, "dist/report.js")))),
  };
  const cases = [];
  const graph = (changes = {}) => ({
    schemaVersion: "2.0.0",
    id: "urn:test:graph",
    namespace: "test",
    entities: [],
    mappings: [],
    authorities: [],
    ...changes,
  });
  const add = (name, action) =>
    cases.push({ name, action, expected: perform(api, action) });
  const diff = (name, before, after) =>
    add(name, {
      operation: "diff",
      before: typeof before === "string" ? before : JSON.stringify(before),
      after: typeof after === "string" ? after : JSON.stringify(after),
    });
  add("fresh-empty-diff", { operation: "empty-diff" });
  diff("empty", graph(), graph());
  diff(
    "headers-and-packs-ignored",
    graph({ label: "a", relationPacks: [{ id: "a" }] }),
    graph({
      schemaVersion: "unsupported",
      id: "other",
      namespace: "other",
      label: "b",
      metadata: { x: 1 },
      relationPacks: [{ id: "b" }],
    }),
  );
  for (const [field, kind] of [
    ["entities", "entity"],
    ["mappings", "mapping"],
    ["authorities", "authority"],
  ]) {
    diff(
      kind + "-add-remove-change",
      graph({ [field]: [{ id: "z", label: "old" }, { id: "removed" }] }),
      graph({ [field]: [{ id: "added" }, { id: "z", label: "new" }] }),
    );
    diff(
      kind + "-last-duplicate",
      graph({
        [field]: [
          { id: "a", x: 1 },
          { id: "a", x: 2 },
        ],
      }),
      graph({
        [field]: [
          { id: "a", x: 2 },
          { id: "a", x: 3 },
        ],
      }),
    );
  }
  diff(
    "all-kind-phase-sorting",
    graph({
      entities: [{ id: "z" }, { id: "a", label: "old" }],
      mappings: [{ id: "m" }],
      authorities: [{ id: "q" }],
    }),
    graph({
      entities: [{ id: "a", label: "new" }, { id: "b" }],
      mappings: [{ id: "n" }],
      authorities: [{ id: "r" }],
    }),
  );
  diff(
    "last-duplicate-equal",
    graph({
      entities: [
        { id: "a", x: 1 },
        { id: "a", x: 2 },
      ],
    }),
    graph({ entities: [{ id: "a", x: 2 }] }),
  );
  diff(
    "missing-vs-null",
    graph({ entities: [{ id: "a", x: null, y: 1 }] }),
    graph({ entities: [{ id: "a", y: null, z: null }] }),
  );
  diff(
    "negative-zero-number-equality",
    graph({ entities: [{ id: "a", x: -0 }] }),
    graph({ entities: [{ id: "a", x: 0 }] }),
  );
  diff(
    "nested-key-order-equal",
    graph({ entities: [{ id: "a", value: { Z: 1, a: 2, 10: 4, 2: 3 } }] }),
    graph({ entities: [{ value: { 2: 3, 10: 4, a: 2, Z: 1 }, id: "a" }] }),
  );
  diff(
    "array-order-changed",
    graph({ entities: [{ id: "a", value: [1, 2] }] }),
    graph({ entities: [{ id: "a", value: [2, 1] }] }),
  );
  diff(
    "record-raw-duplicate-properties",
    '{"entities":[{"id":"a","x":1,"x":2}],"mappings":[],"authorities":[]}',
    graph({ entities: [{ id: "a", x: 2 }] }),
  );
  const keys = [
    "10",
    "2",
    "a",
    "A",
    "é",
    "é",
    "😀",
    "\ud800",
    "\udfff",
    "\ue000",
    "\u{f0000}",
  ];
  diff(
    "changed-properties-ordinal",
    graph({
      entities: [{ id: "a", ...Object.fromEntries(keys.map((k) => [k, 1])) }],
    }),
    graph({
      entities: [
        {
          id: "a",
          ...Object.fromEntries([...keys].reverse().map((k) => [k, 2])),
        },
      ],
    }),
  );
  for (const [name, keys] of [
    ["case", ["z", "Z", "a", "A"]],
    ["numeric", ["2", "10", "01"]],
    ["canonical", ["é", "é"]],
    ["ignorable", ["a", "a\0", "a\u200d"]],
    ["surrogate", ["\ud800", "\udfff", "\ufffd", "\ue000", "\u{f0000}"]],
    ["nonlatin", ["日", "あ", "Ω", "ж", "한", "中"]],
  ]) {
    for (const reverse of [false, true]) {
      const ids = reverse ? [...keys].reverse() : keys;
      diff(
        "ids-" + name + "-" + reverse,
        graph({ entities: ids.map((id) => ({ id, value: 1 })) }),
        graph({ entities: ids.map((id) => ({ id, value: 2 })) }),
      );
    }
  }
  diff(
    "canonical-key-tie-record-change-empty-properties",
    graph({ entities: [{ id: "a", é: 1, é: 2 }] }),
    graph({ entities: [{ id: "a", é: 2, é: 1 }] }),
  );
  diff(
    "canonical-key-tie-nested-property-change",
    graph({ entities: [{ id: "a", value: { é: 1, é: 2 } }] }),
    graph({ entities: [{ id: "a", value: { é: 2, é: 1 } }] }),
  );
  diff(
    "duplicate-id-retains-first-position-tie",
    graph({
      entities: [
        { id: "é", x: 1 },
        { id: "é", x: 1 },
        { id: "é", x: 2 },
      ],
    }),
    graph({
      entities: [
        { id: "é", x: 2 },
        { id: "é", x: 3 },
      ],
    }),
  );
  let deep = 1;
  for (let n = 0; n < 128; n++) deep = { value: deep };
  diff(
    "deep-128",
    graph({ entities: [{ id: "a", value: deep }] }),
    graph({ entities: [{ id: "a", value: deep }] }),
  );
  const docs = (name, g, correspondences = []) =>
    add(name, {
      operation: "graph-documentation",
      graph: JSON.stringify(g),
      correspondences: JSON.stringify(correspondences),
    });
  docs("documentation-empty", graph());
  docs("documentation-null-fallbacks", graph({ label: null, revision: null }));
  docs(
    "documentation-empty-label-and-revision",
    graph({ label: "", revision: "" }),
  );
  docs(
    "documentation-complete",
    graph({
      label: "Map | label\nsecond",
      revision: "r1",
      entities: [
        { id: "a", kind: "Z" },
        { id: "b", kind: "a" },
        { id: "c", kind: "Z" },
      ],
      mappings: [
        { id: "m", relation: "z" },
        { id: "n", relation: "a" },
      ],
      authorities: [
        { concept: "c", facts: ["type", "presence"], source: "s" },
        { concept: "d", facts: [], source: "t" },
      ],
    }),
    [{ id: "second" }, { id: "first" }],
  );
  for (const reverse of [false, true]) {
    const kinds = [
      "é",
      "é",
      "a",
      "a\0",
      "\ud800",
      "\udfff",
      "\ufffd",
      "\ue000",
      "\u{f0000}",
    ];
    if (reverse) kinds.reverse();
    docs(
      "documentation-locale-ties-utf16-" + reverse,
      graph({
        id: "g\ud800",
        label: "\udfff",
        revision: "\ue000\ue001",
        entities: kinds.map((kind, i) => ({ id: String(i), kind })),
        mappings: kinds.map((relation, i) => ({ id: String(i), relation })),
        authorities: [
          {
            concept: "c\ud800|\n",
            facts: ["x\udfff", "y|\n"],
            source: "s\ud800",
          },
        ],
      }),
      [{ id: "\udfff" }, { id: "a|\n`" }],
    );
  }
  const base = () => ({
    graph: graph(),
    adapters: [],
    driftIssues: [],
    validation: { valid: true, issues: [] },
    diff: api.emptyGraphDiff(),
  });
  const report = (name, input) =>
    add(name, { operation: "drift-report", input: JSON.stringify(input) });
  report("drift-empty-pass", base());
  report("drift-invalid-status-with-no-errors", {
    ...base(),
    validation: { valid: false, issues: [] },
  });
  report("drift-warnings-only", {
    ...base(),
    driftIssues: [
      { severity: "warning", code: "W", message: "warning" },
      { severity: "info", code: "I", message: "info" },
    ],
  });
  const diagnosis = (severity, code, message, extra = {}) => ({
    severity,
    code,
    message,
    ...extra,
  });
  report("drift-complete-fail", {
    ...base(),
    graph: graph({
      entities: [{ id: "a" }],
      mappings: [{ id: "m" }],
      authorities: [{ id: "q" }],
    }),
    adapters: [
      {
        diagnostics: [
          diagnosis("warning", "A|\n", "one|\n\r\\", {
            subjectId: "",
            path: "ignored",
          }),
          diagnosis("error", "B", "two", { subjectId: null, path: "fallback" }),
        ],
      },
      { diagnostics: [diagnosis("error", "C", "three", { path: "p|\n" })] },
    ],
    driftIssues: [
      diagnosis("error", "D", "four", { correspondenceId: "c|\n" }),
      diagnosis("info", "I", "info"),
    ],
    validation: {
      valid: true,
      issues: [
        diagnosis("warning", "V", "five", { subjectId: "v" }),
        diagnosis("error", "E", "six"),
      ],
    },
    diff: {
      changes: [
        {
          change: "changed",
          kind: "entity",
          id: "a|\n",
          changedProperties: ["x|\n", "y\r"],
        },
        { change: "added", kind: "mapping", id: "m" },
        {
          change: "removed",
          kind: "authority",
          id: "q",
          changedProperties: [],
        },
      ],
      counts: { added: 91, removed: 92, changed: 93 },
    },
    cacheHits: ["a", "a", "b"],
  });
  for (const count of [1, 3, 30, 31, 60]) {
    for (const section of ["drift", "adapter", "validation"]) {
      const entries = Array.from({ length: count }, (_, i) =>
        diagnosis(
          i % 3 === 0 ? "error" : i % 3 === 1 ? "warning" : "info",
          "code-" + (i % 2),
          `message-${i}|\n`,
          i % 4 === 0
            ? { correspondenceId: "", subjectId: "" }
            : i % 4 === 1
              ? {
                  correspondenceId: `c-${i}`,
                  subjectId: `s-${i}`,
                  path: "ignored",
                }
              : i % 4 === 2
                ? { path: `p-${i}` }
                : { correspondenceId: null, subjectId: null, path: null },
        ),
      );
      const value = base();
      if (section === "drift") value.driftIssues = entries;
      else if (section === "adapter")
        value.adapters = [
          { diagnostics: entries.slice(0, 10) },
          { diagnostics: entries.slice(10) },
        ];
      else value.validation.issues = entries;
      report(`drift-grouping-${section}-${count}`, value);
    }
  }
  report("drift-group-key-collision", {
    ...base(),
    driftIssues: Array.from({ length: 31 }, (_, i) =>
      diagnosis(i % 2 ? "x\0y" : "x", i % 2 ? "z" : "y\0z", "m-" + i, {
        correspondenceId: "s-" + i,
      }),
    ),
  });
  report("drift-utf16-escaping", {
    ...base(),
    driftIssues: [
      diagnosis("error", "c\ud800|\n", "m\udfff|\n\r\\", {
        correspondenceId: "s\ud800",
      }),
    ],
    validation: {
      valid: false,
      issues: [
        diagnosis("warning", "v\udfff", "\ue000\ue001", { path: "p\ud800" }),
      ],
    },
    diff: {
      changes: [
        {
          change: "changed",
          kind: "entity",
          id: "i\ud800|\n",
          changedProperties: ["\udfff", "é", "é"],
        },
      ],
      counts: { added: 0, removed: 0, changed: 1 },
    },
  });
  verifyTree();
  writeFileSync(
    corpusPath,
    JSON.stringify(
      {
        schemaVersion: "1.0.0",
        referenceEngine: supplement.referenceEngine,
        originalRuntime: process.version,
        originalIcu: process.versions.icu,
        originalCollation: new Intl.Collator().resolvedOptions(),
        originalArtifacts: [
          "dist/diff.js",
          "dist/report.js",
          "dist/stable.js",
        ].map((path) => ({
          path,
          digest: sha(readFileSync(join(oracle, path))),
        })),
        scope:
          "Finite read-only JSON diff and complete UTF-16 report text observations. Arbitrary JavaScript, exhaustive locales/ICU versions, resource, package and Linux architecture obligations remain open.",
        cases,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
}
const corpus = JSON.parse(readFileSync(corpusPath));
assert.equal(corpus.referenceEngine, supplement.referenceEngine);
assert.equal(
  corpus.originalCollation.locale,
  new Intl.Collator().resolvedOptions().locale,
);
for (const item of corpus.originalArtifacts)
  assert.equal(sha(readFileSync(join(oracle, item.path))), item.digest);
if (process.argv.includes("--freeze-only")) {
  textOutput({
    status: "original-observations-frozen",
    cases: corpus.cases.length,
    corpusDigest: sha(readFileSync(corpusPath)),
  });
  process.exit(0);
}
assert.equal(process.argv.length, 2);
const output = join(
  root,
  "docs/acceptance/parity",
  `reporting-controls-${new Date().toISOString().replaceAll(":", "-")}`,
);
mkdirSync(output, { recursive: true });
const trace = join(output, "native-executions.ndjson");
const cli = join(root, "target/debug/patamaps");
const { createLegacyValidationApi } = await import(
  pathToFileURL(join(root, "sdk/typescript/legacy-validation.mjs"))
);
let caseName;
const facade = createLegacyValidationApi(cli, (execution) =>
  appendFileSync(trace, JSON.stringify({ caseName, ...execution }) + "\n"),
);
const api = {
  diffMetamapDocuments: facade.diffLegacyDocuments,
  emptyGraphDiff: facade.emptyLegacyGraphDiff,
  renderDriftReport: facade.renderLegacyDriftReport,
  renderGraphDocumentation: facade.renderLegacyGraphDocumentation,
};
const results = corpus.cases.map((test) => {
  caseName = test.name;
  let observed,
    matched = true,
    error;
  try {
    observed = perform(api, test.action);
    assert.deepEqual(observed, test.expected);
  } catch (failure) {
    matched = false;
    error = { name: failure.name, message: failure.message };
  }
  return { name: test.name, matched, observed, ...(error ? { error } : {}) };
});
caseName = "fresh-result-and-input-preservation";
const first = api.emptyGraphDiff();
first.changes.push({ change: "added", kind: "entity", id: "mutation" });
first.counts.added = 3;
assert.deepEqual(api.emptyGraphDiff(), {
  changes: [],
  counts: { added: 0, removed: 0, changed: 0 },
});
const g = {
  entities: [{ id: "a", value: "\ud800", label: undefined }],
  mappings: [],
  authorities: [],
};
const descriptor = Object.getOwnPropertyDescriptor(g.entities[0], "label");
api.diffMetamapDocuments(g, g);
assert.deepEqual(
  Object.getOwnPropertyDescriptor(g.entities[0], "label"),
  descriptor,
);
assert.equal(g.entities[0].value, "\ud800");
verifyTree();
const executions = readFileSync(trace, "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
assert.equal(executions.length, corpus.cases.length + 3);
assert(
  executions.every(
    (call) =>
      call.command[0] === cli &&
      call.command.slice(1).join(" ") === "legacy reporting json" &&
      !call.processError &&
      !call.signal,
  ),
);
const matched = results.filter((row) => row.matched).length;
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
      "legacy-reporting.mjs",
      "legacy-reporting.d.ts",
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
  scope: corpus.scope,
  results,
  traceDigest: sha(readFileSync(trace)),
  driverDigest: sha(readFileSync(fileURLToPath(import.meta.url))),
};
writeFileSync(
  join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
writeFileSync(
  join(root, ".tools/parity/current-reporting-controls.json"),
  JSON.stringify(
    { receipt: relative(root, join(output, "receipt.json")) },
    null,
    2,
  ) + "\n",
);
textOutput({
  receipt: relative(root, join(output, "receipt.json")),
  counts: receipt.counts,
});
process.exitCode = matched === results.length ? 0 : 1;
function textOutput(value) {
  process.stdout.write(JSON.stringify(value) + "\n");
}
