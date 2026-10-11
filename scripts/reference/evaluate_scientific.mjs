import {readFileSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const [root,casesFile,output]=process.argv.slice(2);
const {parseSssomTsv,interpretSssomDocument,exportSssomTsv}=await import(pathToFileURL(join(root,'dist/index.js')));
const {SssomTsvAdapter}=await import(pathToFileURL(join(root,'dist/adapters/sssom-tsv.js')));
const cases=JSON.parse(readFileSync(casesFile,'utf8'));const outputs=[];
for (const c of cases) {
  try {
    const document=parseSssomTsv(c.tsv,c.metadata);
    const interpretation=interpretSssomDocument(document);
    const exported=exportSssomTsv(document);
    const result={id:c.id,status:'source-imported',document,interpretation,exported};
    if (c.sourceOptions) {
      const work=join(root,'scientific-differential');
      const {mkdirSync}=await import('node:fs');mkdirSync(work,{recursive:true});
      writeFileSync(join(work,'source.tsv'),c.tsv);
      const options=c.sourceOptions;
      const discovered=await new SssomTsvAdapter().discover({id:options.id,adapter:'sssom-tsv',path:'source.tsv',formatVersion:'1.0.0',sourceRevision:options.sourceRevision,provenance:options.provenance},{namespace:options.namespace,repository:'metamap-scientific-fixture',repositoryRoot:work});
      result.graph=discovered.document;
    }
    outputs.push(result);
  } catch(e) {outputs.push({id:c.id,status:'rejected',code:e.code??null,message:e.message});}
}
writeFileSync(output,JSON.stringify(outputs,null,2)+'\n');
