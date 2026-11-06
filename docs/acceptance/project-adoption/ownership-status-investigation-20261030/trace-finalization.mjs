import{Scheduler,nativeFinalizationPending}from'/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import{performance}from'node:perf_hooks';
const mark=x=>process.stdout.write(JSON.stringify(x)+'\n');
mark({stage:'import-complete',ms:performance.now()});const t=performance.now();
const rows=new Scheduler().requests();mark({stage:'records-read',ms:performance.now()-t,count:rows.length});
let pending=0;mark({stage:'finalization-start'});
for(const r of rows){const start=performance.now();if(nativeFinalizationPending(r))pending++;const ms=performance.now()-start;if(ms>10)mark({stage:'finalization-record',id:r.id,ms});}
mark({stage:'finalization-complete',pending,ms:performance.now()-t});
