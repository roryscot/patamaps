// Runs only the freshly built, explicitly pinned reference in an isolated tree.
import {readFileSync} from "node:fs";
import {pathToFileURL} from "node:url";
import {resolve} from "node:path";
const root = process.argv[2];
const {compileMetamap, compileProjection, RelationRegistry} = await import(pathToFileURL(resolve(root,"dist/index.js")).href);
const cases = JSON.parse(readFileSync(process.argv[3],"utf8"));
const pack = JSON.parse(readFileSync(resolve(root,"relation-packs/routing.json"),"utf8"));
const results = [];
for (const fixture of cases) {
  const graph = structuredClone(fixture.graph), policy = structuredClone(fixture.policy), spec = structuredClone(fixture.spec);
  // Explicit D001 migration, preserving original record shapes and identifiers.
  delete graph.documentType; delete policy.documentType; delete spec.documentType;
  graph.schemaVersion = "2.0.0"; policy.schemaVersion = "1.0.0"; spec.schemaVersion = "1.0.0";
  const registry = new RelationRegistry(); registry.registerPack(pack);
  const compiled = compileMetamap(graph,policy,{context:fixture.context,evaluatedAt:fixture.evaluatedAt,relationRegistry:registry});
  const projected = compiled.status === "viable" ? compileProjection(graph,compiled.generation,spec,{relationRegistry:registry}) : undefined;
  results.push({id:fixture.id,compiled,projected});
}
process.stdout.write(JSON.stringify(results,null,2)+"\n");
