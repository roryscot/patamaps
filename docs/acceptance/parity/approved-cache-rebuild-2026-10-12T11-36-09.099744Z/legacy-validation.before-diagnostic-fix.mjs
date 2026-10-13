import { execFile, spawnSync } from "node:child_process";
import { isAbsolute, resolve } from "node:path";
import { marshalJson, marshalLegacyPackJson } from "./canonical.mjs";

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
      const error = new Error(
        report.error?.message ?? "Legacy registry request refused",
      );
      error.code = report.error?.code ?? "LEGACY_REGISTRY_INPUT";
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
        : marshalJson(request);
    const command = [executable, "legacy", namespace, operation];
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
  return Object.freeze({
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
