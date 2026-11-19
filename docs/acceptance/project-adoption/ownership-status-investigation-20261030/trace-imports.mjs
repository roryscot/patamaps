import{performance}from'node:perf_hooks';
const files=['/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs','/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs','/Users/admin/Documents/Codex/storage-safeguards/resource-executor.mjs'];
for(const file of files){process.stdout.write(JSON.stringify({stage:'import-start',file,ms:performance.now()})+'\n');await import(file);process.stdout.write(JSON.stringify({stage:'import-finish',file,ms:performance.now()})+'\n');}
