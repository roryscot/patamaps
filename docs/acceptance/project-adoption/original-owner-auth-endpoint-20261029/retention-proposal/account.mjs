import fs from'node:fs';import path from'node:path';import os from'node:os';import{pathToFileURL}from'node:url';
const config=JSON.parse(fs.readFileSync('/Users/admin/Documents/Codex/storage-safeguards/projects.json','utf8'));
const engine=await import(pathToFileURL(config.engine));const project=config.projects.patamaps;const policy=engine.loadPolicy();
const roots=[project.root,...(project.retentionRoots??[]),...config.cacheRoots].filter(fs.existsSync);
for(const tmp of[...new Set([os.tmpdir(),'/private/tmp'])].filter(fs.existsSync))for(const e of fs.readdirSync(tmp,{withFileTypes:true}))if(e.isDirectory()&&project.temporaryPrefixes.some(p=>e.name.startsWith(p)))roots.push(path.join(tmp,e.name));
const unique=[...new Set(roots)].sort();const retained=engine.retainedBytes(unique);
const out={observedAtUtc:new Date().toISOString(),retainedAllocatedBytesUpperBound:retained,maximumRunGrowthBytes:policy.maximumRunGrowthBytes,maximumRetainedBytes:policy.maximumRetainedBytes,reserveFreeBytes:policy.reserveFreeBytes,inventoryRoots:unique.length,requiredReleaseBytes:Math.max(0,retained+policy.maximumRunGrowthBytes-policy.maximumRetainedBytes),filesDeleted:0,policyChanged:false};
fs.writeFileSync('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/owner-auth-endpoint-20261029/retention-review/capacity.json',JSON.stringify(out,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(out));
