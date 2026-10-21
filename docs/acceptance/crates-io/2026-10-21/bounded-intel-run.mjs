// This release's stricter per-run budget; shared supervisor and policy stay intact.
import {existsSync, readFileSync, readdirSync, writeFileSync} from "node:fs";
import {createHash, randomUUID} from "node:crypto";
import os from "node:os";
import path from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";

const base = "/Users/admin/Documents/Codex/storage-safeguards";
const config = JSON.parse(readFileSync(path.join(base, "projects.json"), "utf8"));
if (config.version !== 1) throw new Error("Unknown supervisor configuration");
const engine = await import(pathToFileURL(config.engine));
const {retentionInventory} = await import(pathToFileURL(path.join(base, "retention_admission.mjs")));
const [requested, separator, ...command] = process.argv.slice(2);
const approved = engine.loadPolicy();
const growth = Number(requested);
if (!Number.isSafeInteger(growth) || growth <= 0 || growth > approved.maximumRunGrowthBytes)
  throw new Error("A bounded run must request a positive budget within the approved maximum");
if (approved.maximumRunGrowthBytes !== 4_000_000_000 || approved.maximumRetainedBytes !== 100_000_000_000 || approved.reserveFreeBytes !== 500_000_000)
  throw new Error("The approved Intel policy changed; review before proceeding");
if (separator !== "--" || !command.length) throw new Error("Use GROWTH_BYTES -- COMMAND [ARGS]");
const policy = {...approved, maximumRunGrowthBytes: growth};
const project = config.projects.patamaps;
const roots = () => {
  const result = [project.root, ...(project.retentionRoots ?? []), ...config.cacheRoots].filter(existsSync);
  for (const temporary of [...new Set([os.tmpdir(), "/private/tmp"])].filter(existsSync))
    for (const entry of readdirSync(temporary, {withFileTypes: true}))
      if (entry.isDirectory() && project.temporaryPrefixes.some(prefix => entry.name.startsWith(prefix)))
        result.push(path.join(temporary, entry.name));
  return [...new Set(result)].sort();
};
const capacity = () => Math.min(...[project.root, process.cwd(), os.tmpdir(), "/private/tmp",
  ...(project.retentionRoots ?? []), ...config.cacheRoots].filter(existsSync).map(engine.availableBytes));
const policyFile = path.join(engine.projectRoot, "storage-policy.json");
const policyDigest = () => createHash("sha256").update(readFileSync(policyFile)).digest("hex");
const record = {at: new Date().toISOString(), sharedPolicySha256: policyDigest(), approvedPolicy: approved,
  enforcedRunPolicy: policy, filesDeleted: 0, retentionAdmissions: []};
console.log(JSON.stringify({boundedIntelRun: {maximumRunGrowthBytes: growth,
  maximumRetainedBytes: policy.maximumRetainedBytes, reserveFreeBytes: policy.reserveFreeBytes}}));
try {
  process.exitCode = await engine.guardedCommand("patamaps", command[0], command.slice(1), {
    directory: path.join(os.homedir(), "Documents/Codex/.storage-control/other-projects"),
    childControlDirectory: path.join(os.homedir(), "Documents/Codex/.storage-control/wargame"),
    leaseDirectory: engine.sharedLeaseDirectory, root: project.root, cwd: process.cwd(), policy, capacity,
    retentionRoots: roots, inventory: retentionInventory(engine.retainedBytes, policy, admission => record.retentionAdmissions.push(admission)),
    environment: {...process.env, LOCAL_STORAGE_PROJECT: project.root},
  });
  record.exitCode = process.exitCode;
} finally {
  record.sharedPolicyUnchanged = policyDigest() === record.sharedPolicySha256;
  writeFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "bounded-run-" + randomUUID() + ".json"),
    JSON.stringify(record, null, 2) + "\n", {flag: "wx"});
}
