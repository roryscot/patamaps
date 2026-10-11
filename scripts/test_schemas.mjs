// Optional developer tool: schemas are loaded explicitly and entirely locally.
import {readFileSync,readdirSync} from "node:fs";
import {createRequire} from "node:module";
import {resolve} from "node:path";
import {spawnSync} from "node:child_process";
const require=createRequire(resolve(process.argv[2],"package.json"));
const Ajv=require("ajv/dist/2020.js").default,formats=require("ajv-formats");
const ajv=formats(new Ajv({strict:true,allErrors:true}));
for(const file of readdirSync("schemas"))ajv.addSchema(JSON.parse(readFileSync("schemas/"+file,"utf8")));
for(const file of readdirSync("schemas"))ajv.getSchema(JSON.parse(readFileSync("schemas/"+file,"utf8")).$id);
const names={"graph.json":"graph","pack.json":"relation-pack","request.json":"composition-request","policy.json":"policy","projection-spec.json":"projection-spec"};
for(const file of readdirSync("fixtures/laws")){
 const validator=ajv.getSchema("urn:patamaps:draft:1:schema:"+names[file]);
 if(!validator(JSON.parse(readFileSync("fixtures/laws/"+file,"utf8"))))throw Error(file+JSON.stringify(validator.errors));
}
const proposed=spawnSync(resolve(process.argv[3]),["derive","fixtures/laws/graph.json","fixtures/laws/request.json","--relation-pack","fixtures/laws/pack.json"],{encoding:"utf8"});
if(proposed.status!==0)throw Error(proposed.stdout+proposed.stderr);
const proof=JSON.parse(proposed.stdout).derivation,validator=ajv.getSchema("urn:patamaps:draft:1:schema:derivation");
if(!validator(proof))throw Error(JSON.stringify(validator.errors));
let scientific=0;
if(process.argv[4]){
 const directory=resolve(process.argv[4]);
 const imported=JSON.parse(readFileSync(resolve(directory,"imported.json"),"utf8"));
 const options=JSON.parse(readFileSync(resolve(directory,"crate-options.json"),"utf8"));
 const crate=JSON.parse(readFileSync(resolve(directory,"crate.json"),"utf8"));
 for(const [name,value] of [["sssom-document",imported.document],["sssom-source",options.source],["scientific-crate-options",options],["scientific-crate",crate]]){
  const validate=ajv.getSchema("urn:patamaps:draft:1:schema:"+name);
  if(!validate(value))throw Error(name+JSON.stringify(validate.errors));
  if(validate({...value,unknownField:true}))throw Error(name+" allowed an unknown top-level field");
  scientific++;
 }
}
console.log(`PASS: all successor schemas compile locally; five law fixtures, an actual Rust derivation and ${scientific} actual scientific transports validate; scientific top-level unknown fields refuse.`);
