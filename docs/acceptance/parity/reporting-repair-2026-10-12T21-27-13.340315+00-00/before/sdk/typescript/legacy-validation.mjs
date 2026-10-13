import { execFile, spawnSync } from "node:child_process";
import { isAbsolute, resolve } from "node:path";
import {
  CanonicalJsonError,
  marshalJson,
  marshalLegacyPackJson,
} from "./canonical.mjs";
import {
  createLegacyRegistryClass,
  bindLegacyRegistryGraphSnapshot,
} from "./legacy-registry.mjs";
import {
  createLegacyGraphClass,
  marshalLegacyGraphRequest,
} from "./legacy-graph.mjs";
import {
  createLegacyComposer,
  LegacyCompositionError,
} from "./legacy-composition.mjs";
export { LegacyCompositionError } from "./legacy-composition.mjs";
export { LegacyGraphValidationError } from "./legacy-graph.mjs";

/** Reports describe legacy JSON data. They do not admit a generation. */
export function createLegacyValidationApi(executable, observeExecution) {
  if (!isAbsolute(executable))
    throw new TypeError("Patamaps requires an absolute native executable");
  function finish(command, input, result) {
    observeExecution?.({
      command,
      input,
      exitCode: result.status,
      signal: result.signal,
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
      processError: result.error?.message ?? null,
    });
    if (result.error) throw result.error;
    const report = JSON.parse(result.stdout);
    if (result.status !== 0) {
      const code = report.error?.code ?? "LEGACY_REGISTRY_INPUT";
      const message =
        report.error?.message ?? "Legacy registry request refused";
      const canonicalPackRefusal =
        ["pack", "pack-file"].includes(command[2]) &&
        [
          "DUPLICATE_JSON_KEY",
          "INVALID_JSON_UNICODE",
          "INVALID_JSON_VALUE",
          "JSON_DEPTH_LIMIT",
        ].includes(code);
      const fileSyntaxRefusal =
        command[2] === "pack-file" && code === "INVALID_JSON_SYNTAX";
      const error = fileSyntaxRefusal
        ? new SyntaxError(message)
        : canonicalPackRefusal
          ? new CanonicalJsonError(code, message)
          : command[2] === "compose" &&
              report.error?.name === "MetamapCompositionError"
            ? new LegacyCompositionError(message, report.error.identifier)
            : (["graph", "compose"].includes(command[2]) ||
                  (command[2] === "pack" && command[3] === "digest")) &&
                report.error?.name === "TypeError"
              ? new TypeError(message)
              : new Error(message);
      if (!(
        ["registry", "graph", "compose"].includes(command[2]) ||
        (command[2] === "pack" &&
          command[3] === "digest" &&
          report.error?.name === "TypeError") ||
        (command[2] === "pack-file" &&
          (fileSyntaxRefusal || code === "LEGACY_PACK_SCHEMA"))
      ))
        error.code = code;
      for (const field of ["path", "errno", "syscall"])
        if (report.error?.[field] !== undefined)
          error[field] = report.error[field];
      error.report = report;
      throw error;
    }
    return report;
  }
  function invoke(namespace, operation, request) {
    const input =
      namespace === "pack"
        ? marshalLegacyPackJson(request)
        : namespace === "graph"
          ? marshalLegacyGraphRequest(request)
          : marshalJson(request);
    const command = [executable, "legacy", namespace, operation];
    if (namespace === "pack" && operation === "digest")
      command.push("--locale", new Intl.Collator().resolvedOptions().locale);
    const result = spawnSync(executable, command.slice(1), {
      input,
      encoding: "utf8",
      env: {},
      timeout: 65_000,
      maxBuffer: 16 * 1024 * 1024 + 1,
    });
    return finish(command, input, result);
  }
  async function load(path) {
    const command = [executable, "legacy", "pack-file", "parse", resolve(path)];
    return await new Promise((accept, reject) => {
      execFile(
        executable,
        command.slice(1),
        {
          encoding: "utf8",
          env: {},
          timeout: 65_000,
          maxBuffer: 16 * 1024 * 1024 + 1,
        },
        (error, stdout, stderr) => {
          // A nonzero native status supplies a structured refusal. Launch,
          // timeout and buffer failures remain child-process errors.
          const nativeRefusal = error && typeof error.code === "number";
          try {
            accept(
              finish(command, "", {
                status: error ? (nativeRefusal ? error.code : null) : 0,
                signal: error?.signal ?? null,
                stdout,
                stderr,
                error: error && !nativeRefusal ? error : undefined,
              }),
            );
          } catch (failure) {
            reject(failure);
          }
        },
      );
    });
  }
  let corePack;
  const core = () =>
    (corePack ??= JSON.parse(
      invoke("registry", "json", { action: { operation: "core-pack" } }),
    ));
  const Registry = createLegacyRegistryClass(invoke, core);
  const Graph = createLegacyGraphClass(invoke, Registry);
  return Object.freeze({
    LegacyRelationRegistry: Registry,
    LegacyGraph: Graph,
    composeLegacyDocuments: createLegacyComposer(invoke),
    get legacyCoreRelationPack() {
      return core();
    },
    validateLegacyDocument(document, options = {}) {
      if (
        Object.keys(options).some(
          (key) => key !== "nativePacks" && key !== "legacyPacks",
        )
      )
        throw new TypeError(
          "Legacy validation accepts nativePacks or legacyPacks options",
        );
      if (
        options.nativePacks !== undefined &&
        options.legacyPacks !== undefined
      )
        throw new TypeError(
          "Supply either nativePacks or legacyPacks, not both",
        );
      const request = { document };
      if (options.nativePacks !== undefined)
        request.packs = options.nativePacks;
      if (options.legacyPacks !== undefined)
        request.legacyPacks = options.legacyPacks;
      return invoke("json", "validate", request);
    },
    validateLegacyDocumentShape(document) {
      return invoke("json", "shape", { document });
    },
    parseLegacyRelationPack(value) {
      invoke("pack", "parse", value);
      // Preserve the parser's caller-owned object identity; no JS validation
      // or semantic interpretation happens in this transport.
      return value;
    },
    importLegacyRelationPack(value) {
      return invoke("pack", "import", value);
    },
    digestLegacyRelationPack(value) {
      return invoke("pack", "digest", value);
    },
    loadLegacyRelationPack(path) {
      return load(path);
    },
  });
}

