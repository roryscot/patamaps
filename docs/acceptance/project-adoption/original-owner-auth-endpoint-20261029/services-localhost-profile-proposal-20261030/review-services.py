from pathlib import Path
import hashlib,json,re,subprocess,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps");B=Path(__file__).resolve().parent/"services-localhost-profile-proposal-20261030"
D=B.parent/"services-localhost-profile-proposal-20261030"
C=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds")
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return"sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
F=read(B/"frozen.json");m=read(D/"supervisor.json");ex=read(D/"supervisor-exit.json")
assert sha(B/"frozen.json")=="sha256:42cf17ef56ad3f5e9f0c72e385f38d159c1a55b25f5b0e0b2e15fa4de2f317c1"
approval=read(D/"APPROVAL.json")
assert approval["humanAnswer"]=="Approve one corrected-profile attempt"
assert approval["maximumAdditionalApplicationAttempts"]==1 and approval["automaticPhaseRepairsAuthorized"]==0
assert approval["frozenManifestSha256"]==sha(B/"frozen.json")[7:]

requests=[read(p)for p in(C/"scheduler/requests").glob("*.json")]
matched=[r for r in requests if r["owner"]["pid"]==m["pid"]and r["project"]==str(R)and datetime.datetime.fromisoformat(r["createdAt"].replace("Z","+00:00"))>=datetime.datetime.fromisoformat(m["startedAtUtc"])]
assert len(matched)==1;r=matched[0]
assert r["state"]=="finished"and r.get("leaseReleaseCompleted")is True
stream=(D/"supervisor.stdout").read_text()+(D/"supervisor.stderr").read_text()
ids=re.findall(r"Storage guard record: "+re.escape(str(C))+r"/runs/([0-9a-f-]{36})/run[.]json",stream);assert len(ids)==1
gp=C/"runs"/ids[0]/"run.json";g=read(gp)
assert r["startedAt"]<=g["startedAt"]<=g["finishedAt"]<=r["finishedAt"]
assert g["root"]==str(R)and g["label"]==r["label"]=="patamaps"and g["filesDeleted"]==0
for p,h in F["inputs"].items():assert sha(p)==h
assert sha(B/"run.py")==F["driverDigest"]
old=read(D/"protected-service-before.json")
db=json.loads(subprocess.check_output(["/Applications/Docker.app/Contents/Resources/bin/docker","inspect","advocates-local-advocates-db-1"],text=True,timeout=20))[0]
assert dict(id=db["Id"],running=db["State"]["Running"],startedAt=db["State"]["StartedAt"],restartCount=db["RestartCount"])==old
a=read(B/"receipt.json")if(B/"receipt.json").exists()else None
v=dict(sourceRevision=F["sourceRevision"],ownerCommit=F["ownerCommit"],reservationId=r["id"],reservationFinished=True,leaseReleased=True,guardId=ids[0],guardRecordDigest=sha(gp),supervisorExitCode=ex["exitCode"],guardExitCode=g["exitCode"],guardCompleted=g["completed"],sourceInputsRehashed=F["actualOriginalApiSourceInputs"],interpreterExecutablesRehashed=F["actualInterpreterExecutables"],allFrozenInputsMatched=True,protectedDatabaseStartIdentityUnchanged=True,filesDeleted=0,policyChanged=False,fullGoalComplete=False,endpointAlreadyAccepted=True,realHttpAuthenticationAccepted=False,browserAccepted=False)
if a is None:
 assert ex["exitCode"]==g["exitCode"]==75
 assert not(B/"container.json").exists()and not(B/"run").exists()
 assert g["stopReason"].startswith("Insufficient retained-output headroom")
 v.update(status="verified-isolated-auth-admission-refusal",driverExecuted=False,servicesStarted=0,postgresCreated=False,apiRequestsExecuted=0,browserProjectsExecuted=0,stopReason="insufficient-retained-output-headroom",retainedAllocatedBytesAtStart=g.get("retainedAllocatedBytesAtStart"),guardStopReason=g["stopReason"])
else:
 assert a["apiStopped"]and a["protectedDatabaseStartIdentityUnchanged"]
 stopped=read(B/"owned-container-stop.json");assert stopped["stopped"]and not stopped["containerDeleted"]and not stopped["dataDeleted"]
 v.update(status="verified-isolated-auth-result",driverExecuted=True,driverStatus=a["status"],servicesStarted=a["servicesStarted"],migrateExitCode=a.get("migrateExitCode"),seedExitCode=a.get("seedExitCode"),httpCases=a["cases"],apiRequestsExecuted=len(a["cases"]),apiStopped=True,ownedContainerStopped=True,ownedDataPreserved=True,rawReceiptDigest=sha(B/"receipt.json"),realHttpAuthenticationAccepted=a.get("authenticationAccepted",False),browserAccepted=a.get("browserAccepted",False),browserProjectsExecuted=0,browserProjectCounts=a.get("browserProjectCounts"),browserGroupsStopped=a.get("browserGroupsStopped"),nextProducerPathsAndArtifactBytesRestored=a.get("nextProducerPathsAndArtifactBytesRestored",False))
 if a["status"]=="passed-isolated-original-owner-http-and-browser-auth":
  assert ex["exitCode"]==g["exitCode"]==0 and g["completed"]
  assert a["authenticationAccepted"]and a["browserAccepted"]and a["realPasswordLogins"]==2
  assert len(a["cases"])==12 and all(x["passed"]for x in a["cases"])
  assert a["browserProjectCounts"]=={n:1 for n in["chromium","firefox","webkit","Mobile Chrome","Mobile Safari"]}
  v.update(status="verified-real-owner-auth-and-permissions",browserProjectsExecuted=5,users=2,expectedPermissionOutcomesVerified=True)
 else:
  assert ex["exitCode"]!=0
  v.update(status="verified-isolated-owner-auth-failure",failureType=a.get("failureType"),failureCode=a.get("failure"),failurePreserved=True)
 controls={}
 for mode in["migrate","seed","server"]:
  p=B/"run"/("controls-"+mode+".json")
  if p.exists():controls[mode]=read(p)
 v["sandboxControls"]=controls
 if(B/"container-limits.json").exists():v["inspectedOwnedContainerLimits"]=read(B/"container-limits.json")
