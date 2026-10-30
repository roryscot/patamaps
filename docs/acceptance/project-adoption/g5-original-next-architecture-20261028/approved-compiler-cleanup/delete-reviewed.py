"""Exact user-approved compiler-file removal. Default preflight; no glob deletion."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,stat,subprocess
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
B=Path(__file__).resolve().parent
DEPS=R/"target/debug/deps"
WANTED="35043a7a4eba81a2701edf78ae88f43d08d4a250ea46af4cb74ead7d2e11b939"
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
assert sha(B/"inventory.jsonl")==WANTED
rows=[json.loads(x)for x in(B/"inventory.jsonl").read_text().splitlines()]
assert len(rows)==472 and len({x["path"]for x in rows})==472
assert sum(x["allocatedBytes"]for x in rows)==537149440
assert all(Path(x["path"]).parent==DEPS and Path(x["path"]).name not in[".",".."]for x in rows)
if args.apply_reviewed:
 approval=json.loads((B/"APPROVAL.json").read_text())
 assert approval["userApproved"]is True and approval["inventorySha256"]==WANTED and approval["userAnswer"]=="Approve deleting only these 472 inventoried files"
 assert not(B/"deletion-result.json").exists()and not(B/"deletion-journal.jsonl").exists()
before=activity()
assert all(stat.S_ISDIR(p.lstat().st_mode)for p in[DEPS,*DEPS.parents])
dfd=os.open(DEPS,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
ds=os.fstat(dfd)
protected={
 R/"target/debug/patamaps":"cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355",
 Path("/Volumes/dev_src_case_sensitive/projects/.preservation/patamaps/build-states-envelope/original-next-node-20261028/selected.json"):"6db82ee515f78afb0b83339ff66eb1beb3fb7e3fae3d87534aa51a0ca46d0238"}
excluded=json.loads((B/"excluded.json").read_text())
def preserved():
 assert(DEPS.stat().st_dev,DEPS.stat().st_ino)==(ds.st_dev,ds.st_ino)
 for v in excluded:
  s=Path(v["path"]).lstat()
  assert stat.S_ISDIR(s.st_mode)and(s.st_dev,s.st_ino,stat.S_IMODE(s.st_mode))==(v["device"],v["inode"],int(v["mode"],8))
 assert all(sha(p)==d for p,d in protected.items())
preserved()
# Verify the entire unchanged approved list before removing any member.
for v in rows:
 name=Path(v["path"]).name
 fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=dfd)
 try:
  check_stat(os.fstat(fd),v)
  with os.fdopen(os.dup(fd),"rb")as f:assert hashlib.file_digest(f,"sha256").hexdigest()==v["sha256"]
  check_stat(os.fstat(fd),v);check_stat(os.stat(name,dir_fd=dfd,follow_symlinks=False),v)
 finally:os.close(fd)
activity();preserved()
if not args.apply_reviewed:
 os.close(dfd);print(json.dumps(dict(status="passed-exact-approved-list-preflight",files=472,allocatedBytes=537149440,activity=before,filesDeleted=0)));raise SystemExit(0)
removed=0;failure=None
try:
 with(B/"deletion-journal.jsonl").open("x")as journal:
  for v in rows:
   preserved_dir=DEPS.stat();assert(preserved_dir.st_dev,preserved_dir.st_ino)==(ds.st_dev,ds.st_ino)
   name=Path(v["path"]).name;fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=dfd)
   try:
    check_stat(os.fstat(fd),v)
    with os.fdopen(os.dup(fd),"rb")as f:assert hashlib.file_digest(f,"sha256").hexdigest()==v["sha256"]
    check_stat(os.fstat(fd),v);check_stat(os.stat(name,dir_fd=dfd,follow_symlinks=False),v)
    journal.write(json.dumps(dict(event="approved-unlink-intent",**v))+"\n");journal.flush();os.fsync(journal.fileno())
    os.unlink(name,dir_fd=dfd)
    removed+=1;assert os.fstat(fd).st_nlink==0
    try:os.stat(name,dir_fd=dfd,follow_symlinks=False)
    except FileNotFoundError:pass
    else:raise AssertionError("Approved path reappeared")
    journal.write(json.dumps(dict(event="approved-file-unlinked",path=v["path"],device=v["device"],inode=v["inode"]))+"\n");journal.flush();os.fsync(journal.fileno())
   finally:os.close(fd)
 preserved();after=activity();assert all(not Path(v["path"]).exists()for v in rows)
except BaseException as error:
 failure=type(error).__name__+": "+str(error);raise
finally:
 os.close(dfd)
 result=dict(status="completed-exact-approved-compiler-cleanup"if removed==472 and failure is None else"partial-cleanup-stop-for-review",
  recordedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inventorySha256=WANTED,filesDeleted=removed,
  approvedFiles=472,allocatedBytesSelected=537149440,directoriesDeleted=0,excludedDirectoriesPreserved=4,
  protectedCliAndSelectionUnchanged=all(sha(p)==d for p,d in protected.items()),servicesStopped=0,policyChanged=False,
  sourceApplicationEvidenceArchivesSelected=False,physicalFreedBytesClaimed=False,error=failure,driverSha256=sha(__file__))
 write("deletion-result.json",result);print(json.dumps(result),flush=True)
