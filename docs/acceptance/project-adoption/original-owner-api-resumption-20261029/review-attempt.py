"""Review the one human-approved API readiness launch without re-execution or raw logs."""
from pathlib import Path
import hashlib,json,re,subprocess,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=R/".tools/owner-api-readiness-20261027/repair3-prepared"
CONTROL=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds")
D=R/".tools/owner-api-readiness-20261027/repair3-approved-resumption-20261029"
RID=None
OUT=R/"docs/acceptance/project-adoption/original-owner-api-resumption-20261029"
DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
a=read(B/"APPROVAL.json");frozen=read(B/"frozen.json");before=read(B/"launch-binding-review.json")
assert a["additionalPhaseAttemptAuthorized"]is True and a["maximumAdditionalLaunches"]==1 and a["automaticRepairs"]is False
assert sha(B/"sandbox.sb")==a["preparedProfileSha256"]=="1d49cd4625b3f06cb11cb0670f1da02b41249780e351056d6c87275f1ccbc436"
assert sha(B/"frozen.json")==a["frozenManifestSha256"]and sha(B/"launch-config.json")==a["launchConfigSha256"]
assert all(sha(B/name)==digest for name,digest in before["drivers"].items())
for key in["sourceInputs","runnerInputs","interpreterExecutables"]:
 root=Path(frozen["owner"])if key=="sourceInputs"else B
 for row in frozen[key]:
  p=Path(row["path"]);p=p if p.is_absolute()else root/p
  assert p.name!=".env"and not p.name.startswith(".env."),"Refuse environment-file read"
  assert sha(p)==row["sha256"],"Frozen input changed"
assert subprocess.check_output(["/usr/bin/git","rev-parse","HEAD"],cwd=frozen["owner"],text=True).strip()==frozen["ownerCommit"]
previous=read(B/"previous-failure-preimages.json");assert len(previous)==16
assert all(sha(x["path"])==x["sha256"]for x in previous)
monitor=read(D/"supervisor.json");exitrecord=read(D/"supervisor-exit.json")
requests=[read(p) for p in(CONTROL/"scheduler/requests").glob("*.json")]
matched=[r for r in requests if r["owner"]["pid"]==monitor["pid"] and r["project"]==str(R) and datetime.datetime.fromisoformat(r["createdAt"].replace("Z","+00:00"))>=datetime.datetime.fromisoformat(monitor["startedAtUtc"])]
assert len(matched)==1
RID=matched[0]["id"]
request=read(CONTROL/"scheduler/requests"/(RID+".json"))
assert request["owner"]["pid"]==monitor["pid"]and request["project"]==str(R)
assert str(B/"preflight.py")in request["command"]
assert request["state"]=="finished"and request["leaseReleaseCompleted"]is True,"Reservation not safely released"
stream=(D/"supervisor.stdout").read_text()+(D/"supervisor.stderr").read_text()
ids=re.findall(r"Storage guard record: "+re.escape(str(CONTROL))+r"/runs/([0-9a-f-]{36})/run[.]json",stream)
assert len(ids)==1
guardfile=CONTROL/"runs"/ids[0]/"run.json";guard=read(guardfile)
assert guard["root"]==str(R)and guard["label"]==request["label"]=="patamaps"and guard["filesDeleted"]==0
assert request["startedAt"]<=guard["startedAt"]<=guard["finishedAt"]<=request["finishedAt"]
protected=read(D/"protected-service-before.json")
db=json.loads(subprocess.check_output([DOCKER,"inspect","advocates-local-advocates-db-1"],text=True,timeout=30))[0]
after=dict(id=db["Id"],running=db["State"]["Running"],startedAt=db["State"]["StartedAt"],restartCount=db["RestartCount"])
assert protected==after and after["running"]is True
receiptfile=B/"receipt.json";receipt=read(receiptfile)if receiptfile.exists()else None
summary=dict(status="reviewed-approved-api-attempt",sourceRevision=read(D/"launch-binding-review.json")["sourceRevision"],frozenPayloadPreparedAtRevision=before["sourceRevision"],ownerCommit=frozen["ownerCommit"],
 reservationId=RID,reservationFinished=True,leaseReleased=True,guardId=ids[0],guardRecordSha256=sha(guardfile),
 supervisorExitCode=exitrecord["exitCode"],guardCompleted=guard["completed"],guardExitCode=guard["exitCode"],
 sourceInputCount=len(frozen["sourceInputs"]),runnerInputCount=len(frozen["runnerInputs"]),interpreterExecutableCount=len(frozen["interpreterExecutables"]),
 allFrozenBindingsRechecked=True,profileSha256=sha(B/"sandbox.sb"),earlierFailedRecordsMatched=len(previous),
 protectedDatabaseStartIdentityUnchanged=True,servicesStarted=0,packagesInstalled=0,filesDeleted=0,policyChanged=False,
 apiImportsAccepted=False,authenticationAccepted=False,originalOwnerBrowserAccepted=False,fullGoalComplete=False)
