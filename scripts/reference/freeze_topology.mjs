// Extract only the three pure fixture functions from the pinned original test.
// The source checkout and its tests are never rewritten or executed here.
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
const reference=resolve(process.argv[2]),require=createRequire(resolve(reference,'package.json')),ts=require('typescript');
const revision='399747a4ad05a37cd8db1cedd53048fad2175be4',path='src/__tests__/application-topology.test.ts';
const source=execFileSync('git',['-C',reference,'show',`${revision}:${path}`],{encoding:'utf8'});
const ast=ts.createSourceFile(path,source,ts.ScriptTarget.Latest,true);
const functions=ast.statements.filter(n=>ts.isFunctionDeclaration(n)&&['provenance','document','policy'].includes(n.name?.text));
if(functions.length!==3)throw Error('Pinned fixture functions missing');
const code=ts.transpileModule(functions.map(n=>n.getText(ast)).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
const original=vm.runInNewContext(code+'\nJSON.stringify({graph:document(),policy:policy(document())})',{}, {timeout:2000});
const value=JSON.parse(original),directory=resolve('fixtures/topology');mkdirSync(directory,{recursive:true});
const save=(name,v)=>writeFileSync(resolve(directory,name),JSON.stringify(v,null,2)+'\n');
save('original.json',value);
for(const [name,kind]of [['graph','graph'],['policy','policy']]){const v=structuredClone(value[name]);delete v.$schema;v.schemaVersion='0.1.0';v.documentType=kind;save(name+'.json',v);}
save('source-pin.json',{referenceEngine:revision,sourcePath:path,sourceSha256:createHash('sha256').update(source).digest('hex'),fixtureFunctions:['provenance','document','policy'],migration:'D001: draft envelopes only; original data retained in original.json'});
console.log('Frozen original topology graph/policy and explicit draft-envelope copies.');
