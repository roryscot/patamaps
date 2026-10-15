import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {compileMetamap} from "../reference/metamap-399747a4ad05/dist/viability.js";
import {RelationRegistry,coreRelationPack} from "../reference/metamap-399747a4ad05/dist/relations.js";
const read=name=>JSON.parse(readFileSync(new URL("../reference/metamap-399747a4ad05/examples/"+name,import.meta.url),"utf8"));
const codes=["UNDECLARED_LOSSINESS","UNDECLARED_IMPACT_DIRECTION","UNVERIFIED_DETERMINISM","UNVERIFIED_REVERSIBILITY"];
const evaluatedAt="2026-09-02T00:00:00.000Z";
const records=[];
for(const code of codes){
 const graph=read("example-authority-graph.json");
 const policy=read("example-viability-policy.json");
 const pack=structuredClone(coreRelationPack);
 const mapping=graph.mappings[3];
 const declaration=policy.mappings.find(d=>d.mapping===mapping.id);
 if(code==="UNDECLARED_LOSSINESS")mapping.lossiness="unknown";
 if(code==="UNDECLARED_IMPACT_DIRECTION")delete pack.relations.find(r=>r.id===mapping.relation).impactDirection;
 if(code==="UNVERIFIED_DETERMINISM")mapping.transform={adapter:"fixture",version:"1",deterministic:false};
 if(code==="UNVERIFIED_REVERSIBILITY"){
  declaration.reversibility="reversible";
  mapping.transform={adapter:"fixture",version:"1",deterministic:true,reversible:false};
 }
 const evaluate=p=>compileMetamap(structuredClone(graph),structuredClone(p),{
  context:{environment:"production",maintenance:false},
  evaluatedAt,relationRegistry:new RelationRegistry([structuredClone(pack)])
 });
 const before=evaluate(policy);
 assert.equal(before.status,"rejected",code);
 assert(before.issues.some(i=>i.code===code&&i.subjectId===mapping.id&&i.severity==="error"),code);
 const waiver={id:"urn:waiver:reference-bounded",codes:[code],subjects:[mapping.id],reason:"Explicit temporary migration exception",assertedBy:"team:architecture",expiresAt:"2026-09-03T00:00:00.000Z"};
 const allowed=structuredClone(policy);allowed.waivers=[waiver];
 const after=evaluate(allowed);
 assert.equal(after.status,"viable",code);
 assert(after.issues.some(i=>i.code===code&&i.subjectId===mapping.id&&i.severity==="warning"&&i.waivedBy===waiver.id),code);
 const wrong=structuredClone(allowed);wrong.waivers[0].subjects=[graph.mappings[0].id];
 const scope=evaluate(wrong);assert.equal(scope.status,"rejected",code);
 const expired=structuredClone(allowed);expired.waivers[0].expiresAt=evaluatedAt;
 const expiry=evaluate(expired);assert.equal(expiry.status,"rejected",code);
 assert(expiry.issues.some(i=>i.code==="EXPIRED_WAIVER"),code);
 records.push({code,inputs:{graph,policy,pack,waiver,context:{environment:"production",maintenance:false},evaluatedAt},before,after,scope,expiry});
}
console.log(JSON.stringify({status:"passed",referenceEngine:"399747a4ad05a37cd8db1cedd53048fad2175be4",scope:"Four original-runtime ordinary waiver cases, each unwaived, exact, wrong-subject and expired. Native controls use their own routing fixture; this does not claim identical wire inputs.",records}));

