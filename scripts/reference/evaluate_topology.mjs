import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const root=resolve(process.argv[2]);
const {compileMetamap}=await import(pathToFileURL(resolve(root,'dist/viability.js')).href);
const {RelationRegistry,coreRelationPack}=await import(pathToFileURL(resolve(root,'dist/relations.js')).href);
const registry=new RelationRegistry([coreRelationPack,...['routing','application-topology'].map(n=>JSON.parse(readFileSync(resolve(root,`relation-packs/${n}.json`),'utf8')))]);
const cases=JSON.parse(readFileSync(process.argv[3],'utf8'));
console.log(JSON.stringify(cases.map(c=>({id:c.id,result:compileMetamap(c.graph,c.policy,{context:c.context,evaluatedAt:'2026-09-08T00:00:00.000Z',relationRegistry:registry})}))));
