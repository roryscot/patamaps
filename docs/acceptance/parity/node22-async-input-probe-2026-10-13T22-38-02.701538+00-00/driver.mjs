import { spawn } from 'node:child_process';
import { readFileSync,writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const root="/Users/admin/dev/patamaps/patamaps",prior="/Users/admin/dev/patamaps/patamaps/docs/acceptance/parity/viability-timeout-diagnostic-2026-10-13T21-31-04.553167+00-00",out=dirname(fileURLToPath(import.meta.url)),command=JSON.parse(readFileSync(prior+'/failed-native-command.json')),input=readFileSync(prior+'/failed-native-input.json'),rows=[];
for(let i=0;i<20;i++){
 const start=performance.now();const child=spawn(command[0],command.slice(1),{env:{},stdio:['pipe','pipe','pipe'],timeout:65000});
 writeFileSync(out+'/live.json',JSON.stringify({pid:child.pid,iteration:i+1,startedAt:Date.now()}));
 let stdout='',stderr='';child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');child.stdout.on('data',c=>{stdout+=c;assert(Buffer.byteLength(stdout)<=16*1024*1024+1)});child.stderr.on('data',c=>{stderr+=c;assert(Buffer.byteLength(stderr)<=16*1024*1024+1)});
 const result=await new Promise(resolve=>{child.once('error',error=>resolve({error:error.message}));child.once('close',(status,signal)=>resolve({status,signal}));child.stdin.end(input)});
 writeFileSync(out+'/input-'+(i+1)+'.stdout',stdout);writeFileSync(out+'/input-'+(i+1)+'.stderr',stderr);const row={iteration:i+1,elapsedSeconds:(performance.now()-start)/1000,...result,stdoutBytes:Buffer.byteLength(stdout),stderrBytes:Buffer.byteLength(stderr)};rows.push(row);writeFileSync(out+'/receipt.json',JSON.stringify({scope:'Diagnostic async transport only, no platform/full parity acceptance',node:process.version,uv:process.versions.uv,inputDigest:'sha256:'+createHash('sha256').update(input).digest('hex'),binaryDigest:'sha256:'+createHash('sha256').update(readFileSync(command[0])).digest('hex'),rows},null,2)+'\n');console.log(JSON.stringify(row));assert.equal(result.status,0);assert.equal(result.signal,null);
}
