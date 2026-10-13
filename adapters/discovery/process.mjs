/** Captured-input discovery. Admission and policy decisions stay in Rust. */
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { join, dirname, resolve, isAbsolute, sep } from "node:path";
import {
  configureCanonical,
  canonicalDigest,
} from "patamaps-native-sdk-draft/canonical";
import { configureSssom } from "patamaps-native-sdk-draft/sssom";
import { scientificSkosRelationPack } from "./scientific-relations.js";

const supported = new Map([
  ["typescript-zod", ["typescript-zod.js", "TypeScriptZodAdapter"]],
  ["nextjs-app-router", ["nextjs-app-router.js", "NextjsAppRouterAdapter"]],
  ["prisma", ["prisma.js", "PrismaAdapter"]],
  ["json-collections", ["json-collections.js", "JsonCollectionsAdapter"]],
  ["legacy-sources", ["legacy-sources.js", "LegacySourcesAdapter"]],
  ["sssom-tsv", ["sssom-tsv.js", "SssomTsvAdapter"]],
  ["metamap-shard", ["metamap-shard.js", "MetamapShardAdapter"]],
]);

function capturedPath(path) {
  if (
    typeof path !== "string" ||
    !path ||
    path.includes("\\") ||
    path.includes("\0") ||
    path
      .split("/")
      .some(
        (part) => !part || part === "." || part === ".." || part.includes(":"),
      )
  ) {
    throw new Error("Invalid captured source path");
  }
  return path;
}

function containedConfigPath(path) {
  // Configuration may use '.' and ordinary relative normalization. It may
  // never make a fact provider read outside the supplied captured tree.
  if (
    typeof path !== "string" ||
    !path ||
    path.includes("\\") ||
    path.includes("\0") ||
    isAbsolute(path)
  ) {
    throw new Error(
      "Discovery configuration path must stay within captured inputs",
    );
  }
  const root = resolve("/__patamaps_captured_root__");
  const target = resolve(root, path);
  if (target !== root && !target.startsWith(root + sep)) {
    throw new Error(
      "Discovery configuration path must stay within captured inputs",
    );
  }
}

async function main() {
  // Keep the historical bridge's optional absolute package argument readable
  // for old configurations. No file or module is loaded from that argument.
  let native;
  if (
    process.argv.length === 4 &&
    process.argv[2] === "--native" &&
    isAbsolute(process.argv[3])
  ) {
    native = process.argv[3];
  } else if (
    process.argv.length > 3 ||
    (process.argv[2] !== undefined && !isAbsolute(process.argv[2]))
  ) {
    throw new Error("Unexpected discovery process arguments");
  }
  const chunks = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    bytes += chunk.length;
    if (bytes > 16 * 1024 * 1024)
      throw new Error("Request byte limit exceeded");
    chunks.push(chunk);
  }
  const request = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (
    request.schemaVersion !== "0.1.0" ||
    request.documentType !== "adapter-request" ||
    request.profile !== "patamaps-workspace-draft-1"
  ) {
    throw new Error("Unsupported process protocol");
  }
  const selected = supported.get(request.config.adapter);
  if (!selected) throw new Error("Unsupported optional discovery adapter");
  if (request.config.adapter === "sssom-tsv") {
    if (!native)
      throw new Error(
        "Scientific discovery requires --native and an absolute Patamaps executable",
      );
    configureCanonical(native);
    configureSssom(native);
    if (request.config.metadataPath !== undefined)
      containedConfigPath(request.config.metadataPath);
  }
  if (request.config.adapter === "typescript-zod") {
    if (!Array.isArray(request.config.roots))
      throw new Error("Discovery roots must be an array");
    request.config.roots.forEach(containedConfigPath);
  } else {
    containedConfigPath(
      request.config.adapter === "nextjs-app-router"
        ? request.config.root
        : request.config.path,
    );
  }
  if (
    !Array.isArray(request.inputs) ||
    request.inputs.length === 0 ||
    request.inputs.length > 1024
  ) {
    throw new Error("Invalid captured source inventory");
  }
  const expected = new Map();
  for (const input of request.inputs) {
    const path = capturedPath(input.receipt.path);
    if (typeof input.content !== "string")
      throw new Error("Captured content must be UTF-8 text");
    const digest =
      "sha256:" + createHash("sha256").update(input.content).digest("hex");
    if (
      digest !== input.receipt.digest ||
      Buffer.byteLength(input.content) !== input.receipt.byteLength ||
      expected.has(path)
    ) {
      throw new Error("Invalid captured source receipt");
    }
    expected.set(path, digest);
  }
  // Retain every staging tree. Cleanup is an explicit owner action; discovery
  // must not delete local material as a side effect of a successful call.
  const root = await mkdtemp(join(process.cwd(), ".patamaps-discovery-"));
  for (const input of request.inputs) {
    const path = join(root, input.receipt.path);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, input.content, { flag: "wx" });
  }
  const module = await import(
    new URL("./adapters/" + selected[0], import.meta.url)
  );
  const adapter = new module[selected[1]]();
  const result = await adapter.discover(
    { ...request.config, id: request.sourceId },
    {
      namespace: request.namespace,
      repository: "captured-workspace",
      repositoryRoot: root,
    },
  );
  if (
    result.inputs.length !== expected.size ||
    result.inputs.some((input) => expected.get(input.path) !== input.digest)
  ) {
    throw new Error(
      "Discovery did not consume the exact supplied source inventory",
    );
  }
  const shard = { ...result.document };
  if (!["1.0.0", "2.0.0"].includes(shard.schemaVersion))
    throw new Error("Unsupported legacy envelope");
  delete shard.$schema;
  shard.schemaVersion = "0.1.0";
  shard.documentType = "graph";
  if (adapter.id === "sssom-tsv") {
    const original = scientificSkosRelationPack();
    const converted = {
      ...original,
      schemaVersion: "0.1.0",
      documentType: "relation-pack",
    };
    delete converted.$schema;
    const originalDigest = canonicalDigest(original);
    const convertedDigest = canonicalDigest(converted);
    const changes = [];
    shard.relationPacks = shard.relationPacks.map((pack, index) => {
      if (
        pack.id !== original.id ||
        pack.version !== original.version ||
        pack.digest !== originalDigest
      ) {
        throw new Error(
          "Scientific source pack does not match the pinned compatibility profile",
        );
      }
      changes.push({
        field: `relationPacks[${index}].digest`,
        original: pack.digest,
        converted: convertedDigest,
        reason:
          "The same pinned relation data uses the Patamaps 0.1.0 envelope",
      });
      return { ...pack, digest: convertedDigest };
    });
    shard.metadata = {
      ...shard.metadata,
      patamapsDiscovery: { compatibilityChanges: changes },
    };
  }
  process.stdout.write(
    JSON.stringify({
      schemaVersion: "0.1.0",
      documentType: "adapter-response",
      profile: request.profile,
      sourceId: request.sourceId,
      adapterVersion:
        adapter.id + "@" + adapter.version + "+patamaps-discovery-2",
      requestDigest: request.requestDigest,
      inputs: request.inputs.map((input) => input.receipt),
      shard,
      diagnostics: result.diagnostics.map((diagnostic) => ({
        severity: diagnostic.severity,
        code: diagnostic.code,
        message: diagnostic.message,
      })),
    }),
  );
}

await main();
