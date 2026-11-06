"""Read-only original-owner auth preparation; no imports/services/browser or environment reads."""
from pathlib import Path
import json,hashlib,re,subprocess,ast,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps");O=Path("/Volumes/dev_src_case_sensitive/projects/seeder")
B=Path(__file__).resolve().parent
def sha(p):
 with p.open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
def read(p):return json.loads(p.read_text())
assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=O,text=True).strip()=="c61d51a57120abbbca65d4cb4a432c1cef9343bb"
prior=read(R/"docs/acceptance/project-adoption/original-owner-api-resumption-20261029/review.json")
assert prior["apiReadinessAccepted"] and prior["leaseReleased"]and not prior["authenticationAccepted"]
cfg=read(R/".tools/original-owner-five-project-browser-20261027/browser-config.json")
app=Path(cfg["http"]["app"]);chunks=sorted((app/".next/static/chunks").rglob("*.js"))
assert len(chunks)<=1000 and sum(p.stat().st_size for p in chunks)<=67108864
manifest=[];witness=[]
for p in chunks:
 raw=p.read_bytes();row=dict(path=p.relative_to(app).as_posix(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 manifest.append(row)
 urls=sorted(set(re.findall(rb"https?://(?:localhost|127[.]0[.]0[.]1)(?::[0-9]+)?",raw)))
 if urls:witness.append(dict(**row,publicLoopbackLiterals=[u.decode()for u in urls]))
for a in cfg["http"]["assets"]:
 p=app/".next/static"/a["relative"];assert p.stat().st_size==a["bytes"]and"sha256:"+sha(p)==a["digest"]
inputs=["packages/api/src/routes/auth.py","packages/api/src/routes/rbac.py","packages/api/src/utils/auth.py","packages/api/src/utils/rbac.py","packages/api/src/models/database.py","packages/api/src/models/user.py","packages/api/src/models/auth.py","packages/api/src/main.py","packages/api/src/database/__init__.py","packages/api/src/async_db/engine.py","packages/web/src/lib/config.ts","packages/web/src/lib/api/client-app.ts","packages/web/playwright.config.ts"]
bound=[dict(path=n,sha256=sha(O/n))for n in inputs]
trees={n:ast.parse((O/n).read_text())for n in inputs if n.endswith(".py")}
routes=trees["packages/api/src/routes/auth.py"]
login=next(n for n in routes.body if isinstance(n,ast.AsyncFunctionDef)and n.name=="_do_login")
calls={ast.unparse(n.func)for n in ast.walk(login)if isinstance(n,ast.Call)}
assert "db.query"in calls and"db.commit"in calls and"verify_password"in calls
rbac=trees["packages/api/src/routes/rbac.py"]
permissions=next(n for n in rbac.body if isinstance(n,ast.AsyncFunctionDef)and n.name=="get_permissions")
assert any(isinstance(n,ast.Call)and ast.unparse(n.func)=="db.query"for n in ast.walk(permissions))
raw=(app/".next/static/chunks/0cca3dd7b286f28a.js").read_text()
assert 'api:{baseURL:"http://127.0.0.1:1"'in raw
nativeCandidates=[Path("/usr/local/opt/postgresql@16/bin/postgres"),Path("/usr/local/opt/postgresql@15/bin/postgres"),Path("/usr/local/bin/postgres"),Path("/Applications/Postgres.app/Contents/Versions/latest/bin/postgres")]
docker="/Applications/Docker.app/Contents/Resources/bin/docker"
db=json.loads(subprocess.check_output([docker,"inspect","advocates-local-advocates-db-1"],text=True,timeout=30))[0]
assert db["Id"]=="a0aad891673301454689ad960980e85efa82078e93fbd326b77c149708676d0b"and db["State"]["Running"]
image=json.loads(subprocess.check_output([docker,"image","inspect",db["Image"]],text=True,timeout=30))[0]
assert any(x.startswith("postgres@sha256:")for x in image.get("RepoDigests",[]))
boundAfter=[dict(path=n,sha256=sha(O/n))for n in inputs];assert boundAfter==bound
assert all(sha(app/x["path"])==x["sha256"]for x in manifest)
result=dict(status="verified-readonly-auth-preparation",recordedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 ownerCommit="c61d51a57120abbbca65d4cb4a432c1cef9343bb",sourceRevision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=R,text=True).strip(),
 ownerInputsBound=bound,selectedJavaScriptFiles=len(manifest),selectedJavaScriptBytes=sum(x["bytes"]for x in manifest),
 chunkManifestSha256=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),publicLoopbackLiteralWitnesses=witness,
 compiledConfigBaseUrlLiteral="http://127.0.0.1:1",compiledAuthCallGraphTraced=False,activeAuthenticationOriginAccepted=False,
 loginQueriesAndCommitsUser=True,permissionEndpointQueriesAssignedRoles=True,
 checkedNativePostgresLocations=[dict(path=str(p),present=p.is_file())for p in nativeCandidates],
 nativePostgresSearchExhaustive=False,cachedPublicPostgresImageId=image["Id"],cachedPublicPostgresRepoDigests=image["RepoDigests"],
 cachedImageArchitecture=image["Architecture"],cachedImageOs=image["Os"],unrelatedDatabaseBorrowed=False,
 apiImportsExecuted=0,servicesStarted=0,packagesInstalled=0,filesDeleted=0,policyChanged=False,
 realAuthenticationAccepted=False,fullGoalComplete=False,auditorSha256=sha(Path(__file__)))
with(B/"selected-chunks.private.json").open("x")as f:json.dump(manifest,f,indent=2)
P=R/"docs/acceptance/project-adoption/original-owner-auth-preparation-20261029";P.mkdir()
with(P/"review.json").open("x")as f:json.dump(result,f,indent=2);f.write("\n")
with(P/"audit.py").open("xb")as f:f.write(Path(__file__).read_bytes())
print(json.dumps({k:result[k]for k in["status","selectedJavaScriptFiles","selectedJavaScriptBytes","compiledConfigBaseUrlLiteral","activeAuthenticationOriginAccepted","loginQueriesAndCommitsUser","permissionEndpointQueriesAssignedRoles","servicesStarted","apiImportsExecuted","fullGoalComplete"]}))
