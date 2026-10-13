import assert from "node:assert/strict";
import {readFileSync,writeFileSync,existsSync,appendFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {execFileSync} from "node:child_process";
import {createLegacyValidationApi} from "../../../../sdk/typescript/legacy-validation.mjs";
import {MetamapGraph as Original} from "../../../../.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/dist/graph.js";
const sha=raw=>"sha256:"+createHash("sha256").update(raw).digest("hex");
const d={schemaVersion:"2.0.0",id:"urn:factory:test",namespace:"test",entities:[],mappings:[],authorities:[]};
class ReferenceChild extends Original {}
const reference=ReferenceChild.from(d);
const expected={child:reference instanceof ReferenceChild,base:reference instanceof Original,document:reference.document===d};
const expectedFile=new URL("factory-expected.json",import.meta.url);
if(!existsSync(expectedFile))writeFileSync(expectedFile,JSON.stringify({originalEngine:"399747a4ad05a37cd8db1cedd53048fad2175be4",graphArtifactDigest:sha(readFileSync(new URL("../../../../.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/dist/graph.js",import.meta.url))),expected},null,2)+"\n",{flag:"wx"});
assert.deepEqual(expected,JSON.parse(readFileSync(expectedFile)).expected);
const binary=new URL("../../../../target/debug/patamaps",import.meta.url).pathname;
const calls=[];const api=createLegacyValidationApi(binary,execution=>{calls.push(execution);appendFileSync(new URL("factory-native-executions.ndjson",import.meta.url),JSON.stringify(execution)+"\n");});
class CandidateChild extends api.LegacyGraph {}
const candidate=CandidateChild.from(d);
const observed={child:candidate instanceof CandidateChild,base:candidate instanceof api.LegacyGraph,document:candidate.document===d};
assert.deepEqual(observed,expected);
assert(calls.some(call=>call.command[2]==="graph"));assert(calls.every(call=>call.exitCode===0));
const receipt={schemaVersion:"1.0.0",status:"matched",scope:"One frozen original inherited-factory observation; constructor subclass nominal identity is not adopted by the original factory.",expected,observed,originalExpectedDigest:sha(readFileSync(expectedFile)),candidate:{binaryDigest:sha(readFileSync(binary)),engine:JSON.parse(execFileSync(binary,["engine"])),sdkSourceInventory:["legacy-graph.mjs","legacy-registry.mjs","legacy-validation.mjs","canonical.mjs"].map(name=>({path:"sdk/typescript/"+name,digest:sha(readFileSync(new URL("../../../../sdk/typescript/"+name,import.meta.url)))}))},driverDigest:sha(readFileSync(new URL(import.meta.url))),nativeExecutions:calls.length};
writeFileSync(new URL("factory-receipt.json",import.meta.url),JSON.stringify(receipt,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({status:"matched",receipt:"docs/acceptance/parity/"+new URL(".",import.meta.url).pathname.split("/").filter(Boolean).at(-1)+"/factory-receipt.json"}));
