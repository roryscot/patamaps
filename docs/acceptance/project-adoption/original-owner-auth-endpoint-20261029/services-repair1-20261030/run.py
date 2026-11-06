from pathlib import Path
import json,os,sys,subprocess,hashlib,secrets,socket,time,signal,urllib.request,urllib.error,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps");B=Path(__file__).resolve().parent
sys.path.insert(0,str(R/"scripts"))
from bench_axum_retained import LEASE_PROBE,validate_ownership,NODE
probeAttempt=0
def live_ownership(phase):
 global probeAttempt
 probeAttempt+=1
 prefix=Path(__file__).resolve().parent/("ownership-probe-"+str(probeAttempt))
 try:
  p=subprocess.run([str(NODE),"--input-type=module","-e",LEASE_PROBE],capture_output=True,text=True,timeout=30)
 except subprocess.TimeoutExpired as e:
  prefix.with_suffix(".stdout.private").write_bytes(e.stdout or b"")
  prefix.with_suffix(".stderr.private").write_bytes(e.stderr or b"")
  raise ValueError("MEASUREMENT_OWNERSHIP_UNAVAILABLE")from None
 prefix.with_suffix(".stdout.private").write_text(p.stdout)
 prefix.with_suffix(".stderr.private").write_text(p.stderr)
 if p.returncode:raise ValueError("MEASUREMENT_OWNERSHIP_UNAVAILABLE")
 return validate_ownership(json.loads(p.stdout),phase)
DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return"sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
def write(p,v,private=False):
 p=Path(p)
 with p.open("x")as f:json.dump(v,f,indent=2);f.write("\n")
 if private:p.chmod(0o600)
def db():
 d=json.loads(subprocess.check_output([DOCKER,"inspect","advocates-local-advocates-db-1"],text=True,timeout=20))[0]
 return dict(id=d["Id"],running=d["State"]["Running"],startedAt=d["State"]["StartedAt"],restartCount=d["RestartCount"])
def docker(*args):
 return subprocess.check_output([DOCKER,*args],text=True,stderr=subprocess.PIPE,timeout=30)
report=dict(status="preparing-isolated-owner-auth",cases=[],servicesStarted=0,filesDeleted=0,packagesInstalled=0,policyChanged=False,authenticationAccepted=False,browserAccepted=False,startedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
def save():(B/"receipt.json").write_text(json.dumps(report,indent=2)+"\n")
def interrupted(sig,frame):raise SystemExit(128+sig)
signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
F=read(B/"frozen.json");api=None;beforeDB=db();save()
def check():
 for p,h in F["inputs"].items():assert sha(p)==h
 assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=F["owner"],text=True).strip()==F["ownerCommit"]
def child(mode,env,background=False):
 out=(B/"run"/(mode+".stdout")).open("xb");err=(B/"run"/(mode+".stderr")).open("xb")
 try:p=subprocess.Popen(["/usr/bin/sandbox-exec","-f",str(B/"sandbox.sb"),F["apiPython"],"-I","-S","-B",str(B/"bootstrap.py"),str(B/"run"),mode],cwd=Path(F["owner"])/"packages/api",env=env,stdout=out,stderr=err)
 finally:out.close();err.close()
 if background:return p
 try:code=p.wait(timeout=120)
 except subprocess.TimeoutExpired:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  raise RuntimeError("OWNED_"+mode.upper()+"_TIMEOUT")
 report[mode+"ExitCode"]=code;save()
 assert code==0,"ORIGINAL_OWNER_"+mode.upper()+"_FAILED"
 assert all(read(B/"run"/("controls-"+mode+".json")).values())
