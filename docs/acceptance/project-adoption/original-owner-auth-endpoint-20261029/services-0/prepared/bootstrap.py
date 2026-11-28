from pathlib import Path
import sys,os,json,resource,runpy,datetime,uuid,signal
W=Path(sys.argv[1]);mode=sys.argv[2]
cfg=json.loads((W.parent/"service-config.private.json").read_text())
resource.setrlimit(resource.RLIMIT_CPU,(90,90));resource.setrlimit(resource.RLIMIT_FSIZE,(4194304,4194304))
sys.dont_write_bytecode=True
sys.path[:0]=[cfg["apiSource"],cfg["site"]]
def audit(event,args):
 if event=="open"and args and isinstance(args[0],(str,bytes,os.PathLike)):
  if any(p==".env"or p.startswith((".env.",".env-"))for p in Path(os.fsdecode(args[0])).parts):raise PermissionError("original dotenv refused")
# Verify the new service confinement before importing original application code.
import socket
controls={}
try:
 q=socket.socket();q.settimeout(1)
 try:q.connect(("127.0.0.1",9));controls["otherPortDenied"]=False
 except PermissionError:controls["otherPortDenied"]=True
 except OSError:controls["otherPortDenied"]=False
 finally:q.close()
except PermissionError:controls["otherPortDenied"]=True
try:
 (W.parent/"forbidden-service-write-control").write_text("preserved if confinement fails\n")
 controls["outsideWriteDenied"]=False
except PermissionError:controls["outsideWriteDenied"]=True
try:
 (W/".env.blocked-control").read_text();controls["dotenvReadDenied"]=False
except PermissionError:controls["dotenvReadDenied"]=True
(W/("controls-"+mode+".json")).write_text(json.dumps(controls))
assert all(controls.values()),"OWNED_SERVICE_SANDBOX_CONTROLS_FAILED"

sys.addaudithook(audit)
if mode=="migrate":
 runpy.run_path(str(Path(cfg["apiSource"])/"scripts/run_migrations.py"),run_name="__main__")
elif mode=="seed":
 from sqlalchemy import create_engine,inspect,text
 from src.models.user import User
 from src.models.auth import Role,UserRole
 from src.utils.auth import hash_password,create_access_token
 engine=create_engine(os.environ["DATABASE_URL"])
 with engine.begin()as conn:
  assert conn.execute(text("select current_database()")).scalar()==cfg["databaseName"]
  assert conn.execute(text("select count(*) from users")).scalar()==0,"Owned DB not empty"
  actual={c["name"]for c in inspect(conn).get_columns("users")}
  assert{c.name for c in User.__table__.columns}<=actual,"ORIGINAL_MIGRATIONS_MISSING_USER_COLUMNS"
  for which,permissions in[("allowed",["admin:users","admin:access"]),("denied",[])]:
   user=cfg["users"][which];role=uuid.uuid4()
   conn.execute(User.__table__.insert().values({"id":user["id"],"email":user["email"],"passwordHash":hash_password(user["password"]),"name":"Owned Patamaps "+which,"pointsBalance":0}))
   conn.execute(Role.__table__.insert().values(id=role,name="PATAMAPS_"+which.upper(),permissions=permissions))
   conn.execute(UserRole.__table__.insert().values(id=uuid.uuid4(),user_id=user["id"],role_id=role))
 token=create_access_token({"sub":cfg["users"]["allowed"]["id"]},expires_delta=datetime.timedelta(seconds=-60))
 p=W/"expired-token.private";p.write_text(token);p.chmod(0o600)
 (W/"seed-result.json").write_text(json.dumps(dict(status="seeded-isolated-original-models",users=2,roles=2,permission="admin:users",realPostgres=True,authenticationAccepted=False)))
 engine.dispose()
elif mode=="server":
 import uvicorn
 uvicorn.run("src.main:app",host="127.0.0.1",port=18765,workers=1,access_log=False,log_level="warning")
else:raise ValueError("Unknown isolated owner phase")
