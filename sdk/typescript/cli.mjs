#!/usr/bin/env node
import { createLegacyValidationApi } from "./legacy-validation.mjs";
const [flag, native, ...args] = process.argv.slice(2);
if (flag !== "--native" || !native) {
  process.stderr.write(
    "Patamaps compatibility CLI requires --native /absolute/path/to/patamaps\n",
  );
  process.exitCode = 2;
} else {
  try {
    const api = createLegacyValidationApi(native);
    const result = await api.runLegacyCli(args);
    process.stdout.write(result.stdout);
    process.stderr.write(result.stderr);
    process.exitCode = result.exitCode;
  } catch (e) {
    process.stderr.write((e instanceof Error ? e.message : String(e)) + "\n");
    process.exitCode = 1;
  }
}
