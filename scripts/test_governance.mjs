// Independent WebCrypto owner, exact CLI signing bytes, isolated native consumer.
// Ephemeral private keys stay in memory; no signing material is logged or saved.
import assert from "node:assert/strict";
import {webcrypto,createHash} from "node:crypto";
import {mkdtempSync,readFileSync,writeFileSync,rmSync,readdirSync} from "node:fs";
import {tmpdir,homedir} from "node:os";
import {resolve,join} from "node:path";
import {spawnSync} from "node:child_process";
import {createRequire} from "node:module";
const cli=resolve(process.argv[2]),reference=resolve(process.argv[3]);
const tsc=join(reference,"node_modules/typescript/lib/tsc.js"),node=process.execPath,rustc=join(homedir(),".cargo/bin/rustc");
const work=mkdtempSync(join(tmpdir(),"patamaps-governance-"));
const consumer="urn:consumer:independent",environment="test",now="2026-10-10T01:00:00.000Z";
const checks=[];
const hash=bytes=>"sha256:"+createHash("sha256").update(bytes).digest("hex");
const write=(path,data)=>writeFileSync(join(work,path),JSON.stringify(data));
function run(args,expected=0){
 const p=spawnSync(cli,args,{cwd:work,encoding:"utf8",env:{...process.env,PATH:"/usr/bin:/bin"}});
 assert.equal(p.status,expected,p.stdout+p.stderr);return p.stdout;
}
function invoke(binary,args){const p=spawnSync(binary,args,{cwd:work,encoding:"utf8",env:{...process.env,PATH:"/usr/bin:/bin"}});assert.equal(p.status,0,p.stdout+p.stderr);return p.stdout;}
const require=createRequire(join(reference,"package.json")),Ajv=require("ajv/dist/2020.js").default,formats=require("ajv-formats");
const ajv=formats(new Ajv({strict:true,allErrors:true}));
for(const file of readdirSync("schemas"))ajv.addSchema(JSON.parse(readFileSync("schemas/"+file,"utf8")));
function schema(name,value){const v=ajv.getSchema("urn:patamaps:draft:1:schema:"+name);assert(v(value),JSON.stringify(v.errors));}
try {
 const keys=new Map();
 for(const principal of ["owner","agent"])keys.set(principal,await webcrypto.subtle.generateKey({name:"Ed25519"},true,["sign","verify"]));
 const publicKeys=await Promise.all(["owner","agent"].map(async p=>({id:p+"-key",principal:p,algorithm:"Ed25519",publicKey:Buffer.from(await webcrypto.subtle.exportKey("spki",keys.get(p).publicKey)).toString("base64"),validFrom:"2026-10-10T00:00:00.000Z",validUntil:"2026-10-10T08:00:00.000Z",revoked:false})));
 const actions=["activate","bootstrap","rollback","rebind-implementation","change-graph","change-authority","change-policy","relax-policy","raise-budget","add-waiver","change-law","change-source","change-context","change-projection"];
 const trust={schemaVersion:"0.1.0",documentType:"trusted-consumer",mode:"governed",id:"urn:trust:independent",revision:"1",consumer,environment,principals:[{id:"owner",role:"owner",revoked:false},{id:"agent",role:"agent",revoked:false}],keys:publicKeys,grants:["owner","agent"].map(principal=>({id:principal+"-grant",principal,actions,scopes:[{subject:"*",fact:"*"}],validFrom:"2026-10-10T00:00:00.000Z",validUntil:"2026-10-10T08:00:00.000Z",revoked:false}))};
 const rustSource='pub fn greet(input: &str) -> String { format!("Hello, {}!", input) }\n';
 const graph={schemaVersion:"0.1.0",documentType:"graph",id:"urn:graph:independent",namespace:"independent",revision:"1",entities:[{id:"urn:operation:greet",kind:"routing:command",attributes:{path:"/greet/:id"}},{id:"urn:handler:greet",kind:"routing:handler",locators:[{uri:"rust:crate::service::greet"},{uri:"typescript:./service.ts#greet"}]}],mappings:[{id:"urn:mapping:greet",relation:"routing:handled_by",sources:["urn:operation:greet"],targets:["urn:handler:greet"],cardinality:"one-to-one",lossiness:"lossless",provenance:{status:"declared",assertedBy:"independent-consumer"}}],authorities:[]};
 const policy={schemaVersion:"0.1.0",documentType:"policy",id:"urn:policy:independent",graph:{id:graph.id,revision:"1"},mappings:[{mapping:"urn:mapping:greet",coverage:"total",determinism:"deterministic",reversibility:"irreversible"}],constraints:[],evidence:[]};
 const spec={schemaVersion:"0.1.0",documentType:"projection-spec",id:"urn:projection:independent",consumer,select:{ids:["urn:operation:greet"]},slots:[{name:"handler",relation:"routing:handled_by",direction:"outgoing",cardinality:"exactly-one",targetKinds:["routing:handler"]}],pathTree:{}};
 for(const [name,value]of Object.entries({"trust.json":trust,"graph.json":graph,"policy.json":policy,"spec.json":spec,"sources.json":[{id:"urn:source:service",locator:"rust:crate::service",digest:hash(rustSource),byteLength:Buffer.byteLength(rustSource),content:rustSource}],"emissions.json":[{projection:spec.id,language:"rust",bindingSlot:"handler"},{projection:spec.id,language:"typescript",bindingSlot:"handler"}]}))write(name,value);
 schema("trusted-consumer",trust);schema("projection-spec",spec);
 run(["capture","graph.json","policy.json","--spec","spec.json","--source-receipts","sources.json","--relation-pack",resolve("relation-packs/routing.json"),"--as-of","2026-10-09T12:00:00Z","-o","capture.json"]);
 schema("capture",JSON.parse(readFileSync(join(work,"capture.json"),"utf8")));
 run(["propose","capture.json","--trust","trust.json","--consumer",consumer,"--environment",environment,"--proposer","agent","--emissions","emissions.json","-o","prepared.json"]);
 const prepared=JSON.parse(readFileSync(join(work,"prepared.json"),"utf8"));schema("prepared-candidate",prepared);schema("change-proposal",prepared.proposal);schema("artifact-manifest",prepared.proposal.artifacts);
 assert(prepared.proposal.requirements.some(r=>r.action==="bootstrap"));
 async function sign(principal,suffix="") {
  run(["approval-payload","prepared.json","--principal",principal,"--key",principal+"-key","--grant",principal+"-grant","--issued-at","2026-10-10T00:30:00.000Z","--expires-at","2026-10-10T02:00:00.000Z","-o",principal+"-payload.json","--overwrite"]);
  const payload=readFileSync(join(work,principal+"-payload.json"));assert.equal(payload.at(-1),125,"Signing file has no appended newline");schema("approval-payload",JSON.parse(payload));
  const signature=await webcrypto.subtle.sign({name:"Ed25519"},keys.get(principal).privateKey,Buffer.concat([payload,Buffer.from(suffix)]));
  write(principal+"-signature.json",Buffer.from(signature).toString("base64"));
  run(["attach-signature",principal+"-payload.json",principal+"-signature.json","-o",principal+"-approval.json","--overwrite"]);
  const approval=JSON.parse(readFileSync(join(work,principal+"-approval.json"),"utf8"));schema("approval",approval);return approval;
 }
 const verify=(principal,file="prepared.json",expected=0)=>JSON.parse(run(["verify-approval",file,principal+"-approval.json","--trust","trust.json","--now",now],expected));
 await sign("owner");assert.equal(verify("owner").status,"authorized-under-supplied-context");checks.push("independent-webcrypto-signature-over-exact-cli-file");
 await sign("agent");assert(verify("agent","prepared.json",1).issues.some(i=>i.code==="GOVERNANCE_OWNER_REQUIRED"));checks.push("agent-self-approval-refused");
 await sign("owner","\n");assert(verify("owner","prepared.json",1).issues.some(i=>i.code==="GOVERNANCE_BAD_SIGNATURE"));checks.push("appended-newline-signature-refused");await sign("owner");
 const swapped=structuredClone(prepared);swapped.files["bindings-0.rs"]+='\npub fn changed() {}\n';write("swapped.json",swapped);assert(verify("owner","swapped.json",1).issues.some(i=>i.code==="GOVERNANCE_ARTIFACT_BYTES_MISMATCH"));checks.push("changed-file-bytes-refused");
 for(const file of prepared.proposal.artifacts.files){const content=prepared.files[file.path];assert.equal(hash(content),file.byteDigest);assert.equal(Buffer.byteLength(content),file.byteLength);writeFileSync(join(work,file.path),content);}
 writeFileSync(join(work,"bindings.rs"),prepared.files["bindings-0.rs"]);writeFileSync(join(work,"bindings.ts"),prepared.files["bindings-1.ts"]);
 writeFileSync(join(work,"service.rs"),rustSource);writeFileSync(join(work,"service.ts"),'export function greet(input: string): string { return `Hello, ${input}!`; }\n');
 writeFileSync(join(work,"main.rs"),'mod service;mod bindings;fn main(){let id=bindings::SemanticId::parse("urn:operation:greet").unwrap();println!("{}",bindings::dispatch(id,"Ada"));}\n');
 writeFileSync(join(work,"consumer.ts"),'import {dispatch} from "./bindings.js";console.log(dispatch("urn:operation:greet","Ada"));\n');write("package.json",{type:"module"});
 invoke(rustc,["--edition=2024","main.rs","-o","consumer-rust"]);assert.equal(invoke(join(work,"consumer-rust"),[]).trim(),"Hello, Ada!");
 invoke(node,[tsc,"--strict","--target","ES2022","--module","NodeNext","--moduleResolution","NodeNext","consumer.ts","bindings.ts","service.ts"]);assert.equal(invoke(node,[join(work,"consumer.js")]).trim(),"Hello, Ada!");checks.push("exact-reviewed-rust-and-typescript-artifacts-execute");
 const report={scope:"pure external approval and isolated consumer; protected activation not attempted",checks,proposal:prepared.proposal,approval:JSON.parse(readFileSync(join(work,"owner-approval.json"),"utf8")),artifactPaths:Object.keys(prepared.files)};
 if(process.argv[4])writeFileSync(resolve(process.argv[4]),JSON.stringify(report,null,2)+"\n");
 console.log("PASS: "+checks.join(", ")+"; all governance schemas validate actual records; native CLI and Rust consumer execute with Node absent from PATH.");
}finally{rmSync(work,{recursive:true,force:true});}
