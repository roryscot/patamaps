/** Execute and compare the native legacy renderer; retain every generated file. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, join, dirname } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { ensureGuarded } from "./storage_guard.mjs";
await ensureGuarded();
const root=resolve(dirname(fileURLToPath(import.meta.url)),"../..");
const [executable, oracleRoot, workArgument]=process.argv.slice(2);
assert(executable && oracleRoot && workArgument, "compiler, pinned original package and fresh work are required");
const work=resolve(workArgument);
assert(work.startsWith(join(root,".tools")+ "/"));
mkdirSync(work);
const original=await import(pathToFileURL(join(oracleRoot,"dist/index.js")));
const sdk=await import(pathToFileURL(join(root,"sdk/typescript/index.mjs")));
const require=createRequire(import.meta.url);
const ts=require(join(oracleRoot,"../..","typescript/lib/typescript.js"));
const calls=[];
const api=sdk.createLegacyValidationApi(executable,event=>{
  const response=JSON.parse(event.stdout);
  calls.push({command:event.command.slice(1),operation:JSON.parse(event.input).operation,exitCode:event.exitCode,
    inputDigest:createHash("sha256").update(event.input).digest("hex"),errorCode:response.error?.code??null});
});
const copy=v=>structuredClone(v);
const target={id:"urn:render:target",kind:"render:item",attributes:{number:1e21,tiny:1e-7,text:'quotes " and \uE000 \ud800',nested:{"10":"ten","2":"two",z:0,a:false}}};
const slot=(name,cardinality,targets)=>({name,relation:"core:contains",direction:"outgoing",cardinality,mappings:[],targets});
const content={
  schemaVersion:"1.0.0",
  generation:{id:"urn:render:generation",digest:"sha256:"+"0".repeat(64)},
  graph:{id:"urn:render:graph",digest:"sha256:"+"1".repeat(64)},
  spec:{id:"urn:render:spec",digest:"sha256:"+"2".repeat(64)},
  entries:[{subject:{id:"urn:render:subject",kind:"render:item",label:"Subject"},
    slots:[slot("required","exactly-one",[target]),slot("optional","zero-or-one",[]),
      slot("optionalPresent","zero-or-one",[target]),slot("multiple","one-or-more",[target]),
      slot("many","many",[target,{id:"urn:render:other",kind:"render:item"}])]}]
};
function address(value){
  const {$schema,id,digest,...body}=value;
  const sum=original.valueDigest(body);
  return {...body,id:"urn:metamap:projection:"+sum.slice(7),digest:sum};
}
const projection=address(content);
const positives=[];
async function execute(label,source,exportName,check){
  const path=join(work,label+".mts");
  writeFileSync(path,source,{flag:"wx"});
  const options={strict:true,noEmit:true,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.NodeNext,
    moduleResolution:ts.ModuleResolutionKind.NodeNext,types:[],skipLibCheck:false};
  const program=ts.createProgram([path],options);
  const diagnostics=ts.getPreEmitDiagnostics(program);
  assert.equal(diagnostics.length,0,ts.formatDiagnosticsWithColorAndContext(diagnostics,{
    getCurrentDirectory:()=>work,getCanonicalFileName:f=>f,getNewLine:()=>"\n"}));
  const emitted=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}});
  const executablePath=join(work,label+".mjs");
  writeFileSync(executablePath,emitted.outputText,{flag:"wx"});
  const module=await import(pathToFileURL(executablePath));
  const resolver="resolve"+exportName[0].toUpperCase()+exportName.slice(1);
  const entry=module[resolver]("urn:render:subject");
  assert.equal(entry,module[exportName]["urn:render:subject"]);
  assert.throws(()=>module[resolver]("__proto__"),/Unknown Metamap identity/);
  assert.throws(()=>module[resolver]("urn:render:absent"),/Unknown Metamap identity/);
  check(entry);
}
for(const [label,options] of [["default",{}],["named",{exportName:"ownerTopology"}],["nullish-name",{exportName:null}]]){
  const expected=original.emitTypeScriptProjection(projection,options);
  const actual=api.emitLegacyTypeScriptProjection(projection,options);
  assert.equal(actual,expected,label);
  await execute(label,actual,options.exportName??"metamapProjection",entry=>{
    assert.deepEqual(entry.slots.required,target);
    assert.equal(entry.slots.optional,null);
    assert.deepEqual(entry.slots.optionalPresent,target);
    assert.equal(entry.slots.multiple.length,1);
    assert.equal(entry.slots.many.length,2);
  });
  positives.push(label);
}
const dangerous=copy(content);
dangerous.entries[0].subject.attributes=JSON.parse('{"__proto__":{"polluted":true},"constructor":"ordinary-own-data"}');
dangerous.entries[0].subject.attributes.expression='"; globalThis.PATAMAPS_RENDER_EXECUTED=true; //';
dangerous.entries[0].slots.push(slot("__proto__","many",[target]));
assert.equal(globalThis.PATAMAPS_RENDER_EXECUTED,undefined);
await execute("prototype-data",api.emitLegacyTypeScriptProjection(address(dangerous)), "metamapProjection",entry=>{
  assert(Object.hasOwn(entry.subject.attributes,"__proto__"));
  assert.deepEqual(entry.subject.attributes.__proto__,{polluted:true});
  assert.equal(Object.getPrototypeOf(entry.subject.attributes),Object.prototype);
  assert(Object.hasOwn(entry.subject.attributes,"constructor"));
  assert.equal(entry.subject.attributes.constructor,"ordinary-own-data");
  assert(Object.hasOwn(entry.slots,"__proto__"));
  assert.deepEqual(entry.slots.__proto__,[target]);
  assert.equal(Object.getPrototypeOf(entry.slots),Object.prototype);
  assert.equal(globalThis.PATAMAPS_RENDER_EXECUTED,undefined);
});
positives.push("prototype-data");
const refusals=[];
function refuse(label,value,options={}){
  assert.throws(()=>api.emitLegacyTypeScriptProjection(value,options),label);
  const call=calls.at(-1);
  assert.equal(call.operation,"projection-emit-typescript");
  assert.notEqual(call.exitCode,0);
  refusals.push(label);
}
for(const name of ["","class","await","Object","Error","arguments","eval","x".repeat(129),"x;process.exit()","é","1name"]){
  refuse("export-"+refusals.length,projection,{exportName:name});
}
refuse("nonstrings",projection,{exportName:42});
refuse("null-options",projection,null);
refuse("null-record",null);
refuse("comment-injection",{...projection,id:"urn:test:*/globalThis.PATAMAPS_RENDER_EXECUTED=true"});
refuse("header-newline",{...projection,id:"urn:test:\nunsafe"});
refuse("stale-digest",{...projection,digest:"sha256:"+"f".repeat(64)});
refuse("unknown-field",{...projection,unexpected:true});
for(const [cardinality,targets] of [["exactly-one",[]],["zero-or-one",[target,{...target,id:"urn:render:other"}]],["one-or-more",[]]]){
  const wrong=copy(content);wrong.entries[0].slots=[slot("broken",cardinality,targets)];
  refuse("cardinality-"+cardinality,address(wrong));
}
const huge=copy(content);huge.entries[0].subject.attributes={payload:"a".repeat(9*1024*1024)};
refuse("bounded-output-expansion",address(huge));
assert.equal(calls.at(-1).errorCode,"LEGACY_PROJECTION_RESOURCE_LIMIT");
assert(calls.every(x=>x.operation==="projection-emit-typescript"));
const result={status:"passed-native-legacy-typescript-renderer-controls",positives,refusals,
  typedAndExecutedModules:4,oracleVersion:JSON.parse(readFileSync(join(oracleRoot,"package.json"))).version,
  oracleDigest:createHash("sha256").update(readFileSync(join(oracleRoot,"dist/projection.js"))).digest("hex"),
  nativeCalls:calls.length,calls,filesDeleted:0,ownerApplicationAccepted:false};
writeFileSync(join(work,"receipt.json"),JSON.stringify(result,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({status:result.status,positiveControls:positives.length,refusalControls:refusals.length,nativeCalls:calls.length}));
