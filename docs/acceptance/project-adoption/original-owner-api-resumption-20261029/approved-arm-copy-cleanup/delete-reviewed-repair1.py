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

import tarfile
assert args.apply_reviewed
assert sha(B/"inventory.jsonl")==WANTED
approval=json.loads((B/"APPROVAL.json").read_text())
assert approval["userApproved"]is True and approval["inventorySha256"]==WANTED
rows=[json.loads(x)for x in(B/"inventory.jsonl").read_text().splitlines()]
assert len(rows)==1
v=rows[0];p=Path(v["path"])
assert p==DEPS/"runtime"and v["allocatedBytes"]==118345728
s=json.loads((B/"summary.json").read_text())
assert not(B/"repair1-deletion-journal.jsonl").exists()and not(B/"repair1-deletion-result.json").exists()
def backups():
 assert sha(s["archive"])==s["archiveSha256"]
 assert sha(s["retainedFailedCandidate"])==v["sha256"]
 with tarfile.open(s["archive"],"r:xz")as t:
  matches=[m for m in t if m.name==s["archiveMember"]]
  assert len(matches)==1 and matches[0].isfile()and matches[0].mode==v["mode"]and matches[0].size==v["logicalBytes"]
  with t.extractfile(matches[0])as f:assert hashlib.file_digest(f,"sha256").hexdigest()==v["sha256"]
 pointer=Path("/Volumes/dev_src_case_sensitive/projects/.preservation/patamaps/build-states-envelope/original-next-node-20261028/selected.json")
 assert sha(pointer)=="6db82ee515f78afb0b83339ff66eb1beb3fb7e3fae3d87534aa51a0ca46d0238"
 assert sha(R/"target/debug/patamaps")=="cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355"
def db():
 d=json.loads(subprocess.check_output(["/Applications/Docker.app/Contents/Resources/bin/docker","inspect","advocates-local-advocates-db-1"],text=True,timeout=30))[0]
 return dict(id=d["Id"],running=d["State"]["Running"],startedAt=d["State"]["StartedAt"],restartCount=d["RestartCount"])
before=activity();beforeDB=db();assert beforeDB["running"]
backups()
for parent in[p.parent,*p.parent.parents]:assert stat.S_ISDIR(parent.lstat().st_mode)
dfd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);ds=os.fstat(dfd)
lsof=subprocess.run(["/usr/sbin/lsof","-nP","-Fpcfn",str(p)],capture_output=True,text=True,timeout=20)
(B/"repair1-preunlink-lsof.private").write_text(lsof.stdout)
(B/"repair1-preunlink-lsof-stderr.private").write_text(lsof.stderr)
assert lsof.returncode==1 and not lsof.stdout.strip()and not lsof.stderr.strip(),"Open consumer or uncertain inspection"
fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=dfd)
removed=0;error=None
try:
 check_stat(os.fstat(fd),v)
 with os.fdopen(os.dup(fd),"rb")as f:assert hashlib.file_digest(f,"sha256").hexdigest()==v["sha256"]
 check_stat(os.fstat(fd),v)
 activity();assert db()==beforeDB
 assert(p.parent.stat().st_dev,p.parent.stat().st_ino)==(ds.st_dev,ds.st_ino)
 check_stat(os.stat(p.name,dir_fd=dfd,follow_symlinks=False),v)
 with(B/"repair1-deletion-journal.jsonl").open("x")as j:
  j.write(json.dumps(dict(event="approved-unlink-intent",**v))+"\n");j.flush();os.fsync(j.fileno())
  os.unlink(p.name,dir_fd=dfd);removed=1
  assert os.fstat(fd).st_nlink==0
  try:os.stat(p.name,dir_fd=dfd,follow_symlinks=False)
  except FileNotFoundError:pass
  else:raise AssertionError("Approved path reappeared")
  j.write(json.dumps(dict(event="approved-file-unlinked",path=v["path"],device=v["device"],inode=v["inode"]))+"\n");j.flush();os.fsync(j.fileno())
 backups();activity();assert db()==beforeDB and not p.exists()
except BaseException as e:
 error=type(e).__name__+": "+str(e);raise
finally:
 os.close(fd);os.close(dfd)
 result=dict(status="completed-exact-approved-arm-copy-removal"if removed==1 and error is None else"stopped-for-review",filesDeleted=removed,approvedFiles=1,inventorySha256=WANTED,allocatedBytesSelected=v["allocatedBytes"],directoriesDeleted=0,archiveAndRetainedCandidateRehashed=True,selectedPointerAndCliUnchanged=True,protectedDatabaseStartIdentityUnchanged=db()==beforeDB,servicesStopped=0,policyChanged=False,physicalFreedBytesClaimed=False,error=error,driverSha256=sha(__file__),recordedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 write("repair1-deletion-result.json",result);print(json.dumps(result),flush=True)
