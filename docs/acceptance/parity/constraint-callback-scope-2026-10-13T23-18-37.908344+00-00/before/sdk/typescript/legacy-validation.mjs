import { execFile, spawn } from "node:child_process";
import { spawnWithInputSync } from "./native-input.mjs";
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
  LegacyGraphValidationError,
  marshalLegacyGraphRequest,
} from "./legacy-graph.mjs";
import {
  createLegacyComposer,
  LegacyCompositionError,
} from "./legacy-composition.mjs";
import { createLegacyReportingApi } from "./legacy-reporting.mjs";
import { createLegacyCorrespondenceApi } from "./legacy-correspondence.mjs";
import { createLegacyCliApi } from "./legacy-cli.mjs";
import { createLegacyWorkspaceApi } from "./legacy-workspace.mjs";
import { createLegacyEvaluationApi } from "./legacy-evaluation.mjs";
import { createLegacyViabilityApi } from "./legacy-viability.mjs";
export {
  LEGACY_METAMAP_VIABILITY_POLICY_VERSION,
  LEGACY_METAMAP_GENERATION_VERSION,
} from "./legacy-viability.mjs";
export { setLegacyDefaultAdapterRegistryFactory } from "./legacy-workspace.mjs";
import { createLegacyConfigApi } from "./legacy-config.mjs";
import { SssomError } from "./sssom.mjs";
import { createLegacyReferenceApi } from "./legacy-references.mjs";
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
        ["pack-file", "config", "config-file", "workspace"].includes(
          command[2],
        ) && code === "INVALID_JSON_SYNTAX";
      const error = fileSyntaxRefusal
        ? new SyntaxError(message)
        : ["config", "config-file"].includes(command[2]) &&
            report.error?.name === "CanonicalJsonError"
          ? new CanonicalJsonError(code, message)
          : ["config", "config-file"].includes(command[2]) &&
              report.error?.name === "SssomError"
            ? new SssomError(code, message)
            : canonicalPackRefusal
              ? new CanonicalJsonError(code, message)
              : ["compose", "workspace"].includes(command[2]) &&
                  report.error?.name === "MetamapCompositionError"
                ? new LegacyCompositionError(message, report.error.identifier)
                : ["references", "correspondence", "workspace", "cli"].includes(
                      command[2],
                    ) && report.error?.name === "URIError"
                  ? new URIError(message)
                  : ([
                        "graph",
                        "compose",
                        "references",
                        "correspondence",
                        "workspace",
                        "cli",
                        "evaluation",
                        "viability",
                      ].includes(command[2]) ||
                        (command[2] === "pack" && command[3] === "digest")) &&
                      report.error?.name === "TypeError"
                    ? new TypeError(message)
                    : new Error(message);
      // Original v1 policy/generation parsers throw ordinary errors. Keep the
      // structured native diagnostic in the execution trace, not on the error.
      if (command[2] === "viability") throw error;
      if (!(
        [
          "registry",
          "graph",
          "compose",
          "references",
          "correspondence",
          "evaluation",
          ...(["LEGACY_WORKSPACE_INPUT", "INVALID_JSON_SYNTAX"].includes(code)
            ? ["workspace", "cli"]
            : []),
          ...([
            "LEGACY_CONFIG_SCHEMA",
            "LEGACY_CONFIG_SEMANTIC",
            "INVALID_JSON_SYNTAX",
          ].includes(code)
            ? ["config", "config-file"]
            : []),
        ].includes(command[2]) ||
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
        : namespace === "graph" ||
            (namespace === "json" && ["validate", "shape"].includes(operation))
          ? marshalLegacyGraphRequest(request)
          : marshalJson(request);
    const command = [executable, "legacy", namespace, operation];
    if (namespace === "pack" && operation === "digest")
      command.push("--locale", new Intl.Collator().resolvedOptions().locale);
    const result = spawnWithInputSync(executable, command.slice(1), {
      input,
      encoding: "utf8",
      env: {},
      timeout: 65_000,
      maxBuffer: 16 * 1024 * 1024 + 1,
    });
    return finish(command, input, result);
  }
  async function invokeAsync(namespace, operation, request) {
    const input = marshalJson(request),
      command = [executable, "legacy", namespace, operation];
    return await new Promise((accept, reject) => {
      const child = spawn(executable, command.slice(1), {
        env: {},
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 65_000,
      });
      let stdout = "",
        stderr = "",
        failure;
      child.stdout.setEncoding("utf8");
      child.stderr.setEncoding("utf8");
      child.stdout.on("data", (part) => {
        stdout += part;
        if (Buffer.byteLength(stdout) > 16 * 1024 * 1024 + 1) {
          failure = new Error(
            "Native output exceeds the configured transport buffer",
          );
          child.kill();
        }
      });
      child.stderr.on("data", (part) => {
        stderr += part;
        if (Buffer.byteLength(stderr) > 16 * 1024 * 1024 + 1) {
          failure = new Error(
            "Native error output exceeds the configured transport buffer",
          );
          child.kill();
        }
      });
      child.on("error", (error) => {
        failure = error;
      });
      child.stdin.on("error", (error) => {
        failure ??= error;
      });
      child.on("close", (status, signal) => {
        try {
          accept(
            finish(command, input, {
              status,
              signal,
              stdout,
              stderr,
              error: failure,
            }),
          );
        } catch (error) {
          reject(error);
        }
      });
      child.stdin.end(input);
    });
  }
  async function loadFile(namespace, operation, path) {
    const command = [
      executable,
      "legacy",
      namespace,
      ...(operation === null ? [] : [operation]),
      resolve(path),
    ];
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
  const workspace = createLegacyWorkspaceApi(
    invoke,
    invokeAsync,
    Registry,
    (library) => library.configureDiscoveryNative(executable, observeExecution),
  );
  workspace.loadLegacyRelationPack = (path) =>
    loadFile("pack-file", "parse", path);
  const owner = {
    LegacyRelationRegistry: Registry,
    LegacyGraphValidationError,
    LegacyGraph: Graph,
    composeLegacyDocuments: createLegacyComposer(invoke),
    ...createLegacyReportingApi(invoke),
    ...createLegacyCorrespondenceApi(invoke),
    ...createLegacyReferenceApi(invoke),
    ...createLegacyEvaluationApi(invoke, Registry),
    ...createLegacyViabilityApi(invoke, Registry),
    ...createLegacyConfigApi(invoke, loadFile),
    ...workspace,
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
      return loadFile("pack-file", "parse", path);
    },
  };
  Object.assign(owner, createLegacyCliApi(invoke, invokeAsync, owner));
  return Object.freeze(owner);
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
export const parseLegacyEvaluationContext = (value) =>
  api().parseLegacyEvaluationContext(value);
export const evaluateLegacyContextExpression = (expression, context) =>
  api().evaluateLegacyContextExpression(expression, context);
export const requiredLegacyContextKeys = (expression) =>
  api().requiredLegacyContextKeys(expression);
export const legacyInactiveReason = (applicability, context) =>
  api().legacyInactiveReason(applicability, context);
export const legacySelectorMatches = (mapping, selector, entityKinds) =>
  api().legacySelectorMatches(mapping, selector, entityKinds);
export const analyzeLegacyImpact = (document, options) =>
  api().analyzeLegacyImpact(document, options);
export const validateLegacyViabilityPolicy = (value) =>
  api().validateLegacyViabilityPolicy(value);
export const validateLegacyViableGeneration = (value) =>
  api().validateLegacyViableGeneration(value);
export const parseLegacyViabilityPolicy = (value) =>
  api().parseLegacyViabilityPolicy(value);
export const parseLegacyViableGeneration = (value) =>
  api().parseLegacyViableGeneration(value);
export const compileLegacyMetamap = (document, policy, options) =>
  api().compileLegacyMetamap(document, policy, options);
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
export const diffLegacyDocuments = (before, after) =>
  api().diffLegacyDocuments(before, after);
export const emptyLegacyGraphDiff = () => api().emptyLegacyGraphDiff();
export const assembleLegacyWorkspace = (...args) =>
  api().assembleLegacyWorkspace(...args);
export const makeLegacyWorkspaceSnapshot = (...args) =>
  api().makeLegacyWorkspaceSnapshot(...args);
export const legacyWorkspaceHasErrors = (value) =>
  api().legacyWorkspaceHasErrors(value);
export const discoverLegacyWorkspace = (...args) =>
  api().discoverLegacyWorkspace(...args);
export const checkLegacyWorkspace = (...args) =>
  api().checkLegacyWorkspace(...args);
export const writeLegacyWorkspaceOutputs = (...args) =>
  api().writeLegacyWorkspaceOutputs(...args);
export const createDefaultLegacyAdapterRegistry = () =>
  api().createDefaultLegacyAdapterRegistry();
export class LegacyAdapterRegistry {
  #registry = new (api().LegacyAdapterRegistry)();
  register(adapter) {
    this.#registry.register(adapter);
    return this;
  }
  get(id) {
    return this.#registry.get(id);
  }
  require(id) {
    return this.#registry.require(id);
  }
  ids() {
    return this.#registry.ids();
  }
}
export const LEGACY_METAMAP_CONFIG_VERSION = "1.0.0";
export const parseLegacyMetamapConfig = (value) =>
  api().parseLegacyMetamapConfig(value);
export const loadLegacyMetamapConfig = (path) =>
  api().loadLegacyMetamapConfig(path);
export const materializeLegacyCorrespondences = (...args) =>
  api().materializeLegacyCorrespondences(...args);
export const isLegacyReferenceIdentifier = (value) =>
  api().isLegacyReferenceIdentifier(value);
export const isLegacyRelationIdentifier = (value) =>
  api().isLegacyRelationIdentifier(value);
export const makeLegacyUrn = (...args) => api().makeLegacyUrn(...args);
export const makeLegacyRepositoryUri = (...args) =>
  api().makeLegacyRepositoryUri(...args);
export const hasLegacyAmbiguousPathLanguage = (path) =>
  api().hasLegacyAmbiguousPathLanguage(path);
export const isLegacyPathPattern = (path) => api().isLegacyPathPattern(path);
export const renderLegacyDriftReport = (input) =>
  api().renderLegacyDriftReport(input);
export const renderLegacyGraphDocumentation = (graph, correspondences) =>
  api().renderLegacyGraphDocumentation(graph, correspondences);

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

export const runLegacyCli = (...args) => api().runLegacyCli(...args);
export const isLegacySourceOfTruthDocument = (...args) =>
  api().isLegacySourceOfTruthDocument(...args);
export const adaptLegacySourcesOfTruth = (...args) =>
  api().adaptLegacySourcesOfTruth(...args);