def request(label,path,expected,body=None,token=None,method=None):
 headers={"Content-Type":"application/json"}
 if token:headers["Authorization"]="Bearer "+token
 q=urllib.request.Request("http://127.0.0.1:18765"+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
 try:
  with urllib.request.urlopen(q,timeout=10)as r:code=r.status;data=r.read(1048577)
 except urllib.error.HTTPError as e:code=e.code;data=e.read(1048577)
 assert len(data)<=1048576
 result=json.loads(data)
 report["cases"].append(dict(name=label,status=code,expected=expected,passed=code==expected));save()
 assert code==expected,"ORIGINAL_OWNER_HTTP_EXPECTATION:"+label
 return result

def browser_workflow(build):
 check()
 import shutil
 from next_retained_runtime import ProducerMoves
 cfgold=read(R/".tools/original-owner-five-project-browser-20261027/browser-config.json")
 state=Path(build["state"]);selection=read(state/"selected.json");attempt=state/selection["attempt"];candidate=attempt/"candidate"
 rows=read(attempt/"artifacts.json")
 bundle=B/"runtime";bundle.mkdir();mapping={}
 for prefix,dest in[("packages/web/.next/standalone","."),("packages/web/.next/static","packages/web/.next/static"),("packages/web/public","packages/web/public")]:
  for n,row in rows.items():
   if n!=prefix and not n.startswith(prefix+"/"):continue
   tail=n[len(prefix):].lstrip("/");relative=dest if not tail else tail if dest=="."else dest+"/"+tail
   assert relative not in mapping;mapping[relative]=(n,row)
 assert len(mapping)<=8192 and sum(row.get("bytes",0)for _,row in mapping.values())<=134217728
 for relative,(source,row)in sorted(mapping.items(),key=lambda x:(len(Path(x[0]).parts),x[0])):
  target=bundle if relative=="."else bundle/relative
  if row["kind"]=="directory":target.mkdir(exist_ok=True)
  else:
   assert row["kind"]=="file";assert sha(candidate/source)==row["digest"]
   shutil.copyfile(candidate/source,target);target.chmod(row["mode"])
 marker="PatamapsRetainedOwnerLabel20261026";assets=[]
 prefix="packages/web/.next/static/"
 for n,row in rows.items():
  if n.startswith(prefix)and n.endswith(".js")and row["kind"]=="file"and marker in(candidate/n).read_text():assets.append(dict(relative=n[len(prefix):],digest=row["digest"],bytes=row["bytes"]))
 assert len(assets)==2
 binding=read(Path(F["build"])/"binding.json");plan=read(Path(F["build"])/"plan.json")
 paths=[Path(F["build"])/"owner",Path(binding["snapshot"]),Path(plan["workspace"]["sources"][0]["invocation"]["executable"])]
 moves=ProducerMoves(B/"producer-moves");(B/"producer-moves").mkdir()
 process=B/"next-process.json"
 config=dict(cfgold)
 config["http"]=dict(app=str(bundle/"packages/web"),assets=assets,marker=marker,unavailable=list(map(str,paths)),logPrefix=str(B/"next"),processRecord=str(process),report=str(B/"next-http.json"))
 config.update(inspection=str(B/"browser"),authSpec=str(B/"auth.spec.cjs"),authConfig=str(B/"auth.config.cjs"),ownedAuthConfig=str(B/"service-config.private.json"))
 write(B/"browser-config.json",config)
 before={str(p):[p.lstat().st_dev,p.lstat().st_ino,p.lstat().st_mode]for p in paths}
 pointer=sha(state/"selected.json");env={"PATH":"/Users/admin/.nvm/versions/node/v22.23.3/bin:/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(B/"run/home"),"TMPDIR":str(B/"run/tmp")+"/","LANG":"en_US.UTF-8","CI":"1","NODE_ENV":"production","NEXT_TELEMETRY_DISABLED":"1","NODE_OPTIONS":"--max-old-space-size=2048"}
 node="/Users/admin/.nvm/versions/node/v22.23.3/bin/node";child=None
 try:
  for p in paths:moves.take(p,p.with_name(p.name+".owned-auth-unavailable-20261029"))
  with(B/"browser-wrapper.stdout").open("xb")as out,(B/"browser-wrapper.stderr").open("xb")as err:
   child=subprocess.Popen([node,str(B/"browser.mjs"),str(B/"browser-config.json")],env=env,cwd=B,stdout=out,stderr=err)
   try:code=child.wait(timeout=180)
   except subprocess.TimeoutExpired:
    child.terminate()
    try:child.wait(timeout=10)
    except subprocess.TimeoutExpired:child.kill();child.wait()
    raise RuntimeError("OWNED_AUTH_BROWSER_TIMEOUT")
  report["browserWrapperExitCode"]=code;save()
  assert code==0,"ORIGINAL_OWNER_AUTH_BROWSER_FAILED"
  observed=read(B/"browser/inspection.json");http=read(B/"next-http.json")
  assert observed["status"]=="passed-original-owner-five-project-auth"and observed["authCases"]==5 and observed["realAuthenticationAccepted"]
  assert observed["projectCounts"]=={n:1 for n in["chromium","firefox","webkit","Mobile Chrome","Mobile Safari"]}
  assert observed["frontendForwarderClosed"]and observed["ownedGuardianClosed"]and observed["proxyClosed"]
  assert http["serverStopped"]and read(process)["closed"]
  stop=read(B/"browser/guard-result.json");assert stop["status"]=="stopped-owned-browser-groups"and not stop["ownershipUncertain"]
  report.update(browserAccepted=True,browserAuthCases=5,browserProjectCounts=observed["projectCounts"],nextServerStopped=True,browserGroupsStopped=len(stop["groups"]))
 finally:
  if child is not None and child.poll()is None:
   child.terminate()
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:child.kill();child.wait()
  moves.restore()
  assert {str(p):[p.lstat().st_dev,p.lstat().st_ino,p.lstat().st_mode]for p in paths}==before
  assert sha(state/"selected.json")==pointer
  for n,row in rows.items():
   if row["kind"]=="file":assert sha(candidate/n)==row["digest"]
  report["nextProducerPathsAndArtifactBytesRestored"]=True;save()

try:
 end=time.monotonic()+20
 while True:
  try:ownership=live_ownership("functional");break
  except AssertionError as e:
   if e.args!=("MEASUREMENT_HEARTBEAT_OR_CANCELLATION",)or time.monotonic()>=end:raise
   time.sleep(1)
 check();assert beforeDB["running"]and beforeDB["id"]==F["protectedDbId"]
 build=read(Path(F["build"])/"receipt.json")
 assert build["status"]=="passed-declared-owner-endpoint-build"
 # Check required ports without taking over another listener.
 for port in[18765,18766,13000]:
  s=socket.socket();s.bind(("127.0.0.1",port));s.close()
 token=secrets.token_hex(16);databaseName="patamaps_auth_"+token[:12];password=secrets.token_urlsafe(32)
 (B/"database").mkdir(mode=0o700);
 (B/"container-passwd").write_text("root:x:0:0:root:/root:/bin/sh\npostgres:x:501:20:Owned PostgreSQL:/tmp:/bin/sh\n")
 (B/"container-group").write_text("root:x:0:\nowned:x:20:\n")
 assert os.getuid()==501 and os.getgid()==20
 (B/"run").mkdir();(B/"run/home").mkdir();(B/"run/tmp").mkdir();(B/"run/uploads").mkdir()
 settings=B/"run/readiness-settings";settings.write_text("")
 (B/"run/.env.blocked-control").write_text("dummy service denial control\n")
 envfile=B/"database-env.private"
 envfile.write_text("POSTGRES_USER=patamaps_owned\nPOSTGRES_PASSWORD="+password+"\nPOSTGRES_DB="+databaseName+"\n");envfile.chmod(0o600)
 users={k:dict(id="patamaps-"+k+"-"+token,email=k+"-"+token[:12]+"@example.com",password=secrets.token_urlsafe(24))for k in["allowed","denied"]}
 cfg=dict(apiSource=str(Path(F["owner"])/"packages/api"),site=F["site"],databaseName=databaseName,users=users)
 write(B/"service-config.private.json",cfg,True)
 cid=docker("create","--name","patamaps-auth-"+token,"--label","patamaps.auth.owner="+token,"--label","buildctl.project="+str(R),"--label","buildctl.request="+ownership["id"],"--read-only","--user","501:20","--cap-drop","ALL","--security-opt","no-new-privileges:true","--cpus","1","--memory","536870912","--memory-swap","536870912","--pids-limit","128","--log-driver","none","--network","bridge","--publish","127.0.0.1:18766:5432","--mount","type=bind,source="+str(B/"database")+",target=/var/lib/postgresql/data","--mount","type=bind,source="+str(B/"container-passwd")+",target=/etc/passwd,readonly","--mount","type=bind,source="+str(B/"container-group")+",target=/etc/group,readonly","--tmpfs","/tmp:rw,nosuid,nodev,size=67108864","--tmpfs","/var/run/postgresql:rw,nosuid,nodev,size=16777216,uid=501,gid=20","--env-file",str(envfile),F["postgresImage"]).strip()
 write(B/"container.json",dict(containerId=cid,ownerToken=token,project=str(R)))
 d=json.loads(docker("inspect",cid))[0];h=d["HostConfig"]
 assert not d["State"]["Running"]and d["Image"]==F["postgresImage"]
 assert h["NanoCpus"]==1000000000 and h["Memory"]==h["MemorySwap"]==536870912 and h["PidsLimit"]==128 and h["ReadonlyRootfs"]and not h["AutoRemove"]
 assert h["PortBindings"]=={"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"18766"}]}
 assert h["LogConfig"]["Type"]=="none"and h["NetworkMode"]=="bridge"and not h["Privileged"]
 assert any(x in["no-new-privileges","no-new-privileges:true"]for x in h["SecurityOpt"])
 assert d["Config"]["Labels"]["patamaps.auth.owner"]==token and d["Config"]["Labels"]["buildctl.request"]==ownership["id"]
 binds=[m for m in d["Mounts"]if m["Type"]=="bind"]
 assert len(binds)==3
 assert {(m["Source"],m["Destination"],m["RW"])for m in binds}=={(str(B/"database"),"/var/lib/postgresql/data",True),(str(B/"container-passwd"),"/etc/passwd",False),(str(B/"container-group"),"/etc/group",False)}
 assert d["Config"]["User"]=="501:20"and h["CapDrop"]==["ALL"]and not h.get("CapAdd")
 assert set(h["Tmpfs"])=={"/tmp","/var/run/postgresql"}
 write(B/"container-limits.json",dict(containerId=cid,cpu=1,memoryBytes=536870912,swapBytes=0,pids=128,readonlyRoot=True,logDriver="none",publishedLoopbackPort=18766,ownedData=str(B/"database"),nativeExclusive=True,maximumObservedOwnedDataBytes=536870912))
 docker("start",cid);report["servicesStarted"]=1;report["containerId"]=cid;save()
 end=time.monotonic()+30
 while True:
  p=subprocess.run([DOCKER,"exec",cid,"pg_isready","-U","patamaps_owned","-d",databaseName],capture_output=True,timeout=5)
  if p.returncode==0:break
  assert time.monotonic()<end,"OWNED_POSTGRES_NOT_READY";time.sleep(.3)
 env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(B/"run/home"),"TMPDIR":str(B/"run/tmp")+"/","LANG":"en_US.UTF-8","ENV_FILE":str(settings),"APP_ENV":"test","ENVIRONMENT":"test","APP_NAME":"Owned Patamaps authentication","API_BASE_URL":"http://127.0.0.1:18765","DATABASE_URL":"postgresql://patamaps_owned:"+password+"@127.0.0.1:18766/"+databaseName,"INTERNAL_API_KEY":secrets.token_urlsafe(32),"JWT_SECRET":secrets.token_urlsafe(48),"MEDIA_BUCKET_NAME":"patamaps-owned-auth","MEDIA_CDN_BASE_URL":"http://127.0.0.1:9","UPLOAD_DIR":str(B/"run/uploads"),"KAFKA_ENABLED":"false","PYTHONPATH":str(Path(F["owner"])/"packages/api")+":"+F["site"],"PYTHONDONTWRITEBYTECODE":"1","CORS_ORIGINS":"http://127.0.0.1:13000,http://localhost:13000"}
 child("migrate",env);child("seed",env)
 api=child("server",env,True);report["servicesStarted"]=2;save()
 end=time.monotonic()+30
 while True:
  assert api.poll()is None,"ORIGINAL_API_EXITED_BEFORE_READY"
  try:
   with urllib.request.urlopen("http://127.0.0.1:18765/openapi.json",timeout=1)as r:
    assert r.status==200;break
  except(urllib.error.URLError,TimeoutError):
   assert time.monotonic()<end,"ORIGINAL_API_READINESS_TIMEOUT";time.sleep(.2)
 request("missing-session","/api/v1/auth/me",401)
 request("invalid-session","/api/v1/auth/me",401,token="invalid-owned-negative")
 request("wrong-password","/api/v1/auth/login",401,body=dict(email=users["allowed"]["email"],password="wrong-owned-password"))
 sessions={}
 for which in["allowed","denied"]:
  user=users[which]
  response=request(which+"-real-login","/api/v1/auth/login",200,body=dict(email=user["email"],password=user["password"]))
  session=response["access_token"];sessions[which]=session
  current=request(which+"-current-user","/api/v1/auth/me",200,token=session)
  assert current["id"]==user["id"]and current["email"]==user["email"],"ORIGINAL_SESSION_IDENTITY_MISMATCH"
  perms=request(which+"-permissions","/api/v1/rbac/permissions",200,token=session)
  assert("admin:users"in perms["permissions"])==(which=="allowed"),"ORIGINAL_RBAC_IDENTITY_MISMATCH"
  result=request(which+"-permission-check","/api/v1/rbac/check-permission?permission=admin%3Ausers",200,token=session,method="POST")
  assert result["has_permission"]==(which=="allowed")
 request("expired-session","/api/v1/auth/me",401,token=(B/"run/expired-token.private").read_text())
 browser_workflow(build)
 check();assert db()==beforeDB
 report.update(status="passed-isolated-original-owner-http-and-browser-auth",authenticationAccepted=True,users=2,realPasswordLogins=2,permission="admin:users",expectedPermissionOutcomesVerified=True)
except BaseException as e:
 report.update(status="failed-isolated-original-owner-auth",failureType=type(e).__name__,failure=str(e));raise
finally:
 if api is not None:
  api.terminate()
  try:api.wait(timeout=10)
  except subprocess.TimeoutExpired:api.kill();api.wait()
 report.update(apiStopped=api is None or api.poll()is not None,protectedDatabaseStartIdentityUnchanged=db()==beforeDB,finishedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 save()
print(json.dumps({k:report[k]for k in["status","authenticationAccepted","users","realPasswordLogins","expectedPermissionOutcomesVerified","apiStopped"]if k in report}))
