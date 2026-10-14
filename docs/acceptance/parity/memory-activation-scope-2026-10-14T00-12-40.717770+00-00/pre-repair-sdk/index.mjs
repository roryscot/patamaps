import { execFileSync } from "node:child_process";
import { isAbsolute } from "node:path";
export {
  CanonicalJsonError,
  createCanonicalApi,
  configureCanonical,
  canonicalJson,
  canonicalDigest,
  parseStrictJson,
  legacyReferenceValue,
} from "./canonical.mjs";

/** Thin transport. Parsed JSON is wire data; use replay for verification. */
export class Patamaps {
  constructor(executable) {
    if (!isAbsolute(executable))
      throw new Error(
        "Patamaps requires an absolute installed native executable",
      );
    this.executable = executable;
  }
  runJson(arguments_) {
    if (
      !Array.isArray(arguments_) ||
      arguments_.some((a) => typeof a !== "string")
    )
      throw new TypeError("Use an argument vector");
    const output = execFileSync(this.executable, arguments_, {
      encoding: "utf8",
      env: {},
      timeout: 65_000,
      maxBuffer: 16 * 1024 * 1024,
    });
    return JSON.parse(output);
  }
  replay(path) {
    return this.runJson(["replay", path]);
  }
  generate(config, root) {
    return this.runJson(["generate", config, "--root", root]);
  }
  check(config, baseline, root) {
    return this.runJson(["check", config, baseline, "--root", root]);
  }
}

export * from "./sssom.mjs";
export * from "./legacy-validation.mjs";
