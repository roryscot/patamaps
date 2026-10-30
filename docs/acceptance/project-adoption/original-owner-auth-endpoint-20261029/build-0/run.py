from pathlib import Path
import json,os,sys,hashlib,subprocess,signal,datetime,time
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=Path(__file__).resolve().parent;ROOT=B.parent
sys.path.insert(0,str(R/"scripts"))
from bench_phases import measured
from project_watch import stop
from bench_axum_retained import live_ownership,measurement_state,configured_state_roots
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return"sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+"\n")
def term(s,f):raise SystemExit(128+s)
signal.signal(signal.SIGTERM,term);signal.signal(signal.SIGINT,term)
F=read(B/"frozen.json");CLI=Path(F["cli"]);OLD=R/".tools/installed-original-owner-next-20261027/owner-native"
fixture=read(R/".tools/installed-original-owner-next-20261027/owner-fixture.json")
report=dict(status="preparing-declared-owner-endpoint",commands=[],filesDeleted=0,policyChanged=False,servicesStarted=0,actualAuthenticationAccepted=False,startedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
def save():write(B/"receipt.json",report)
def check_inputs():
 assert sha(__file__)==F["driverDigest"]
 for p,h in F["inputs"].items():assert sha(p)==h
 assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=F["owner"],text=True).strip()==F["ownerCommit"]
 assert subprocess.check_output(["git","status","--porcelain=v1"],cwd=F["owner"],text=True)==""
def run(label,args,deadline=900):
 report["currentCommand"]=label;save()
 sample,raw=measured([sys.executable,"-B",str(R/"scripts/project_watch.py"),"__guard",*map(str,args)],B,dict(os.environ),retained=B/label,deadline=deadline,cleanup=stop)
 report["commands"].append(dict(role=label,measurement=sample));save()
 assert sample["exitCode"]==0,"OWNER_ENDPOINT_COMMAND_FAILED:"+label
 return json.loads(raw)
def artifacts(state):
 selected=read(state/"selected.json");attempt=state/selected["attempt"];rows=read(attempt/"artifacts.json")
 for n,row in rows.items():
  if row["kind"]=="file":assert sha(attempt/"candidate"/n)==row["digest"]
 return dict(pointer=sha(state/"selected.json"),manifest=sha(attempt/"artifacts.json"),files=sum(x["kind"]=="file"for x in rows.values()),attempts=sorted(p.name for p in(state/"attempts").iterdir()))
save()
try:
 end=time.monotonic()+20
 while True:
  try:report["reservation"]=live_ownership("functional");break
  except AssertionError as e:
   if e.args!=("MEASUREMENT_HEARTBEAT_OR_CANCELLATION",)or time.monotonic()>=end:raise
   time.sleep(1)
 check_inputs()
 oldstate=Path(read(OLD/"receipt.json")["state"]);priorstate=Path(fixture["priorState"])
 protected={str(s):artifacts(s)for s in[oldstate,priorstate]}
 owner=B/"owner";owner.mkdir()
 for n,h in fixture["sourceInputs"].items():
  assert not any(x==".env"or x.startswith(".env.")for x in Path(n).parts)
  p=Path(fixture["source"])/n;assert sha(p)==h
  target=owner/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes());target.chmod(0o600)
  assert sha(target)==h
 (B/"tmp").mkdir()
 plan=read(OLD/"plan.json");binding=read(OLD/"binding.json");prep=read(OLD/"preparation.json")
 originalConfig=dict(plan["project"]["nonsecretConfiguration"])
 plan["project"]["nonsecretConfiguration"].update(api="http://127.0.0.1:18765",tmp=str(B/"tmp"))
 assert {k for k in originalConfig if originalConfig[k]!=plan["project"]["nonsecretConfiguration"][k]}=={"api","tmp"}
 for name,value in[("plan.json",plan),("binding.json",binding),("preparation.json",prep)]:write(B/name,value)
 state=measurement_state(B,Path(configured_state_roots()[0]).resolve()/"original-owner-auth-endpoint-20261029",configured_state_roots())
 report.update(sourceRevision=F["sourceRevision"],ownerCommit=F["ownerCommit"],sourceInputs=len(fixture["sourceInputs"]),state=str(state),previousStates=protected,declaredApiOrigin=plan["project"]["nonsecretConfiguration"]["api"],changedConfigurationKeys=["api","tmp"],planDigest=sha(B/"plan.json"),bindingDigest=sha(B/"binding.json"),preparationDigest=sha(B/"preparation.json"),compilerDigest=sha(CLI),driverDigest=sha(__file__))
 save()
 result=run("endpoint-project-build",[CLI,"project-build",B/"plan.json","--source",owner,"--state",state,"--context",B/"binding.json","--preparation",B/"preparation.json"],2400)
 assert result["status"]=="selected-project-build"and result["verification"]=="commands-executed"
 attempt=state/result["attempt"];candidate=attempt/"candidate"
 assert all(sha(candidate/n)==h for n,h in fixture["expectedGenerated"].items())
 tests=read(candidate/"packages/web/.next/patamaps-route-tests.json")
 assert tests["success"]and tests["numPassedTests"]==tests["numTotalTests"]==3 and tests["numFailedTests"]==0
 chunks=sorted((candidate/"packages/web/.next/static/chunks").rglob("*.js"))
 witnesses=[]
 for p in chunks:
  s=p.read_text()
  if"this.baseUrl="in s and'const t="http://127.0.0.1:18765"'in s:witnesses.append(dict(path=p.relative_to(candidate).as_posix(),digest=sha(p)))
 assert witnesses,"DECLARED_AUTH_CLIENT_ENDPOINT_NOT_COMPILED"
 for s,expected in protected.items():assert artifacts(Path(s))==expected
 check_inputs()
 verified=run("endpoint-final-bindings",[CLI,"project-build-verify",state],900)
 assert verified["status"]=="verified-selected-build-bindings"
 report.update(status="passed-declared-owner-endpoint-build",selection=result,endpointWitnesses=witnesses,generatedOutputs=8,routeTestsPassed=3,previousSelectionsAndArtifactsUnchanged=True,newState=artifacts(state))
except BaseException as e:
 report.update(status="failed-declared-owner-endpoint-build",failureType=type(e).__name__,failure=str(e));raise
finally:
 report["finishedAtUtc"]=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
print(json.dumps({k:report[k]for k in["status","declaredApiOrigin","generatedOutputs","routeTestsPassed","previousSelectionsAndArtifactsUnchanged"]if k in report}))