assert all(sha(x["path"])==x["digest"]for x in read(D/"prior-admission-preimages.json"))
v.update(priorAdmissionPreserved=True,approvedSeparateCleanupFilesDeleted=216)
v["applicationAttemptAuthorized"]=1
v["automaticPhaseRetriesExecuted"]=0
v["actualLaunchRevision"]=approval["actualLaunchRevision"]
v["frozenManifestSha256"]=sha(B/"frozen.json")[7:]
v["all422FrozenInputBindingsMatched"]=len(F["inputs"])==422
v["priorFailureFilesRehashed"]=len(read(D/"prior-admission-preimages.json"))
v["ownedContainerInspectedStopped"]=False
if (B/"container.json").exists():
 owned=read(B/"container.json")
 info=json.loads(subprocess.check_output(["/Applications/Docker.app/Contents/Resources/bin/docker","inspect",owned["containerId"]],text=True,timeout=20))[0]
 assert info["Id"]==owned["containerId"] and info["Config"]["Labels"]["patamaps.auth.owner"]==owned["ownerToken"]
 assert not info["State"]["Running"] and not info["State"]["Restarting"] and info["State"]["Pid"]==0
 h=info["HostConfig"]
 assert info["Image"]==F["postgresImage"] and info["Config"]["User"]=="501:20"
 assert h["NanoCpus"]==1000000000 and h["Memory"]==h["MemorySwap"]==536870912 and h["PidsLimit"]==128
 assert h["ReadonlyRootfs"] and h["CapDrop"]==["ALL"] and not h.get("CapAdd") and not h["Privileged"] and not h["AutoRemove"]
 assert h["LogConfig"]["Type"]=="none" and h["PortBindings"]=={"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"18866"}]}
 assert {(z["Source"],z["Destination"],z["RW"]) for z in info["Mounts"] if z["Type"]=="bind"}=={(str(B/"database"),"/var/lib/postgresql/data",True),(str(B/"container-passwd"),"/etc/passwd",False),(str(B/"container-group"),"/etc/group",False)}
 v.update(ownedContainerInspectedStopped=True,ownedContainerLimitsIndependentlyMatched=True,ownedDataDirectoryPreserved=(B/"database").is_dir())
if isinstance(v.get("failureCode"),str) and not re.fullmatch(r"[A-Z][A-Z0-9_: -]{0,160}",v["failureCode"]):
 v["failureCodeSha256"]="sha256:"+hashlib.sha256(v.pop("failureCode").encode()).hexdigest()
listeners={}
for port in [18765,18866,13000]:
 proc=subprocess.run(["/usr/sbin/lsof","-nP","-t","-iTCP:"+str(port),"-sTCP:LISTEN"],capture_output=True,text=True,timeout=15)
 assert proc.returncode in [0,1]
 listeners[str(port)]=sorted(set(proc.stdout.split()))
v["testPortListenerCountsAfterRun"]={port:len(pids)for port,pids in listeners.items()}
if all(not items for items in listeners.values()):
 v["testPortsHaveNoListeners"]=True
else:
 assert a is not None and a["servicesStarted"]==0 and not(B/"container.json").exists(),"A test listener still requires owned-process investigation"
 v["testPortsHaveNoListeners"]=False
 v["unownedPortCollisionRequiresReview"]=True
v["databasePort"]=18866
v["priorFailureFilesRehashed"]=len(read(D/"prior-admission-preimages.json"))
if a is not None:
 v["profileSyntaxExitCode"]=a.get("profileSyntaxExitCode")
 v["profileSyntaxStdoutBytes"]=a.get("profileSyntaxStdoutBytes")
 v["profileSyntaxStderrBytes"]=a.get("profileSyntaxStderrBytes")
 for n,key in [("stdout","profileSyntaxStdoutSha256"),("stderr","profileSyntaxStderrSha256")]:
  p=B/("profile-syntax."+n+".private")
  if p.exists():
   assert p.stat().st_size<=65536
   if a.get("profileSyntax"+n.title()+"Bytes",0)<=65536:
    assert sha(p)=="sha256:"+a[key]
 if a["servicesStarted"]>0:
  assert a["profileSyntaxExitCode"]==0
 v["profilePrecheckBeforeDatabaseSatisfied"]=a["servicesStarted"]==0 or a["profileSyntaxExitCode"]==0
v["reviewerDigest"]=sha(__file__)
P=R/"docs/acceptance/project-adoption/original-owner-auth-endpoint-20261029/services-localhost-profile-proposal-20261030";P.mkdir()
with(P/"review.json").open("x")as f:json.dump(v,f,indent=2);f.write("\n")
with(P/"review-services.py").open("xb")as f:f.write(Path(__file__).read_bytes())
with(P/"monitor.py").open("xb")as f:f.write((B/"monitor.py").read_bytes())
print(json.dumps(v))
