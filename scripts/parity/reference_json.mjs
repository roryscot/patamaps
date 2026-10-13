import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const [source, input] = process.argv.slice(2);
const { parseStrictJson, canonicalJson } = await import(
  pathToFileURL(join(source, "dist/canonical.js")).href
);
const text = JSON.parse(readFileSync(input, "utf8")).text;
try {
  const value = parseStrictJson(text);
  console.log(
    JSON.stringify({
      status: "accepted",
      canonical: canonicalJson(value),
      ownKeys:
        value !== null && typeof value === "object" ? Object.keys(value) : null,
    }),
  );
} catch (error) {
  console.log(
    JSON.stringify({
      status: "refused",
      error: {
        name: error.name,
        code: error.code ?? null,
        message: error.message,
      },
    }),
  );
}
