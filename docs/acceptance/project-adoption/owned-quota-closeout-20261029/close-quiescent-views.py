"""Normal closure of explicitly inspected finished owned quota views; never deletes."""
from pathlib import Path
import json,hashlib,subprocess,os,stat,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=Path(__file__).resolve().parent
C=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds")
IDS=["dd7f6893-0d07-4364-989a-35cc6fadab27","0e3c4d70-2ab6-4853-89ca-aad6d83748c5","2dd79d43-fae4-45e0-b1ce-7e52ac243afb","ad3339dd-9c2d-4781-9757-279fd295f692","e8a38608-124e-4d30-846e-7ad726b0689b","8569ca95-2790-47d8-b484-0ade4229b3bb"]
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
 with Path(p).open("x")as f:json.dump(v,f,indent=2);f.write("\n")
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
def activity():
 root=Path(os.environ["PATAMAPS_CLOSE_SCHEDULER_ROOT"])
 assert read(root/"transaction/owner.json")["pid"]==os.getppid()==int(os.environ["PATAMAPS_CLOSE_TRANSACTION_PID"])
 for p in(root/"requests").glob("*.json"):assert read(p)["state"]not in["queued","running","preparing","needs-review"],"Active reservation"
def inventory(root):
 entries=[]
 assert root.is_dir()and not root.is_symlink()
 for p in sorted(root.rglob("*")):
  s=p.lstat();name=p.relative_to(root).as_posix();mode=stat.S_IMODE(s.st_mode)
  if stat.S_ISLNK(s.st_mode):entry=dict(path=name,kind="symlink",mode=mode,target=os.readlink(p))
  elif stat.S_ISREG(s.st_mode):
   assert p.name!=".env"and not p.name.startswith(".env."),"Refuse environment-file read"
   entry=dict(path=name,kind="file",mode=mode,bytes=s.st_size,sha256=sha(p))
  elif stat.S_ISDIR(s.st_mode):entry=dict(path=name,kind="directory",mode=mode)
  else:raise RuntimeError("Unsupported member")
  entries.append(entry);assert len(entries)<=32768
 return entries
def docker(*args):return subprocess.check_output(["/Applications/Docker.app/Contents/Resources/bin/docker",*args],text=True,timeout=30)
def db():
 d=json.loads(docker("inspect","advocates-local-advocates-db-1"))[0]
 return dict(id=d["Id"],running=d["State"]["Running"],startedAt=d["State"]["StartedAt"],restartCount=d["RestartCount"])
def hdi(args,target,prefix):
 p=subprocess.run(["/usr/bin/hdiutil",*args],capture_output=True,text=True,timeout=60)
 (target/(prefix+".stdout.private")).write_text(p.stdout);(target/(prefix+".stderr.private")).write_text(p.stderr)
 assert p.returncode==0,"Normal disk operation refused; no force or retry"
 return p.returncode
activity();beforeDB=db();assert beforeDB["running"]is True
inspected=read(B/"inspection.json")+read(B/"additional-inspection.json")
api=read(R/".tools/owner-api-readiness-20261027/repair3-prepared/frozen.json")
apiPaths=[Path(api["owner"]),Path(api["site"]),Path(api["pythonRealPath"])]
apiPaths.extend(Path(api["owner"])/x["path"]for x in api["sourceInputs"])
summary=dict(status="running-owned-view-closure",volumes=[],filesDeleted=0,servicesStopped=0,policyChanged=False,forceUsed=False)
error=None
try:
 for rid in IDS:
  activity();previous=next(x for x in inspected if x["id"]==rid);assert previous["safeForNormalClosure"]is True
  r=read(C/"scheduler/requests"/(rid+".json"));w=r["workspace"];mount=Path(w["mount"]);work=Path(w["work"]);image=Path(w["image"])
  assert r["project"]==str(R)and r["state"]=="finished"and r["enforcement"]=="container-fixed-volume"and r["ownershipSealed"]
  assert str(image).startswith(str(R/".tools/buildctl")+"/")and image.parent==Path(w["home"])
  assert r["releaseProof"]["containerStopped"]and r["releaseProof"]["hostProcessGroupStopped"]
  assert all(not str(p.resolve(strict=True)).startswith(str(mount)+"/")for p in apiPaths),"API dependency is in volume"
  for cid in r["containerIds"]:
   d=json.loads(docker("inspect",cid))[0];s=d["State"]
   assert not s["Running"]and not s["Paused"]and not s["Restarting"]and s["Pid"]==0
   assert d["Config"]["Labels"]["buildctl.request"]==rid and d["Config"]["Labels"]["buildctl.project"]==str(R)
  target=B/("closure-"+rid);target.mkdir(exist_ok=False)
  p=subprocess.run(["/usr/sbin/lsof","-nP","-Fpcfn","+D",str(mount)],capture_output=True,text=True,timeout=20)
  (target/"preclosure-lsof.private").write_text(p.stdout);(target/"preclosure-lsof-stderr.private").write_text(p.stderr)
  assert p.returncode==1 and not p.stdout.strip()and not p.stderr.strip(),"Open handle or uncertain inventory; no closure"
  initial=inventory(work);write(target/"work-inventory.json",initial)
  s=image.lstat();identity=(s.st_dev,s.st_ino,s.st_size)
  assert stat.S_ISREG(s.st_mode)and s.st_size==w["imageBytes"]<=r["limits"]["diskBytes"]
  hdi(["detach",str(mount)],target,"normal-detach")
  assert not work.exists()and image.is_file()
  assert(image.stat().st_dev,image.stat().st_ino,image.stat().st_size)==identity
  closedDigest=sha(image)
  hdi(["attach","-readonly","-nobrowse","-noautoopen","-mountpoint",str(mount),str(image)],target,"readonly-restore")
  assert os.statvfs(work).f_flag&os.ST_RDONLY
  assert inventory(work)==initial,"Read-only restored file bytes/modes differ"
  hdi(["detach",str(mount)],target,"final-normal-detach")
  assert not work.exists()and sha(image)==closedDigest
  assert(image.stat().st_dev,image.stat().st_ino,image.stat().st_size)==identity
  row=dict(id=rid,imageBytes=identity[2],closedImageSha256=closedDigest,workEntries=len(initial),
   workFiles=sum(x["kind"]=="file"for x in initial),readonlyRestorationBytesModesMatched=True,
   readonlyCycleImageBytesUnchanged=True,normalFinalClosure=True,backingImagePreserved=True,filesDeleted=0)
  write(target/"result.json",row);summary["volumes"].append(row)
  print(json.dumps(dict(id=rid,status="closed-preserved-readonly-restoration-verified")),flush=True)
 assert db()==beforeDB
 summary["status"]="passed-owned-quota-view-closure"
except BaseException as e:
 error=type(e).__name__+": "+str(e);summary["status"]="stopped-owned-view-closure-for-review";raise
finally:
 summary.update(error=error,protectedDatabaseStartIdentityUnchanged=db()==beforeDB,driverSha256=sha(__file__),
  recordedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),actualPhysicalFreedBytesClaimed=False,
  capacityAdmissionRechecked=False,apiPreflightRepeated=False)
 write(B/"closure-result.json",summary);print(json.dumps({k:summary[k]for k in["status","filesDeleted","servicesStopped","protectedDatabaseStartIdentityUnchanged","error"]}),flush=True)
