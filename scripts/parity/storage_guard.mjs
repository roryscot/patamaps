/** Local verification transport to the installed shared storage supervisor.
 * No policy or lease implementation belongs in the native product or SDK. */
import { readFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { homedir, tmpdir } from "node:os";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

export async function ensureGuarded() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  const install = join(homedir(), "Documents/Codex/storage-safeguards");
  const raw = readFileSync(join(install, "projects.json"));
  const config = JSON.parse(raw);
  if (config.version !== 1 || resolve(config.projects.patamaps.root) !== root)
    throw new Error(
      "Storage supervisor does not register this Patamaps checkout",
    );
  const engine = await import(pathToFileURL(config.engine));
  const lease =
    process.env.LOCAL_STORAGE_PROJECT === root
      ? engine.inheritedLease(process.env, engine.sharedLeaseDirectory)
      : null;
  if (lease) {
    engine.assertUnpaused(
      join(homedir(), "Documents/Codex/.storage-control/other-projects"),
    );
    const free = Math.min(
      ...[root, tmpdir(), "/private/tmp"]
        .filter(existsSync)
        .map(engine.availableBytes),
    );
    const policy = engine.loadPolicy();
    engine.checkCapacity(policy, free, free);
    return {
      mode: "inherited-live-supervisor",
      project: root,
      configurationDigest:
        "sha256:" + createHash("sha256").update(raw).digest("hex"),
      policy,
      availableBytesAtEntry: free,
    };
  }
  const result = spawnSync(
    config.node,
    [
      join(install, "run-project.mjs"),
      "patamaps",
      "--",
      process.execPath,
      ...process.argv.slice(1),
    ],
    { stdio: "inherit", env: process.env },
  );
  if (result.error) throw result.error;
  process.exit(result.status ?? 75);
}