let configured;
export function configureLegacyValidation(executable, observeExecution) {
  configured = createLegacyValidationApi(executable, observeExecution);
}
function api() {
  if (!configured)
    configureLegacyValidation(process.env.PATAMAPS_EXECUTABLE ?? "");
  return configured;
}
export const validateLegacyDocument = (document, options) =>
  api().validateLegacyDocument(document, options);
export const validateLegacyDocumentShape = (document) =>
  api().validateLegacyDocumentShape(document);
export const parseLegacyRelationPack = (value) =>
  api().parseLegacyRelationPack(value);
export const importLegacyRelationPack = (value) =>
  api().importLegacyRelationPack(value);
export const digestLegacyRelationPack = (value) =>
  api().digestLegacyRelationPack(value);
export const loadLegacyRelationPack = (path) =>
  api().loadLegacyRelationPack(path);
export const composeLegacyDocuments = (documents, options) =>
  api().composeLegacyDocuments(documents, options);

/** Configured convenience class with the same public registry methods. */
export class LegacyRelationRegistry {
  #registry;
  constructor(packs) {
    this.#registry = new (api().LegacyRelationRegistry)(packs);
    bindLegacyRegistryGraphSnapshot(this, this.#registry);
  }
  registerPack(pack) {
    return this.#registry.registerPack(pack);
  }
  getPack(id) {
    return this.#registry.getPack(id);
  }
  getLaw(id) {
    return this.#registry.getLaw(id);
  }
  executablePacks() {
    return this.#registry.executablePacks();
  }
  get(id) {
    return this.#registry.get(id);
  }
  hasPack(id, version) {
    return this.#registry.hasPack(id, version);
  }
  all() {
    return this.#registry.all();
  }
  allPacks() {
    return this.#registry.allPacks();
  }
}
export const legacyCoreRelationPack = () => api().legacyCoreRelationPack;

export class LegacyGraph {
  #graph;
  constructor(document, options = {}) {
    const registry = options.registry ?? new LegacyRelationRegistry();
    this.#graph = new (api().LegacyGraph)(document, { ...options, registry });
    this.document = this.#graph.document;
    this.registry = this.#graph.registry;
    this.validationIssues = this.#graph.validationIssues;
  }
  static from(value, options = {}) {
    const registry = options.registry ?? new LegacyRelationRegistry();
    new (api().LegacyGraph)(value, { ...options, registry, validate: true });
    return new this(value, { ...options, registry, validate: false });
  }
  getEntity(id) {
    return this.#graph.getEntity(id);
  }
  getMapping(id) {
    return this.#graph.getMapping(id);
  }
  mappingsFor(id, options) {
    return this.#graph.mappingsFor(id, options);
  }
  neighbors(id, options) {
    return this.#graph.neighbors(id, options);
  }
  trace(id, options) {
    return this.#graph.trace(id, options);
  }
  resolveAuthority(concept, fact) {
    return this.#graph.resolveAuthority(concept, fact);
  }
}
