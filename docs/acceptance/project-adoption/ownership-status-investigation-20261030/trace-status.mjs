import{Scheduler,defaultDirectory,parallelEnabled}from'/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import fs from'node:fs';import path from'node:path';import{performance}from'node:perf_hooks';
const mark=(stage,extra={})=>process.stdout.write(JSON.stringify({stage,ms:performance.now(),...extra})+'\n');
mark('import-complete');
const root=path.join(defaultDirectory,'scheduler');const files=fs.readdirSync(path.join(root,'requests')).filter(n=>n.endsWith('.json'));
mark('request-directory-listed',{files:files.length});
const s=new Scheduler();const original=s.requests.bind(s);
s.requests=()=>{mark('request-parse-start');const rows=original();mark('request-parse-finish',{records:rows.length});return rows;};
mark('status-start');const status=s.status();mark('status-finish',{records:status.requests.length});
