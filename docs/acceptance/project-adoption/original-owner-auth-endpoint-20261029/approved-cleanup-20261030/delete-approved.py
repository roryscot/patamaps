"""Exact user-approved compiler-file removal. Default preflight; no glob deletion."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,stat,subprocess
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=Path(__file__).resolve().parent
DEPS=R/".tools/project-adoption/next-runtime-architecture-20261028/native-0/aarch64"
WANTED="7ef75018d190317065d6831eee11884dbc0743bbef13f761fd1831c8ac8f7f8b"
parser=argparse.ArgumentParser();parser.add_argument("--apply-reviewed",action="store_true");args=parser.parse_args()
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write(name,v):
 with(B/name).open("x")as f:json.dump(v,f,indent=2);f.write("\n")
def check_stat(s,v):
 assert stat.S_ISREG(s.st_mode)
 assert(s.st_dev,s.st_ino,stat.S_IMODE(s.st_mode),s.st_nlink,s.st_size,s.st_blocks*512,s.st_mtime_ns,s.st_ctime_ns)==(
  v["device"],v["inode"],v["mode"],v["links"],v["logicalBytes"],v["allocatedBytes"],v["mtimeNs"],v["ctimeNs"]),v["path"]
def activity():
 scheduler=Path(os.environ["PATAMAPS_CLEANUP_SCHEDULER_ROOT"])
 owner=json.loads((scheduler/"transaction/owner.json").read_text())
 assert owner["pid"]==os.getppid()==int(os.environ["PATAMAPS_CLEANUP_TRANSACTION_PID"])
 for p in(scheduler/"requests").glob("*.json"):
  v=json.loads(p.read_text());assert v["state"]not in["running","preparing","queued","needs-review"],"Active or uncertain reservation"
 rows=subprocess.check_output(["/bin/ps","-axo","pid=,comm="],text=True)
 for row in rows.splitlines():
  p=row.strip().split(None,1)
  assert not(len(p)==2 and Path(p[1]).name in["cargo","rustc","clang","clang++","gcc","cc","c++","rust-lld"]),"Compiler active"
 docker="/Applications/Docker.app/Contents/Resources/bin/docker"
 ids=subprocess.check_output([docker,"ps","--quiet","--no-trunc"],text=True,timeout=30).split()
 for cid in ids:
  v=json.loads(subprocess.check_output([docker,"inspect",cid],text=True,timeout=30))[0]
  assert(v["Config"].get("Labels")or{}).get("buildctl.project")!=str(R)and"patamaps"not in v["Name"].lower(),"Patamaps container active"
 return dict(activeOrQueuedReservations=0,knownCompilers=0,patamapsContainers=0,runningOtherContainers=len(ids))

assert args.apply_reviewed
wanted="fe1f6374fb1e7d0024e035ebb112c96575d621ce72369bf81e8b0626b6bf441f"
assert sha(B/"inventory.jsonl")==wanted
a=json.loads((B/"APPROVAL.json").read_text());assert a["userApproved"]and a["inventorySha256"]==wanted
rows=[json.loads(x)for x in(B/"inventory.jsonl").read_text().splitlines()]
assert len(rows)==216 and sum(x["allocatedBytes"]for x in rows)==2450522112
summary=json.loads((B/"summary.json").read_text())
def backups():
 assert "sha256:"+sha(summary["backupManifestPath"])==summary["backupManifestSha256"]
 for x in summary["retainedBackups"]:assert "sha256:"+sha(x["path"])==x["sha256"]
def protected():
 F=json.loads((R/".tools/owner-auth-endpoint-20261029/services-0/frozen.json").read_text())
 for p,h in F["inputs"].items():assert "sha256:"+sha(p)==h
 for v in rows:assert "sha256:"+sha(v["artifactManifestPath"])==v["artifactManifestSha256"]
def db():
 d=json.loads(subprocess.check_output(["/Applications/Docker.app/Contents/Resources/bin/docker","inspect","advocates-local-advocates-db-1"],text=True,timeout=30))[0]
 return dict(id=d["Id"],running=d["State"]["Running"],startedAt=d["State"]["StartedAt"],restartCount=d["RestartCount"])
activity();beforeDB=db();backups();protected()
lsof=subprocess.run(["/usr/sbin/lsof","-nP","-Fpcfn",*[x["path"]for x in rows]],capture_output=True,text=True,timeout=30)
(B/"preunlink-lsof.private").write_text(lsof.stdout);(B/"preunlink-lsof-stderr.private").write_text(lsof.stderr)
assert lsof.returncode==1 and not lsof.stdout.strip()and not lsof.stderr.strip()
# All identities, bytes and real ancestors must pass before any removal.
for v in rows:
 p=Path(v["path"])
 for d in[p.parent,*p.parent.parents]:assert stat.S_ISDIR(d.lstat().st_mode)
 check_stat(p.lstat(),v);assert "sha256:"+sha(p)==v["sha256"];check_stat(p.lstat(),v)
activity();assert db()==beforeDB
removed=0;error=None
try:
 with(B/"deletion-journal.jsonl").open("x")as j:
  for v in rows:
   p=Path(v["path"])
   for d in[p.parent,*p.parent.parents]:assert stat.S_ISDIR(d.lstat().st_mode)
   dfd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
   fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=dfd)
   try:
    check_stat(os.fstat(fd),v)
    with os.fdopen(os.dup(fd),"rb")as f:assert "sha256:"+hashlib.file_digest(f,"sha256").hexdigest()==v["sha256"]
    check_stat(os.stat(p.name,dir_fd=dfd,follow_symlinks=False),v)
    j.write(json.dumps(dict(event="approved-unlink-intent",**v))+"\n");j.flush();os.fsync(j.fileno())
    os.unlink(p.name,dir_fd=dfd);removed+=1;assert os.fstat(fd).st_nlink==0
    j.write(json.dumps(dict(event="approved-file-unlinked",path=v["path"],device=v["device"],inode=v["inode"]))+"\n");j.flush();os.fsync(j.fileno())
   finally:os.close(fd);os.close(dfd)
 backups();protected();activity();assert db()==beforeDB
 assert all(not Path(v["path"]).exists()and Path(v["path"]).parent.is_dir()for v in rows)
except BaseException as e:error=type(e).__name__+": "+str(e);raise
finally:
 write("deletion-result.json",dict(status="completed-exact-approved-dependency-removal"if removed==216 and error is None else"stopped-for-review",filesDeleted=removed,directoriesDeleted=0,inventorySha256=wanted,protectedBindingsAndBackupsRehashed=True,protectedDatabaseStartIdentityUnchanged=db()==beforeDB,policyChanged=False,error=error,driverSha256=sha(__file__)))
 print(json.dumps(dict(filesDeleted=removed,error=error)),flush=True)
