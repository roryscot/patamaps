import{Scheduler}from'/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import{performance}from'node:perf_hooks';
const mark=v=>process.stdout.write(JSON.stringify(v)+'\n');
const s=new Scheduler();const original=s.requests.bind(s);
s.requests=()=>{const rows=original();rows.map=fn=>Array.prototype.map.call(rows,(r,i)=>{const t=performance.now();const v=fn(r,i);const ms=performance.now()-t;if(ms>10)mark({stage:'record-detail',id:r.id,index:i,state:r.state,ms});return v;});return rows;};
const t=performance.now();s.status();mark({stage:'complete',ms:performance.now()-t});