if receipt is None:
 assert exitrecord["exitCode"]==75 and guard["exitCode"]==75 and guard["completed"]is False
 assert not(B/"run").exists(),"Preparation began; inspect partial result explicitly"
 assert guard["stopReason"].startswith("Insufficient retained-output headroom"),"Unexpected guard failure"
 summary.update(status="verified-approved-api-admission-refusal",preflightExecuted=False,securityControlsExecuted=False,
  libraryImportsExecuted=0,applicationImportExecuted=False,stopReason="insufficient-retained-output-headroom",apiReadinessAccepted=False)
else:
 assert receipt["sourceBindingRechecked"]is True and receipt["sourceInputCount"]==387
 assert exitrecord["exitCode"]==guard["exitCode"]==receipt["childExitCode"]
 report=receipt["childReport"];assert report is not None,"Missing child report requires partial audit"
 controls=report["sandboxControls"];assert set(controls)=={"networkDenied","outsideWriteDenied","dotenvReadDenied"}
 imports=report["imports"]
 expected=["bcrypt","pydantic_core","fastapi","uvicorn","sqlalchemy","psycopg2","asyncpg","pydantic_settings","jose","passlib.context","httpx","redis","greenlet","alembic","email_validator"]
 assert [x["module"]for x in imports]==expected if imports else not all(controls.values())
 app=report["application"]
 for name in["stdout","stderr"]:
  p=B/"run"/name;assert p.stat().st_size==receipt[name]["bytes"]<=4194304 and sha(p)==receipt[name]["sha256"]
 ready=all(controls.values())and len(imports)==15 and all(x["status"]=="passed"for x in imports)and app is not None and app["status"]=="passed"
 if ready:assert receipt["childExitCode"]==0 and guard["completed"]is True
 else:assert receipt["childExitCode"]!=0
 summary.update(status="verified-api-import-readiness"if ready else"verified-api-readiness-failure",
  preflightExecuted=True,securityControlsExecuted=True,sandboxControls=controls,libraryImportsExecuted=len(imports),
  libraryImportResults=[dict(module=x["module"],status=x["status"],**({"exceptionType":x["exceptionType"]}if x["status"]!="passed"else{}))for x in imports],
  applicationImportExecuted=app is not None,applicationImportStatus=None if app is None else app["status"],
  apiImportsAccepted=ready,apiReadinessAccepted=ready and all(app.get(k)is True for k in["authLoginPresent","authMePresent","permissionsPresent"])if ready else False,
  privateReceiptSha256=sha(receiptfile),privateStdoutSha256=receipt["stdout"]["sha256"],privateStderrSha256=receipt["stderr"]["sha256"])
assert all(sha(row["path"])==row["sha256"] for row in read(D/"original-admission-preimages.json"))
assert sha(D/"monitor.py")==sha(B/"monitor.py") and sha(D/"launch-config.json")==sha(B/"launch-config.json")
assert read(R/".tools/retention-review-20261029-arm-node-copy/independent-review.json")["filesDeleted"]==1
summary.update(originalAdmissionRefusalPreserved=True,maximumActualApiPreflights=1,automaticRepairs=False,approvedSeparateCleanupFilesDeleted=1,earlierFailedInputRecordsRehashed=16)
summary["reviewerSha256"]=sha(__file__)
OUT.mkdir(exist_ok=False)
with(OUT/"review.json").open("x")as out:json.dump(summary,out,indent=2);out.write("\n")
for name in["preflight.py","child.py","monitor.py","sandbox.sb"]:
 with(OUT/name).open("xb")as out:out.write((B/name).read_bytes())
with(OUT/"review-attempt.py").open("xb")as out:out.write(Path(__file__).read_bytes())
print(json.dumps(summary))
