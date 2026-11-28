import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
const need=(v,c)=>{if(!v)throw Error(c);};
const hashFile=p=>{const h=crypto.createHash('sha256'),b=Buffer.alloc(1048576),fd=fs.openSync(p,'r');try{let n;while((n=fs.readSync(fd,b,0,b.length,null)))h.update(b.subarray(0,n));return 'sha256:'+h.digest('hex');}finally{fs.closeSync(fd);}};
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
function checkTree(root,rows){
 const expected=new Map(Array.isArray(rows)?rows.map(r=>[r.path,r]):Object.entries(rows)),actual=new Set();
 const visit=(p,name)=>{const s=fs.lstatSync(p),isRoot=name==='.';if(!isRoot||expected.has('.')){const r=expected.get(name);need(r,'OWNER_BROWSER_INPUT_MEMBERSHIP');actual.add(name);need((s.mode&0o7777)===r.mode,'OWNER_BROWSER_INPUT_MODE');if(s.isSymbolicLink())need(r.kind==='symlink'&&fs.readlinkSync(p)===r.target,'OWNER_BROWSER_INPUT_LINK');else if(s.isDirectory())need(r.kind==='directory','OWNER_BROWSER_INPUT_KIND');else{need(s.isFile()&&r.kind==='file'&&s.size===r.bytes&&hashFile(p)===r.digest,'OWNER_BROWSER_INPUT_BYTES');}}
  if(s.isDirectory()&&!s.isSymbolicLink())for(const n of fs.readdirSync(p))visit(path.join(p,n),name==='.'?n:name+'/'+n);
 };
 visit(root,'.');need(actual.size===expected.size,'OWNER_BROWSER_INPUT_MEMBERSHIP');
}
export function preflight(c){
 need(hashFile(c.toolsManifest)===c.toolsManifestDigest,'OWNER_BROWSER_INPUT_MANIFEST');
 checkTree(c.tools,json(c.toolsManifest));
 need(hashFile(c.cacheManifest)===c.cacheManifestDigest,'OWNER_BROWSER_CACHE_MANIFEST');
 checkTree(c.cache,json(c.cacheManifest));
 need(hashFile(c.node)===c.nodeDigest,'OWNER_BROWSER_NODE_CHANGED');
}
const write=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});
const listen=s=>new Promise((resolve,reject)=>{s.once('error',reject);s.listen(0,'127.0.0.1',resolve);});
const close=s=>new Promise(resolve=>{if(!s)return resolve();s.close(resolve);s.closeAllConnections?.();});
export async function inspect(c,{root,assertLive}){
 assertLive();fs.mkdirSync(c.inspection);fs.mkdirSync(path.join(c.inspection,'home'));fs.mkdirSync(path.join(c.inspection,'tmp'));
 const report={status:'running',projectCounts:{},upstreamCases:0,apiAccepted:false,originPolicy:'owned-frontend-and-api-origins-only'};
 const counters={forwarded:0,denied:0,connectDenied:0,bodyLimitFailures:0,upstreamErrors:0};
 let proxy,spy,front,child,closed=false,childCode=null,cancelled=false;
 const live=()=>{assertLive();need(!cancelled,'OWNER_BROWSER_CANCELLED');};
 const stop=()=>{cancelled=true;if(child&&!closed)child.kill('SIGTERM');};
 process.on('SIGTERM',stop);process.on('SIGINT',stop);
 try{
  const origin=new URL(root);
  front=http.createServer((req,res)=>{
   const u=new URL(req.url,root);if(u.origin!==origin.origin){res.writeHead(403);res.end();return;}
   const upstream=http.request(u,{method:req.method,headers:{...req.headers,host:origin.host}},r=>{
    res.writeHead(r.statusCode??502,r.headers);let bytes=0;
    r.on('data',x=>{bytes+=x.length;if(bytes>8388608){upstream.destroy();res.destroy();return;}res.write(x);});
    r.on('end',()=>res.end());r.on('error',()=>res.destroy());
   });upstream.on('error',()=>{if(!res.headersSent)res.writeHead(502);res.end();});req.pipe(upstream);
  });
  await new Promise((resolve,reject)=>{front.once('error',reject);front.listen(13000,'127.0.0.1',resolve);});
  const browserRoot='http://127.0.0.1:13000';
  const allowedOrigins=new Set([browserRoot,'http://127.0.0.1:18765']);

  proxy=http.createServer((req,res)=>{
   let target;try{target=new URL(req.url,root);}catch{counters.denied++;res.writeHead(403);res.end();return;}
   if(!allowedOrigins.has(target.origin)||target.username||target.password){counters.denied++;res.writeHead(403);res.end();return;}
   counters.forwarded++;
   const headers={...req.headers,host:origin.host};delete headers['proxy-connection'];delete headers['proxy-authorization'];
   const upstream=http.request(target,{method:req.method,headers},response=>{
    res.writeHead(response.statusCode??502,response.headers);let bytes=0;
    response.on('data',chunk=>{bytes+=chunk.length;if(bytes>8388608){counters.bodyLimitFailures++;upstream.destroy();res.destroy();return;}res.write(chunk);});
    response.on('end',()=>res.end());response.on('error',()=>res.destroy());
   });
   upstream.on('error',()=>{if(!res.destroyed){counters.upstreamErrors++;if(!res.headersSent)res.writeHead(502);res.end();}});
   req.on('error',()=>upstream.destroy());req.pipe(upstream);
  });
  proxy.on('connect',(_req,socket)=>{counters.connectDenied++;socket.end('HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');});
  proxy.on('upgrade',(_req,socket)=>{counters.denied++;socket.destroy();});
  await listen(proxy);const proxyUrl='http://127.0.0.1:'+proxy.address().port;
  const viaProxy=url=>new Promise((resolve,reject)=>{const q=http.request(proxyUrl,{method:'GET',path:url,headers:{'user-agent':'Mozilla/5.0 PatamapsOwnerRuntimeQualification/1.0'}},r=>{r.resume();r.on('end',()=>resolve(r.statusCode));});q.on('error',reject);q.end();});
  need(await viaProxy(browserRoot+'/')===200,'OWNER_BROWSER_PROXY_ALLOWED_ROOT');
  let spyRequests=0;spy=http.createServer((_req,res)=>{spyRequests++;res.end('not-a-provider');});await listen(spy);
  need(await viaProxy('http://127.0.0.1:'+spy.address().port+'/')===403&&spyRequests===0,'OWNER_BROWSER_PROXY_ORIGIN_REFUSAL');
  await close(spy);spy=null;report.proxyOriginRefusalPassed=true;
  const token=crypto.randomBytes(16).toString('hex');
  const env={PATH:path.dirname(c.node)+':/usr/bin:/bin:/usr/sbin:/sbin',HOME:path.join(c.inspection,'home'),TMPDIR:path.join(c.inspection,'tmp')+'/',LANG:'en_US.UTF-8',TZ:'UTC',CI:'1',NODE_OPTIONS:'--max-old-space-size=4096',PYTHONDONTWRITEBYTECODE:'1',PLAYWRIGHT_BROWSERS_PATH:c.cache,PLAYWRIGHT_SKIP_BROWSER_GC:'1',PLAYWRIGHT_HTML_OPEN:'never',PLAYWRIGHT_TEST_BASE_URL:browserRoot,PATAMAPS_OWNED_AUTH_CONFIG:c.ownedAuthConfig,PATAMAPS_TEST_PROXY:proxyUrl,PATAMAPS_BROWSER_OUTPUT:c.inspection,PATAMAPS_BROWSER_OWNER:token,DEBUG:'pw:browser'};
  const cfg={work:c.inspection,cache:c.cache,tmp:env.TMPDIR.replace(/\/$/,''),ownerToken:token,node:c.node,script:path.join(c.tools,'driver','test-cli.cjs'),cli:path.join(c.tools,'packages/web/node_modules/@playwright/test/cli.js'),arguments:['test',c.authSpec,'--config',c.authConfig],env};
  const cfgPath=path.join(c.inspection,'browser-config.json');write(cfgPath,cfg);
  const out=fs.openSync(path.join(c.inspection,'node.stdout'),'wx',0o600),err=fs.openSync(path.join(c.inspection,'node.stderr'),'wx',0o600);
  const began=performance.now();
  try{
   child=spawn(c.python,['-B',path.join(c.tools,'driver','owned_browser_guard.py'),cfgPath],{cwd:path.join(c.tools,'packages/web'),env,stdio:['ignore',out,err],detached:true});
   write(path.join(c.inspection,'guardian-process.json'),{pid:child.pid});
   const exited=new Promise(resolve=>{child.once('error',()=>{childCode=-1;});child.once('close',code=>{closed=true;childCode??=code;resolve();});});
   while(!closed){live();need(performance.now()-began<120000,'OWNER_BROWSER_SUITE_TIMEOUT');need(fs.fstatSync(out).size<=4194304&&fs.fstatSync(err).size<=4194304,'OWNER_BROWSER_SUITE_LOG_BOUND');await delay(100);}
   await exited;need(childCode===0,'OWNER_BROWSER_UPSTREAM_SUITE_FAILED');
  }finally{
   if(child&&!closed){child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('close',r)),delay(10000)]);need(closed,'OWNER_BROWSER_GUARDIAN_SURVIVED');}
   fs.closeSync(out);fs.closeSync(err);
  }
  live();
  const guard=json(path.join(c.inspection,'guard-result.json'));need(guard.status==='stopped-owned-browser-groups'&&!guard.ownershipUncertain&&guard.groups.length>0&&guard.groups.every(g=>g.stopped),'OWNER_BROWSER_GROUP_SURVIVED');
  const result=json(path.join(c.inspection,'results.json')),tests=[];
  const walk=s=>{for(const spec of s.specs??[])for(const t of spec.tests??[])tests.push(t);for(const sub of s.suites??[])walk(sub);};walk(result);
  const names=['chromium','firefox','webkit','Mobile Chrome','Mobile Safari'];
  need(result.config.globalTimeout===120000&&result.config.workers===1,'OWNER_BROWSER_UPSTREAM_BOUNDS_CHANGED');
  need(result.config.projects.length===5&&names.every(n=>result.config.projects.some(p=>p.name===n)),'OWNER_BROWSER_MATRIX_CHANGED');
  need(result.stats.expected===5&&result.stats.unexpected===0&&result.stats.flaky===0&&result.stats.skipped===0&&tests.length===5,'OWNER_BROWSER_CASE_COUNTS');
  for(const t of tests){need(t.status==='expected'&&t.results.length===1&&t.results[0].status==='passed','OWNER_BROWSER_CASE_FAILED');report.projectCounts[t.projectName]=(report.projectCounts[t.projectName]??0)+1;}
  need(names.every(n=>report.projectCounts[n]===1)&&Object.keys(report.projectCounts).length===5,'OWNER_BROWSER_PROJECT_COUNTS');
  need(counters.bodyLimitFailures===0,'OWNER_BROWSER_PROXY_BODY_BOUND');
  preflight(c);live();
  report.status='passed-original-owner-five-project-auth';report.realAuthenticationAccepted=true;report.authCases=5;report.upstreamCases=0;report.skipped=0;report.flaky=0;report.browserGroups=guard.groups.length;report.producerUnavailableThroughout=true;report.ownedGuardianClosed=closed;report.proxy=counters;
 }catch(error){report.status='failed';report.failureCodes=[...new Set(String(error.message).match(/OWNER_[A-Z_]+/g)??[])];throw error;
 }finally{
  await close(spy);await close(proxy);await close(front);report.proxyClosed=true;report.frontendForwarderClosed=true;
  process.off('SIGTERM',stop);process.off('SIGINT',stop);write(path.join(c.inspection,'inspection.json'),report);
 }
}
