import { spawnSync } from "node:child_process";
import { isAbsolute } from "node:path";
import { marshalJson } from "./canonical.mjs";
export {
  SSSOM_BUILTIN_PREFIXES,
  SSSOM_PROPAGATABLE_SLOTS,
} from "./sssom-profile.mjs";

export const SSSOM_MAX_BYTES = 64 * 1024 * 1024;
export const SSSOM_FORMAT_VERSION = "1.0.0";
export const SSSOM_ENTITY_PROFILE = "sssom-1.0-entity-tsv";
export class SssomError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "SssomError";
    this.code = code;
  }
}
function freeze(value) {
  if (value && typeof value === "object") {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}
function encoded(input) {
  if (typeof input === "string") marshalJson(input);
  else if (!(input instanceof Uint8Array))
    throw new TypeError("Expected UTF-8 text or Uint8Array");
  const bytes =
    typeof input === "string"
      ? Buffer.from(input, "utf8")
      : Buffer.from(input.buffer, input.byteOffset, input.byteLength);
  if (bytes.length > SSSOM_MAX_BYTES)
    throw new SssomError("SSSOM_SIZE_LIMIT", "SSSOM input exceeds 64 MiB");
  return bytes.toString("base64");
}
export function createSssomApi(executable, observeExecution) {
  if (!isAbsolute(executable))
    throw new TypeError("Patamaps requires an absolute native executable");
  function invoke(operation, value, args = []) {
    const command = [executable, "sssom", "json", operation, ...args];
    const input = marshalJson(value);
    const result = spawnSync(executable, command.slice(1), {
      input,
      encoding: "utf8",
      env: {},
      timeout: 65_000,
      maxBuffer: 1024 * 1024 * 1024 + 1,
    });
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
    if (result.status !== 0) {
      const report = JSON.parse(result.stdout);
      if (report.status !== "refused" || !report.error)
        throw new Error(
          `Patamaps scientific transport failed (${result.status}): ${result.stdout}${result.stderr}`,
        );
      throw new SssomError(report.error.code, report.error.message);
    }
    if (!result.stdout.endsWith("\n"))
      throw new Error(
        "Patamaps scientific transport is missing its framing LF",
      );
    return freeze(JSON.parse(result.stdout.slice(0, -1)));
  }
  return Object.freeze({
    parseSssomTsv(input, externalMetadata) {
      return invoke("parse", {
        input: encoded(input),
        ...(externalMetadata === undefined
          ? {}
          : { metadata: encoded(externalMetadata) }),
      });
    },
    parseSssomDocument(value) {
      return invoke("document", value);
    },
    parseSssomSourceConfig(value) {
      return invoke("source-config", value);
    },
    interpretSssomDocument(value) {
      return invoke("interpret", value);
    },
    expandSssomCurie(value, prefixes) {
      return invoke("expand", { value, prefixes });
    },
    exportSssomTsv(value, options = {}) {
      if (
        Object.keys(options).some((key) => key !== "condense") ||
        (options.condense !== undefined &&
          typeof options.condense !== "boolean")
      )
        throw new SssomError(
          "SSSOM_EXPORT_OPTIONS",
          "Only a boolean condense option is supported",
        );
      return invoke("export", value, options.condense ? ["--condense"] : []);
    },
  });
}
let configured;
export function configureSssom(executable, observeExecution) {
  configured = createSssomApi(executable, observeExecution);
}
function api() {
  if (!configured) configureSssom(process.env.PATAMAPS_EXECUTABLE ?? "");
  return configured;
}
export const parseSssomTsv = (input, metadata) =>
  api().parseSssomTsv(input, metadata);
export const parseSssomDocument = (value) => api().parseSssomDocument(value);
export const parseSssomSourceConfig = (value) =>
  api().parseSssomSourceConfig(value);
export const interpretSssomDocument = (value) =>
  api().interpretSssomDocument(value);
export const exportSssomTsv = (value, options) =>
  api().exportSssomTsv(value, options);
export const expandSssomCurie = (value, prefixes) =>
  api().expandSssomCurie(value, prefixes);
