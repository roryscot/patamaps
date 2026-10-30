from pathlib import Path
import sys,os,json,subprocess,hashlib,time,secrets,datetime
root=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
phase=Path(__file__).resolve().parent
cfg=json.loads((phase/"frozen.json").read_text())
owner=Path(cfg["owner"])
work=phase/"run"
work.mkdir()
(work/"home").mkdir()
(work/"tmp").mkdir()
(work/"uploads").mkdir()
(work/".env.blocked-control").write_text("read must be denied\n")
(work/"readiness-settings").write_text("")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
def check():
 for entry in cfg["sourceInputs"]:
  if sha(owner/entry["path"])!=entry["sha256"]:raise RuntimeError("bound source input changed")
 for entry in cfg["runnerInputs"]:
  if sha(phase/entry["path"])!=entry["sha256"]:raise RuntimeError("bound preflight input changed")
 p=subprocess.run(["/usr/bin/git","rev-parse","HEAD"],cwd=owner,capture_output=True,text=True,check=True)
 if p.stdout.strip()!=cfg["ownerCommit"]:raise RuntimeError("original owner HEAD changed")
check()
env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(work/"home"),"TMPDIR":str(work/"tmp")+"/","LANG":"en_US.UTF-8","ENV_FILE":str(work/"readiness-settings"),"APP_ENV":"test","ENVIRONMENT":"test","APP_NAME":"Patamaps isolated import preflight","API_BASE_URL":"http://127.0.0.1:8000","DATABASE_URL":"postgresql://patamaps_import_only@127.0.0.1:9/patamaps_import_only","INTERNAL_API_KEY":secrets.token_urlsafe(32),"JWT_SECRET":secrets.token_urlsafe(48),"MEDIA_BUCKET_NAME":"patamaps-import-only","MEDIA_CDN_BASE_URL":"http://127.0.0.1:9","UPLOAD_DIR":str(work/"uploads"),"KAFKA_ENABLED":"false","PYTHONDONTWRITEBYTECODE":"1"}
argv=["/usr/bin/sandbox-exec","-f",str(phase/"sandbox.sb"),cfg["python"],"-I","-S","-B",str(phase/"child.py"),str(work),cfg["site"],str(owner/"packages/api")]
with (work/"stdout").open("xb") as out,(work/"stderr").open("xb") as err:
 p=subprocess.Popen(argv,cwd=work,env=env,stdout=out,stderr=err)
 (work/"process.json").write_text(json.dumps({"pid":p.pid,"startedAtUtc":start}))
 try:code=p.wait(timeout=100)
 except subprocess.TimeoutExpired:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  code=124
check()
result={"schemaVersion":1,"phase":"owner-api-import-readiness","startedAtUtc":start,"finishedAtUtc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"childExitCode":code,"ownerCommit":cfg["ownerCommit"],"sourceInputCount":len(cfg["sourceInputs"]),"sourceBindingRechecked":True,"networkAllowed":False,"packagesInstalled":0,"servicesStarted":0,"databaseUsed":False,"originalOwnerBrowserAccepted":False}
if (work/"child-report.json").is_file():result["childReport"]=json.loads((work/"child-report.json").read_text())
else:result["childReport"]=None
for name in ["stdout","stderr"]:
 p=work/name
 result[name]={"bytes":p.stat().st_size,"sha256":sha(p)}
(phase/"receipt.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({"phase":result["phase"],"childExitCode":code,"sourceInputCount":result["sourceInputCount"],"reportPresent":result["childReport"] is not None}))
raise SystemExit(code)
