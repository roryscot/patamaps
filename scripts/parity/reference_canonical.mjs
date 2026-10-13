/** The oracle executes pinned MetaMap code; it never supplies candidate output. */
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";

const [source, input] = process.argv.slice(2);
const { canonicalJson, canonicalDigest, parseStrictJson } = await import(
  pathToFileURL(join(source, "dist/canonical.js")).href
);
try {
  const value = parseStrictJson(readFileSync(input, "utf8"));
  console.log(
    JSON.stringify({
      status: "accepted",
      canonical: canonicalJson(value),
      digest: canonicalDigest(value),
    }),
  );
} catch (error) {
  console.log(
    JSON.stringify({
      status: "refused",
      name: error.name,
      code: error.code ?? null,
      message: error.message,
    }),
  );
}
