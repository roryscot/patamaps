import { spawnSync } from "node:child_process";
import { isAbsolute } from "node:path";

export class CanonicalJsonError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "CanonicalJsonError";
    this.code = code;
  }
}
const fail = (code, message) => {
  throw new CanonicalJsonError(code, message);
};

function unicode(value) {
  for (let index = 0; index < value.length; index++) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(++index);
      if (!(next >= 0xdc00 && next <= 0xdfff))
        fail("INVALID_JSON_UNICODE", "Unpaired high surrogate");
    } else if (code >= 0xdc00 && code <= 0xdfff)
      fail("INVALID_JSON_UNICODE", "Unpaired low surrogate");
  }
}

/** Marshal JavaScript values without executing getters or toJSON hooks.
 * Undefined, symbols and prototypes cannot survive JSON transport, so they
 * must be checked here. Ordering, encoding and hashing belong to Rust.
 */
function portable(
  value,
  legacy = false,
  allowUtf16 = false,
  numberFacts,
  signedZeroOnly = false,
) {
  const ancestors = new Set();
  function copy(item, depth, path = []) {
    if (depth > 512)
      fail("JSON_DEPTH_LIMIT", "Canonical JSON exceeds 512 levels");
    if (item === null || typeof item === "boolean") return item;
    if (typeof item === "string") {
      if (!allowUtf16) unicode(item);
      return item;
    }
    if (typeof item === "number") {
      if (
        numberFacts &&
        ((!signedZeroOnly && !Number.isFinite(item)) || Object.is(item, -0))
      ) {
        numberFacts.push({
          path,
          kind: Number.isNaN(item)
            ? "nan"
            : Object.is(item, -0)
              ? "negative-zero"
              : item > 0
                ? "positive-infinity"
                : "negative-infinity",
        });
        return 0;
      }
      if (!Number.isFinite(item))
        fail(
          "INVALID_JSON_VALUE",
          "JSON numbers must be finite IEEE-754 values",
        );
      return item;
    }
    if (typeof item !== "object")
      fail("INVALID_JSON_VALUE", "Expected JSON-compatible values");
    if (ancestors.has(item)) fail("INVALID_JSON_VALUE", "Cyclic JSON value");
    if (Object.getOwnPropertySymbols(item).length)
      fail("INVALID_JSON_VALUE", "Symbol properties are not JSON");
    const descriptors = Object.getOwnPropertyDescriptors(item);
    for (const descriptor of Object.values(descriptors)) {
      if (!Object.hasOwn(descriptor, "value"))
        fail("INVALID_JSON_VALUE", "Accessors are not JSON values");
    }
    ancestors.add(item);
    let result;
    if (Array.isArray(item)) {
      if (
        (!numberFacts || signedZeroOnly) &&
        Object.getOwnPropertyNames(item).length !== item.length + 1
      )
        fail(
          "INVALID_JSON_VALUE",
          "Sparse arrays and extra array properties are not JSON",
        );
      result = [];
      Object.setPrototypeOf(result, null);
      for (let index = 0; index < item.length; index++) {
        if (!Object.hasOwn(item, index)) {
          if (numberFacts && !signedZeroOnly) {
            numberFacts.push({ path: [...path, String(index)], kind: "hole" });
            result[index] = 0;
            continue;
          }
          fail("INVALID_JSON_VALUE", "Sparse arrays are not JSON");
        }
        result[index] = copy(
          descriptors[index].value,
          depth + 1,
          numberFacts ? [...path, String(index)] : path,
        );
      }
    } else {
      const prototype = Object.getPrototypeOf(item);
      if (prototype !== Object.prototype && prototype !== null)
        fail("INVALID_JSON_VALUE", "Expected a plain JSON object");
      result = Object.create(null);
      for (const [key, descriptor] of Object.entries(descriptors)) {
        if (!allowUtf16) unicode(key);
        if (!descriptor.enumerable)
          fail(
            "INVALID_JSON_VALUE",
            "Nonenumerable object fields are not JSON",
          );
        if (legacy && descriptor.value === undefined) continue;
        result[key] = copy(
          descriptor.value,
          depth + 1,
          numberFacts ? [...path, key] : path,
        );
      }
    }
    ancestors.delete(item);
    return result;
  }
  const result = copy(value, 0);
  return JSON.stringify(
    numberFacts ? { value: result, numbers: numberFacts } : result,
  );
}

