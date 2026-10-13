import { canonicalDigest } from "./canonical.js";
import { valueDigest } from "./stable.js";

/** Digest source facts using their original versioned wire convention. */
export function relationPackDigest(pack) {
  return pack.schemaVersion === "2.0.0"
    ? canonicalDigest(pack)
    : valueDigest(pack);
}
