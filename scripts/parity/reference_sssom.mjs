/** Observe the actual pinned parser, without reimplementing its results. */
import { readFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";
const oracle = resolve(process.argv[2]);
const request = JSON.parse(readFileSync(process.argv[3], "utf8"));
const { parseSssomTsv } = await import(
  pathToFileURL(join(oracle, "dist/sssom.js"))
);
const { canonicalDigest } = await import(
  pathToFileURL(join(oracle, "dist/canonical.js"))
);
try {
  const document = parseSssomTsv(
    Buffer.from(request.input, "base64"),
    request.metadata === undefined
      ? undefined
      : Buffer.from(request.metadata, "base64"),
  );
  process.stdout.write(
    JSON.stringify({
      status: "accepted",
      canonicalDigest: canonicalDigest(document),
      rows: document.rows.length,
      columns: document.columns.length,
    }) + "\n",
  );
} catch (error) {
  process.stdout.write(
    JSON.stringify({
      status: "refused",
      error: {
        name: error.name,
        code: error.code ?? null,
        message: error.message,
      },
    }) + "\n",
  );
}
