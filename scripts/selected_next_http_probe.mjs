/** Bounded selected-output HTTP probe; callers bind this source into their command argv. */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import net from "node:net";
import {spawn} from "node:child_process";
import {setTimeout as delay} from "node:timers/promises";

const hash=b=>"sha256:"+crypto.createHash("sha256").update(b).digest("hex");
const requireCheck=(value,code)=>{if(!value)throw Error(code);};
export async function probe(cfg){
 const report={status:"running",cases:[],readinessRequests:0,serverStopped:false,producerUnavailableThroughout:true};
 const unavailable=()=>{
  for(const p of cfg.unavailable){
   let present=true;try{fs.lstatSync(p);}catch(e){if(e.code==="ENOENT")present=false;else throw e;}
   requireCheck(!present,"OWNER_PRODUCER_REAPPEARED");
  }
 };
 requireCheck(process.version==="v22.23.3","OWNER_NODE_VERSION");
 requireCheck(cfg.assets.length===2&&cfg.unavailable.length===3,"OWNER_PROBE_PROFILE");
 unavailable();
 const holder=net.createServer();
 await new Promise((resolve,reject)=>{holder.once("error",reject);holder.listen(0,"127.0.0.1",resolve);});
 const port=holder.address().port;
 await new Promise((resolve,reject)=>holder.close(e=>e?reject(e):resolve()));
 const root="http://127.0.0.1:"+port;
 const stdout=fs.openSync(cfg.logPrefix+".stdout","wx",0o600);
 const stderr=fs.openSync(cfg.logPrefix+".stderr","wx",0o600);
 let child,closed=false,exit=null,cancelled=false,logFailure=false;
 const counts={stdout:0,stderr:0};
 const record=()=>fs.writeFileSync(cfg.processRecord,JSON.stringify({pid:child?.pid??null,closed,exit,port,logBytes:counts})+"\n",{mode:0o600});
 let exited;
 const signal=()=>{cancelled=true;if(child&&!closed)child.kill("SIGTERM");};
 process.on("SIGTERM",signal);process.on("SIGINT",signal);
 const live=()=>{unavailable();requireCheck(!cancelled,"OWNER_PROBE_CANCELLED");requireCheck(!logFailure,"OWNER_SERVER_LOG_BOUND");requireCheck(!closed,"OWNER_SERVER_EXITED");};
 async function request(url,ua){
  live();
  const response=await fetch(root+url,{headers:{"user-agent":ua},redirect:"manual",signal:AbortSignal.timeout(10000)});
  let length=0;const chunks=[];
  for await(const bytes of response.body){length+=bytes.length;requireCheck(length<=8388608,"OWNER_HTTP_BODY_BOUND");chunks.push(bytes);}
  const body=Buffer.concat(chunks);
  live();
  return {status:response.status,type:response.headers.get("content-type")??"",body};
 }
 const ua="Mozilla/5.0 PatamapsOwnerRuntimeQualification/1.0";
 const add=(role,response,extra={})=>report.cases.push({role,status:response.status,bodyBytes:response.body.length,bodyDigest:hash(response.body),...extra});
 try{
  child=spawn(process.execPath,[path.join(cfg.app,"server.js")],{cwd:cfg.app,env:{...process.env,HOSTNAME:"127.0.0.1",PORT:String(port)},stdio:["ignore","pipe","pipe"]});
  exited=new Promise(resolve=>{
   child.once("error",error=>{exit={errorCode:error.code??"SPAWN"};});
   child.once("close",(code,signalName)=>{closed=true;exit??={code,signal:signalName};record();resolve();});
  });
  for(const [name,stream,fd] of [["stdout",child.stdout,stdout],["stderr",child.stderr,stderr]]){
   stream.on("data",bytes=>{
    const remaining=Math.max(0,4194304-counts[name]);
    if(remaining)fs.writeSync(fd,bytes.subarray(0,remaining));
    counts[name]+=bytes.length;
    if(counts[name]>4194304){logFailure=true;if(!closed)child.kill("SIGTERM");}
   });
  }
  record();
  const started=performance.now();
  while(true){
   live();requireCheck(performance.now()-started<30000,"OWNER_READINESS_TIMEOUT");
   try{
    const response=await request("/",ua);report.readinessRequests++;
    if(response.status===200&&response.type.includes("text/html")&&response.body.includes(Buffer.from("<html")))break;
   }catch(error){
    if(!["TypeError","TimeoutError"].includes(error.name))throw error;
    report.readinessRequests++;
   }
   await delay(100);
  }
  let response=await request("/",ua);
  requireCheck(response.status===200&&response.type.includes("text/html")&&response.body.includes(Buffer.from("<html")),"OWNER_ROOT_HTML");
  add("public-root-html",response);
  response=await request("/login",ua);
  const login=response.body.toString("utf8");
  requireCheck(response.status===200&&response.type.includes("text/html")&&login.includes('type="email"')&&login.includes('type="password"')&&login.includes('href="/register"'),"OWNER_LOGIN_HTML");
  add("public-login-html",response);
  response=await request("/login","curl/8.7.1");
  requireCheck(response.status===403&&response.body.toString("utf8")==="Forbidden","OWNER_PROXY_BOT_REFUSAL");
  add("original-proxy-bot-refusal",response);
  response=await request("/.env",ua);
  requireCheck(response.status===404&&response.body.toString("utf8")==="Not Found","OWNER_PROXY_PATH_REFUSAL");
  add("original-proxy-sensitive-path-refusal",response);
  for(let i=0;i<cfg.assets.length;i++){
   const expected=cfg.assets[i];
   response=await request("/_next/static/"+expected.relative,ua);
   requireCheck(response.status===200&&response.body.length===expected.bytes&&hash(response.body)===expected.digest&&response.body.includes(Buffer.from(cfg.marker)),"OWNER_COMPILED_EDIT_HTTP");
   add("selected-edited-static-"+(i+1),response,{selectedDigestMatched:true,editedMarkerPresent:true});
  }
  response=await request("/_next/static/patamaps-runtime-missing-20261027.js",ua);
  requireCheck(response.status===404,"OWNER_MISSING_STATIC_REFUSAL");
  add("missing-static-refusal",response);
  requireCheck(report.cases.length===7,"OWNER_HTTP_CASES");
  report.status="passed-current-owner-edited-runtime-http";
 }catch(error){
  report.status="failed";report.failureCodes=[...new Set(String(error.message).match(/OWNER_[A-Z_]+/g)??[])];throw error;
 }finally{
  try{
   if(child&&!closed){
    child.kill("SIGTERM");
    await Promise.race([exited,delay(5000)]);
    if(!closed){child.kill("SIGKILL");await Promise.race([exited,delay(5000)]);}
   }
   requireCheck(!child||closed,"OWNER_SERVER_SURVIVED");
   report.serverStopped=Boolean(child&&closed);
   report.serverExit=exit;report.serverLogBytes=counts;
   unavailable();record();
  }finally{
   process.off("SIGTERM",signal);process.off("SIGINT",signal);
   fs.closeSync(stdout);fs.closeSync(stderr);
   fs.writeFileSync(cfg.report,JSON.stringify(report,null,2)+"\n",{mode:0o600});
  }
 }
 requireCheck(report.status==="passed-current-owner-edited-runtime-http"&&report.serverStopped,"OWNER_RUNTIME_INCOMPLETE");
 console.log(JSON.stringify(report));
}
