import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { ensureGuarded } from "/Users/admin/dev/patamaps/patamaps/scripts/parity/storage_guard.mjs";
import { createLegacyValidationApi } from "/Users/admin/dev/patamaps/patamaps/sdk/typescript/legacy-validation.mjs";
const supervision = await ensureGuarded();
const root = "/Users/admin/dev/patamaps/patamaps";
const out = dirname(fileURLToPath(import.meta.url));
const binary = join(root,"target/debug/patamaps");
const executions = [];
const owner = createLegacyValidationApi(binary,call=>executions.push(call));
const api = { compileMetamap: owner.compileLegacyMetamap };
function host(result, input) {
  return {
    keys: Object.keys(result),
    issueKeys: result.issues?.map((i) => Object.keys(i)) ?? [],
    ...(result.generation
      ? {
          generationKeys: Object.keys(result.generation),
          graphKeys: Object.keys(result.generation.graph),
          sharedContext: result.generation.context === input.options.context,
          frozen: Object.isFrozen(result.generation),
          contextFrozen: Object.isFrozen(input.options.context),
          activeFrozen: Object.isFrozen(result.generation.activeMappings),
        }
      : {}),
  };
}
function observe(c, api) {
  const input = JSON.parse(c.action.input);
  try {
    let result;
    if (c.action.operation === "compile")
      result = api.compileMetamap(input.document, input.policy, input.options);
    if (c.action.operation === "validate-policy")
      result = api.validateViabilityPolicy(input.value);
    if (c.action.operation === "parse-policy") {
      result = api.parseViabilityPolicy(input.value);
      return {
        status: "observed",
        value: result,
        host: {
          shared: result === input.value,
          frozen: Object.isFrozen(result),
        },
      };
    }
    if (c.action.operation === "validate-generation")
      result = api.validateViableGeneration(input.value);
    if (c.action.operation === "parse-generation") {
      result = api.parseViableGeneration(input.value);
      return {
        status: "observed",
        value: result,
        host: {
          shared: result === input.value,
          frozen: Object.isFrozen(result),
        },
      };
    }
    return { status: "observed", value: result, host: host(result, input) };
  } catch (e) {
    return { status: "threw", error: { name: e.name, message: e.message } };
  }
}

const bytes = readFileSync(join(root,"fixtures/parity/viability-controls.json"));
const sha = b=>"sha256:"+createHash("sha256").update(b).digest("hex");
assert.equal(sha(bytes),"sha256:df246fe562839235f187e2f61e21a329d01c3e4f2c20d90c03d37c8191a464fc");
const cases = JSON.parse(bytes).cases.filter(c=>["constraint-183","constraint-205","constraint-225","constraint-239"].includes(c.name));
assert.equal(cases.length,4);
const observations = cases.map(c=>({name:c.name,expected:c.expected,observed:observe(c,api)}));
const differences = observations.filter(c=>JSON.stringify(c.expected)!==JSON.stringify(c.observed));
writeFileSync(join(out,"native-executions.ndjson"),executions.map(c=>JSON.stringify(c)).join("\n")+"\n",{flag:"wx"});
const receipt={status:differences.length?"different":"matched",scope:"Exact four previously timed-out immutable cases; diagnostic subset only, no full-corpus acceptance.",supervision,driverDigest:sha(readFileSync(fileURLToPath(import.meta.url))),binaryDigest:sha(readFileSync(binary)),engine:JSON.parse(execFileSync(binary,["engine"])),cases:4,matched:4-differences.length,observations};
writeFileSync(join(out,"receipt.json"),JSON.stringify(receipt,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({status:receipt.status,cases:4,matched:receipt.matched,receipt:join(out,"receipt.json")}));
assert.equal(differences.length,0);
