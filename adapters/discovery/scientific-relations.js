import { readFileSync } from "node:fs";

// Fixed source-fact data; the Rust registry independently checks admitted use.
export const SCIENTIFIC_SKOS_PREDICATES = Object.freeze({
  "http://www.w3.org/2004/02/skos/core#exactMatch": "scientific:exact-match",
  "http://www.w3.org/2004/02/skos/core#closeMatch": "scientific:close-match",
  "http://www.w3.org/2004/02/skos/core#broadMatch": "scientific:broad-match",
  "http://www.w3.org/2004/02/skos/core#narrowMatch": "scientific:narrow-match",
  "http://www.w3.org/2004/02/skos/core#relatedMatch":
    "scientific:related-match",
});
export function scientificSkosRelationPack() {
  const pack = JSON.parse(
    readFileSync(
      new URL("./profiles/scientific-skos.json", import.meta.url),
      "utf8",
    ),
  );
  if (
    pack.schemaVersion !== "2.0.0" ||
    pack.id !== "urn:metamap:relation-pack:scientific-skos" ||
    pack.version !== "1.0.0"
  ) {
    throw new Error(
      "Bundled scientific SKOS profile has an unexpected identity",
    );
  }
  return pack;
}
