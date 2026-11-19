/** Original-owner legacy stable JSON/digest checks; no admission capability. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, join, dirname } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { ensureGuarded } from "./storage_guard.mjs";
await ensureGuarded();
const root=resolve(dirname(fileURLToPath(import.meta.url)),"../..");
const [executable,oracleRoot,workArgument]=process.argv.slice(2);
assert(executable&&oracleRoot&&workArgument);
const work=resolve(workArgument);assert(work.startsWith(join(root,".tools")+"/"));mkdirSync(work);
const original=await import(pathToFileURL(join(oracleRoot,"dist/index.js")));
const sdk=await import(pathToFileURL(join(root,"sdk/typescript/index.mjs")));
const calls=[];
const api=sdk.createLegacyValidationApi(executable,event=>{
  calls.push({command:event.command.slice(1),operation:JSON.parse(event.input).action.operation,
    exitCode:event.exitCode,inputDigest:createHash("sha256").update(event.input).digest("hex"),
    outputDigest:createHash("sha256").update(event.stdout).digest("hex")});
});
const cases=[
  ["null",null],["false",false],["number",1e21],["small-number",1e-7],["negative-zero",-0],
  ["string","quote \" and newline\n and \ud800 \uE000"],["array",[null,true,-0,"a"]],
  ["v2-data",{schemaVersion:"2.0.0",z:0,a:1,"Upper":2,lower:3}],
  ["integer-members",{"10":"ten","2":"two","01":"one",z:0,a:1}],
  ["collation-forward",Object.fromEntries([["é",1],["e\u0301",2],["A",3],["a",4]])],
  ["collation-reverse",Object.fromEntries([["e\u0301",2],["é",1],["a",4],["A",3]])],
  ["prototype-data",JSON.parse('{"__proto__":{"data":true},"constructor":"data","normal":1}')]
];
for(const [label,value] of cases){
  assert.equal(api.stableLegacyJson(value),original.stableJson(value),label+" compact");
  assert.equal(api.stableLegacyJson(value,true),original.stableJson(value,true),label+" pretty");
  assert.equal(api.digestLegacyValue(value),original.valueDigest(value),label+" digest");
}
const expanded={payload:"a".repeat(9*1024*1024)};
assert.throws(()=>api.stableLegacyJson(expanded,true),/resource bounds/);
assert.equal(api.digestLegacyValue(expanded),original.valueDigest(expanded));
const result={status:"passed-native-legacy-stable-utility-controls",cases:cases.map(x=>x[0]),positiveComparisons:37,
  prettyExpansionRefusal:true,largeCompactDigestPassed:true,oracleVersion:JSON.parse(readFileSync(join(oracleRoot,"package.json"))).version,
  nativeCalls:calls.length,calls,filesDeleted:0,ownerApplicationAccepted:false};
writeFileSync(join(work,"receipt.json"),JSON.stringify(result,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({status:result.status,positiveComparisons:37,nativeCalls:calls.length}));