/** @internal JSON marshalling shared by the native SDK transports. */
export const marshalJson = (value) => portable(value);

/** @internal Version dispatch and portable-pack validation belong to Rust.
 * JSON.stringify preserves unpaired UTF-16 units as escapes for legacy input.
 * Modern JSON/JCS callers continue to use marshalJson's scalar-Unicode check.
 */
export const marshalLegacyPackJson = (value) => portable(value, false, true);

/** @internal Read-only legacy observations preserve UTF-16 and omit undefined
 * object fields as JSON.stringify does. Other non-JSON JS values are refused. */
export const marshalLegacyObservationJson = (value) =>
  portable(value, true, true);

/** @internal Preserve JavaScript numeric facts for read-only context decisions.
 * Graph admission and canonical encoding continue to reject nonfinite numbers. */
export const marshalLegacyNumericObservationJson = (value) =>
  portable(value, true, true, []);

/** @internal Preserve signed zero through the finite JSON compiler transport.
 * Nonfinite and sparse-array domains remain separately unresolved. */
export const marshalLegacySignedZeroObservationJson = (value) =>
  portable(value, true, true, [], true);

/** Object-based API backed by an explicitly selected native executable. */
export function createCanonicalApi(executable, observeExecution) {
  if (!isAbsolute(executable))
    throw new TypeError("Patamaps requires an absolute native executable");
  function invoke(operation, input) {
    const command = [executable, "json", operation];
    const result = spawnSync(executable, command.slice(1), {
      input,
      encoding: "utf8",
      env: {},
      timeout: 65_000,
      maxBuffer: 16 * 1024 * 1024 + 1,
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
          `Patamaps JSON transport failed (${result.status}): ${result.stdout}${result.stderr}`,
        );
      const error = new CanonicalJsonError(
        report.error.code,
        report.error.message,
      );
      error.nativeMessage = report.error.nativeMessage;
      throw error;
    }
    if (!result.stdout.endsWith("\n"))
      throw new Error("Patamaps JSON transport is missing its framing LF");
    return result.stdout.slice(0, -1);
  }
  return Object.freeze({
    canonicalJson(value) {
      return invoke("canonical", portable(value));
    },
    canonicalDigest(value) {
      return JSON.parse(invoke("digest", portable(value)));
    },
    parseStrictJson(text) {
      if (typeof text !== "string") throw new TypeError("Expected JSON text");
      // Unpaired literal units cannot survive UTF-8 transport. Preserve syntax
      // refusal precedence while refusing these untransportable values here.
      try {
        unicode(text);
      } catch (error) {
        try {
          JSON.parse(text);
        } catch {
          fail("INVALID_JSON_SYNTAX", "Invalid JSON syntax");
        }
        throw error;
      }
      invoke("parse", text);
      // Rust established validity; this ordinary host unmarshalling preserves
      // JavaScript's observable original property order.
      return JSON.parse(text);
    },
    legacyReferenceValue(value) {
      return JSON.parse(invoke("parse", portable(value, true)));
    },
  });
}

let configured;
export function configureCanonical(executable, observeExecution) {
  configured = createCanonicalApi(executable, observeExecution);
}
function api() {
  if (!configured) configureCanonical(process.env.PATAMAPS_EXECUTABLE ?? "");
  return configured;
}
export const canonicalJson = (value) => api().canonicalJson(value);
export const canonicalDigest = (value) => api().canonicalDigest(value);
export const parseStrictJson = (text) => api().parseStrictJson(text);
export const legacyReferenceValue = (value) =>
  api().legacyReferenceValue(value);
