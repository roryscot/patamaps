"""Retained process controls for the optional selected-owner ready inspector."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,sys,unittest
PARSER=argparse.ArgumentParser()
PARSER.add_argument("--work",required=True)
PARSER.add_argument("--probe",required=True)
PARSER.add_argument("--node",required=True)
ARGS,UNIT_ARGS=PARSER.parse_known_args()
WORK=Path(ARGS.work);PROBE=Path(ARGS.probe).resolve()
SERVER=r"""
const fs=require('node:fs');const http=require('node:http');const path=require('node:path');
const marker='PatamapsInspectorFixture';
fs.writeFileSync(path.join(__dirname,'started.marker'),'started');
http.createServer((req,res)=>{
 const ua=req.headers['user-agent']||'';
 let status=200,type='text/plain',body='';
 if(req.url==='/') {type='text/html';body='<html><body>fixture</body></html>';}
 else if(req.url==='/login'&&ua.startsWith('curl/')) {status=403;body='Forbidden';}
 else if(req.url==='/login') {type='text/html';body='<html><input type="email"><input type="password"><a href="/register">Register</a></html>';}
 else if(req.url==='/_next/static/fixture-1.js') {type='application/javascript';body='/*'+marker+'1*/';}
 else if(req.url==='/_next/static/fixture-2.js') {type='application/javascript';body='/*'+marker+'2*/';}
 else if(req.url==='/inspect-ready') {body='ready';}
 else {status=404;body='Not Found';}
 res.writeHead(status,{'content-type':type});res.end(body);
}).listen(Number(process.env.PORT),process.env.HOSTNAME);
"""
def digest(data):return "sha256:"+hashlib.sha256(data).hexdigest()
class ReadyInspectorControls(unittest.TestCase):
 def run_case(self,hook=None,invalid=False,expected=0):
  case=WORK/self.id().split(".")[-1];case.mkdir()
  app=case/"app";app.mkdir();(app/"server.js").write_text(SERVER)
  assets=[]
  for i in [1,2]:
   data=("/*PatamapsInspectorFixture"+str(i)+"*/").encode()
   assets.append(dict(relative="fixture-"+str(i)+".js",bytes=len(data),digest=digest(data)))
  cfg=dict(app=str(app),assets=assets,marker="PatamapsInspectorFixture",unavailable=[str(case/n) for n in ["source-unavailable","context-unavailable","provider-unavailable"]],logPrefix=str(case/"server"),processRecord=str(case/"server-process.json"),report=str(case/"http.json"))
  (case/"config.json").write_text(json.dumps(cfg))
  text="import fs from 'node:fs';\nimport {probe} from "+json.dumps(PROBE.as_uri())+";\nconst cfg="+json.dumps(cfg)+";\n"
  if invalid:text+="const inspector=42;\n"
  elif hook is not None:text+="const inspector="+hook+";\n"
  text+="try{await probe(cfg"+(",inspector" if hook is not None or invalid else "")+");}catch(error){console.error(error.message);process.exitCode=1;}\n"
  runner=case/"run.mjs";runner.write_text(text)
  child=subprocess.Popen([ARGS.node,str(runner)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,cwd=case)
  timed_out=False
  try:out,err=child.communicate(timeout=45)
  except subprocess.TimeoutExpired:
   timed_out=True
   os.killpg(child.pid,signal.SIGTERM)
   try:out,err=child.communicate(timeout=5)
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGKILL);out,err=child.communicate()
  (case/"driver.stdout").write_text(out);(case/"driver.stderr").write_text(err)
  (case/"exit.json").write_text(json.dumps(dict(exitCode=child.returncode,timedOut=timed_out)))
  self.assertFalse(timed_out,"bounded fixture driver timed out")
  self.assertEqual(child.returncode,expected,err)
  self.assertLess(len(out.encode()),16384);self.assertLess(len(err.encode()),65536)
  if invalid:
   self.assertFalse((app/"started.marker").exists())
   self.assertFalse((case/"http.json").exists())
   self.assertFalse((case/"server-process.json").exists())
   self.assertFalse((case/"server.stdout").exists())
   self.assertIn("OWNER_PROBE_INSPECTOR",err)
   return case,None,err
  report=json.loads((case/"http.json").read_text());process=json.loads((case/"server-process.json").read_text())
  self.assertTrue(report["serverStopped"]);self.assertTrue(process["closed"])
  check=subprocess.run(["/bin/ps","-p",str(process["pid"]),"-o","pid="],capture_output=True)
  self.assertNotEqual(check.returncode,0,"owned server survived")
  return case,report,err
 def test_default_seven_cases_are_unchanged(self):
  case,report,err=self.run_case()
  self.assertEqual(report["status"],"passed-current-owner-edited-runtime-http")
  self.assertEqual([x["status"] for x in report["cases"]],[200,200,403,404,200,200,404])
  self.assertNotIn("readyInspectionCompleted",report)
 def test_invalid_inspector_refuses_before_server_or_outputs(self):
  self.run_case(invalid=True,expected=1)
 def test_inspector_requests_the_live_owned_server(self):
  hook="""async ({root,assertLive})=>{
   assertLive();const response=await fetch(root+'/inspect-ready',{signal:AbortSignal.timeout(10000)});
   if(response.status!==200||await response.text()!=='ready')throw Error('INSPECTOR_READY_REQUEST_FAILED');
   assertLive();fs.writeFileSync(cfg.report+'.inspection.json',JSON.stringify({ready:true,root}));
  }"""
  case,report,err=self.run_case(hook=hook)
  self.assertTrue(report["readyInspectionCompleted"])
  self.assertEqual(len(report["cases"]),7)
  self.assertTrue(json.loads((case/"http.json.inspection.json").read_text())["ready"])
 def test_inspector_failure_stops_owned_server(self):
  case,report,err=self.run_case(hook="async ()=>{throw Error('OWNER_INSPECTOR_TEST_FAILURE');}",expected=1)
  self.assertEqual(report["status"],"failed")
  self.assertIn("OWNER_INSPECTOR_TEST_FAILURE",report["failureCodes"])
  self.assertNotIn("readyInspectionCompleted",report)
 def test_reappeared_producer_refuses_after_inspector(self):
  case,report,err=self.run_case(hook="async ()=>{fs.writeFileSync(cfg.unavailable[0],'controlled reappearance');}",expected=1)
  self.assertEqual(report["status"],"failed")
  self.assertIn("OWNER_PRODUCER_REAPPEARED",report["failureCodes"])
  self.assertNotIn("readyInspectionCompleted",report)
 def test_sigterm_during_inspector_stops_owned_server(self):
  hook="async ()=>{process.kill(process.pid,'SIGTERM');await new Promise(resolve=>setTimeout(resolve,30));}"
  case,report,err=self.run_case(hook=hook,expected=1)
  self.assertEqual(report["status"],"failed")
  self.assertIn("OWNER_PROBE_CANCELLED",report["failureCodes"])
  self.assertNotIn("readyInspectionCompleted",report)
if __name__=="__main__":
 WORK.mkdir(parents=True,exist_ok=False)
 unittest.main(argv=[sys.argv[0],*UNIT_ARGS])
