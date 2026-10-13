import { readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { performance } from 'node:perf_hooks';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const out=dirname(fileURLToPath(import.meta.url)), prior="/Users/admin/dev/patamaps/patamaps/docs/acceptance/parity/viability-timeout-diagnostic-2026-10-13T21-31-04.553167+00-00", label=process.argv[2];
const command=JSON.parse(readFileSync(prior+'/failed-native-command.json')), input=readFileSync(prior+'/failed-native-input.json','utf8');
const rows=[];
for(let i=0;i<10;i++){
 writeFileSync(out+'/live.json',JSON.stringify({node:process.execPath,pid:process.pid,label,iteration:i+1,startedAt:Date.now()}));
 const start=performance.now(); const result=spawnSync(command[0],command.slice(1),{input,encoding:'utf8',env:{},timeout:65000,maxBuffer:16*1024*1024+1});
 const row={iteration:i+1,elapsedSeconds:(performance.now()-start)/1000,pid:result.pid,status:result.status,signal:result.signal,error:result.error?.message,stdoutBytes:Buffer.byteLength(result.stdout??''),stderrBytes:Buffer.byteLength(result.stderr??'')}; rows.push(row);
 writeFileSync(out+'/'+label+'-'+(i+1)+'.stdout',result.stdout??'');writeFileSync(out+'/'+label+'-'+(i+1)+'.stderr',result.stderr??'');
 writeFileSync(out+'/'+label+'.json',JSON.stringify({node:process.version,scope:'Repeated exact-input diagnostic; no full-corpus acceptance',rows},null,2)+'\n');console.log(JSON.stringify({label,...row}));
 if(result.status!==0) process.exit(1);
}
