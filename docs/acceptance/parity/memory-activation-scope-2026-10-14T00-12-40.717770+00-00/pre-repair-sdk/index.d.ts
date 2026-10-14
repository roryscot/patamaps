export * from "./canonical.js";

export declare class Patamaps {
  readonly executable: string;
  constructor(executable: string);
  runJson(arguments_: string[]): unknown;
  replay(path: string): unknown;
  generate(config: string, root: string): unknown;
  check(config: string, baseline: string, root: string): unknown;
}

export * from "./sssom.js";
export * from "./legacy-validation.js";
