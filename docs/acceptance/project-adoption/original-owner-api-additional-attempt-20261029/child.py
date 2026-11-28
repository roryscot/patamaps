import sys,os,json,signal,resource,socket,importlib,time
from pathlib import Path
work=Path(sys.argv[1]).resolve()
site=Path(sys.argv[2]).resolve()
owner=Path(sys.argv[3]).resolve()
resource.setrlimit(resource.RLIMIT_CPU,(45,45))
resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024*1024,4*1024*1024))
sys.dont_write_bytecode=True
controls={}
try:
 s=socket.socket();s.settimeout(1)
 try:s.connect(("127.0.0.1",9));controls["networkDenied"]=False
 except PermissionError:controls["networkDenied"]=True
 except OSError:controls["networkDenied"]=False
 finally:s.close()
except PermissionError:controls["networkDenied"]=True
try:
 (work.parent/"forbidden-write-control").write_text("retained if sandbox fails\n")
 controls["outsideWriteDenied"]=False
except PermissionError:controls["outsideWriteDenied"]=True
try:
 (work/".env.blocked-control").read_text()
 controls["dotenvReadDenied"]=False
except PermissionError:controls["dotenvReadDenied"]=True
report={"sandboxControls":controls,"imports":[],"application":None,"networkAllowed":False,"serviceStarted":False,"databaseOpened":False}
def save():
 (work/"child-report.json").write_text(json.dumps(report,sort_keys=True)+"\n")
if not all(controls.values()):
 save();raise SystemExit(2)
def audit(event,args):
 if event.startswith(("socket.connect","socket.bind","socket.getaddrinfo","subprocess.","os.exec","os.spawn")) or event=="os.system":
  raise PermissionError("preflight external effect refused")
 if event=="open" and args and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0]))
  if any(x==".env" or x.startswith((".env.",".env-")) for x in p.parts):
   raise PermissionError("preflight dotenv read refused")
sys.addaudithook(audit)
sys.path[:0]=[str(owner),str(site)]
def alarm(signum,frame):raise TimeoutError("bounded import deadline")
signal.signal(signal.SIGALRM,alarm)
for module in ["bcrypt","pydantic_core","fastapi","uvicorn","sqlalchemy","psycopg2","asyncpg","pydantic_settings","jose","passlib.context","httpx","redis","greenlet","alembic","email_validator"]:
 signal.alarm(10)
 try:
  loaded=importlib.import_module(module)
  report["imports"].append({"module":module,"status":"passed","origin":getattr(loaded,"__file__",None)})
 except Exception as e:
  report["imports"].append({"module":module,"status":"failed","exceptionType":type(e).__name__,"missingModule":getattr(e,"name",None)})
 finally:signal.alarm(0)
save()
signal.alarm(30)
try:
 appmod=importlib.import_module("src.main")
 app=getattr(appmod,"app")
 paths=sorted({getattr(r,"path","") for r in app.routes})
 report["application"]={"status":"passed","routeCount":len(app.routes),"authLoginPresent":"/api/v1/auth/login" in paths,"authMePresent":"/api/v1/auth/me" in paths,"permissionsPresent":"/api/v1/rbac/permissions" in paths}
except Exception as e:
 report["application"]={"status":"failed","exceptionType":type(e).__name__,"missingModule":getattr(e,"name",None)}
 import traceback
 traceback.print_exc()
finally:signal.alarm(0)
save()
raise SystemExit(0 if all(x["status"]=="passed" for x in report["imports"]) and report["application"]["status"]=="passed" else 1)
