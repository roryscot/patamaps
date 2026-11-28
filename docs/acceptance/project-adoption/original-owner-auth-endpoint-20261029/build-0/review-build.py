from pathlib import Path
import json,hashlib,subprocess,re,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=Path(__file__).resolve().parent/"build-0"
C=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds")
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return"sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
F=read(B/"frozen.json");m=read(B/"supervisor.json");exitrecord=read(B/"supervisor-exit.json")
requests=[read(p)for p in(C/"scheduler/requests").glob("*.json")]
matched=[r for r in requests if r["owner"]["pid"]==m["pid"]and r["project"]==str(R)and datetime.datetime.fromisoformat(r["createdAt"].replace("Z","+00:00"))>=datetime.datetime.fromisoformat(m["startedAtUtc"])]
assert len(matched)==1;request=matched[0]
assert request["state"]=="finished"and request.get("leaseReleaseCompleted")is True
stream=(B/"supervisor.stdout").read_text()+(B/"supervisor.stderr").read_text()
ids=re.findall(r"Storage guard record: "+re.escape(str(C))+r"/runs/([0-9a-f-]{36})/run[.]json",stream);assert len(ids)==1
guardfile=C/"runs"/ids[0]/"run.json";g=read(guardfile)
assert request["startedAt"]<=g["startedAt"]<=g["finishedAt"]<=request["finishedAt"]
assert g["root"]==str(R)and request["label"]==g["label"]=="patamaps"and g["filesDeleted"]==0
assert sha(B/"run.py")==F["driverDigest"]
for p,h in F["inputs"].items():assert sha(p)==h
receipt=read(B/"receipt.json")if(B/"receipt.json").exists()else None
out=dict(status="reviewed-endpoint-attempt",sourceRevision=F["sourceRevision"],ownerCommit=F["ownerCommit"],reservationId=request["id"],reservationFinished=True,leaseReleased=True,guardId=ids[0],guardRecordDigest=sha(guardfile),supervisorExitCode=exitrecord["exitCode"],guardExitCode=g["exitCode"],guardCompleted=g["completed"],frozenBindingsMatchedAtReview=True,temporaryPlanDraftEditDisclosed=True,executablesUnchanged=True,filesDeleted=0,policyChanged=False,authenticationAccepted=False,browserAccepted=False,fullGoalComplete=False)
if receipt is None:
 assert exitrecord["exitCode"]==g["exitCode"]==75
 out.update(status="verified-endpoint-admission-refusal",buildDriverExecuted=False,endpointCompiled=False,stopReasonDigest="sha256:"+hashlib.sha256(g.get("stopReason","").encode()).hexdigest())
else:
 out.update(buildDriverExecuted=True,driverStatus=receipt["status"],sourceInputs=receipt.get("sourceInputs"),declaredApiOrigin=receipt.get("declaredApiOrigin"),commands=[dict(role=x["role"],exitCode=x["measurement"]["exitCode"])for x in receipt["commands"]],endpointCompiled=False)
 if receipt["status"]=="passed-declared-owner-endpoint-build":
  assert exitrecord["exitCode"]==g["exitCode"]==0 and g["completed"]
  state=Path(receipt["state"]);selection=read(state/"selected.json")
  assert sha(state/"selected.json")==receipt["newState"]["pointer"]
  a=state/selection["attempt"];rows=read(a/"artifacts.json")
  for n,row in rows.items():
   if row["kind"]=="file":assert sha(a/"candidate"/n)==row["digest"]
  for row in receipt["endpointWitnesses"]:
   p=a/"candidate"/row["path"];assert sha(p)==row["digest"]and'const t="http://127.0.0.1:18765"'in p.read_text()
  fixture=read(R/".tools/installed-original-owner-next-20261027/owner-fixture.json")
  assert all(sha(a/"candidate"/n)==h for n,h in fixture["expectedGenerated"].items())
  for old,expected in receipt["previousStates"].items():
   old=Path(old);assert sha(old/"selected.json")==expected["pointer"]
   oldselected=read(old/"selected.json");attempt=old/oldselected["attempt"]
   assert sha(attempt/"artifacts.json")==expected["manifest"]
   for n,row in read(attempt/"artifacts.json").items():
    if row["kind"]=="file":assert sha(attempt/"candidate"/n)==row["digest"]
   assert sorted(p.name for p in(old/"attempts").iterdir())==expected["attempts"]
  out.update(status="verified-declared-owner-endpoint-build",endpointCompiled=True,generatedOutputs=receipt["generatedOutputs"],routeTestsPassed=receipt["routeTestsPassed"],endpointWitnesses=receipt["endpointWitnesses"],selectedArtifactFiles=receipt["newState"]["files"],selectedPointerDigest=receipt["newState"]["pointer"],previousSelectionsAndArtifactsRehashed=True)
 else:
  assert exitrecord["exitCode"]!=0
  out.update(status="verified-endpoint-build-failure",failureType=receipt.get("failureType"),failureCode=receipt.get("failure"),partialStatePreserved=True)
d=json.loads(subprocess.check_output(["/Applications/Docker.app/Contents/Resources/bin/docker","inspect","advocates-local-advocates-db-1"],text=True,timeout=20))[0]
old=read(R/".tools/owner-api-readiness-20261027/repair3-prepared/protected-service-before.json")
assert dict(id=d["Id"],running=d["State"]["Running"],startedAt=d["State"]["StartedAt"],restartCount=d["RestartCount"])==old
out.update(protectedDatabaseStartIdentityUnchanged=True,reviewerDigest=sha(__file__))
P=R/"docs/acceptance/project-adoption/original-owner-auth-endpoint-20261029/build-0";P.mkdir(parents=True)
with(P/"review.json").open("x")as f:json.dump(out,f,indent=2);f.write("\n")
for n in["run.py","monitor.py","launch-config.json"]:
 with(P/n).open("xb")as f:f.write((B/n).read_bytes())
with(P/"review-build.py").open("xb")as f:f.write(Path(__file__).read_bytes())
print(json.dumps(out))
