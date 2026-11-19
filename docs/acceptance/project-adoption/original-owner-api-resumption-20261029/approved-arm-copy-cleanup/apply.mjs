import {Scheduler} from '/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';
import {spawnSync} from 'node:child_process';
const s=new Scheduler();
await s.transaction(async()=>{
 const env={...process.env,PATAMAPS_CLEANUP_SCHEDULER_ROOT:s.root,PATAMAPS_CLEANUP_TRANSACTION_PID:String(process.pid)};
 const p=spawnSync('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/intel-python-3.13.16-20261013/runtime/python/bin/python3',['-I','-S','-B','/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/retention-review-20261029-arm-node-copy/delete-reviewed.py','--apply-reviewed'],{env,stdio:'inherit',timeout:120000});
 if(p.error)throw p.error;
 if(p.status!==0)throw new Error('Exact cleanup refused: '+p.status);
});
