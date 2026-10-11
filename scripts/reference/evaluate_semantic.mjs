// Runs the pinned engine's independently built code; never successor code.
import {readFileSync} from "node:fs";
import {pathToFileURL} from "node:url";
import {resolve} from "node:path";
const {composeCorrespondences,compileMetamap,compileProjection,compilePathTree,RelationRegistry}=await import(pathToFileURL(resolve(process.argv[2],"dist/index.js")).href);
const cases=JSON.parse(readFileSync(process.argv[3],"utf8"));
const result=[];
for(const input of cases){
 const {graph,pack,request,policy,spec}=structuredClone(input);
 for(const v of [graph,pack,request,policy,spec])delete v.documentType;
 graph.schemaVersion="2.0.0";pack.schemaVersion="2.0.0";request.schemaVersion="1.0.0";policy.schemaVersion="2.0.0";spec.schemaVersion="2.0.0";
 const semantic=policy.semantics;delete policy.semantics;delete semantic.interpretation;Object.assign(policy,semantic);
 const requirements=spec.semantics;delete spec.semantics;Object.assign(spec,requirements);
 const registry=new RelationRegistry([pack]);
 const proposed=composeCorrespondences(graph,request,registry);
 const report={id:input.id,proposed};
 if(proposed.status==="proposed"){
  graph.mappings.push(proposed.mapping);policy.derivations=[proposed.derivation];policy.assessments=request.assessments;policy.evidence=request.evidence;
  let context=request.context;
  if(input.after==="stale-context")context={environment:"changed"};
  if(input.after==="changed-premise")graph.mappings[0].provenance.confidence=0.8;
  if(input.after==="changed-evidence")policy.evidence[0].producer="changed";
  if(input.after==="missing-proof")policy.derivations=[];
  const compiled=compileMetamap(graph,policy,{context,evaluatedAt:input.evaluatedAt,relationRegistry:registry});
  report.compiled=compiled;
  if(compiled.status==="viable")report.projected=compileProjection(graph,compiled.generation,spec,{semanticPolicy:policy,relationRegistry:registry});
  if(report.projected?.status==="projected" && spec.pathTree)report.tree=compilePathTree(report.projected.projection,spec);
 }
 result.push(report);
}
process.stdout.write(JSON.stringify(result,null,2)+"\n");
