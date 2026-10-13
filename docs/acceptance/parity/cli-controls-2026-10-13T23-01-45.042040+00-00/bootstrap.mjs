
import cp from 'node:child_process';import {appendFileSync} from 'node:fs';import {syncBuiltinESMExports} from 'node:module';
const exe=process.env.PATAMAPS_TEST_NATIVE,trace=process.env.PATAMAPS_TEST_TRACE;
const log=(command,input,result)=>appendFileSync(trace,JSON.stringify({command,input,exitCode:result.status,signal:result.signal,stdout:result.stdout??'',stderr:result.stderr??'',processError:result.error?.message??null})+'\n');
const sync=cp.spawnSync;cp.spawnSync=function(file,args,options){const r=sync.call(this,file,args,options);if(file===exe)log([file,...args],options?.input??null,r);return r;};
const spawn=cp.spawn;cp.spawn=function(file,args,options){const p=spawn.call(this,file,args,options);if(file===exe){let input='',stdout='',stderr='';const end=p.stdin.end.bind(p.stdin);p.stdin.end=function(chunk,...rest){if(chunk)input+=chunk.toString();return end(chunk,...rest)};p.stdout.on('data',x=>stdout+=x.toString());p.stderr.on('data',x=>stderr+=x.toString());p.on('close',(status,signal)=>log([file,...args],input,{status,signal,stdout,stderr}));}return p;};
const exec=cp.execFile;cp.execFile=function(file,args,options,callback){return exec.call(this,file,args,options,(error,stdout,stderr)=>{if(file===exe)log([file,...args],null,{status:error?.code??0,signal:error?.signal??null,stdout,stderr,error:typeof error?.code==='string'?error:null});callback(error,stdout,stderr)});};
syncBuiltinESMExports();
