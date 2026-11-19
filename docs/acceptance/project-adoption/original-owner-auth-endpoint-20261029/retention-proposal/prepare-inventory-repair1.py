"""Proposal only: byte-verified redundant raw dependency copies; NEVER unlinks."""
from pathlib import Path
import json,hashlib,stat,os,subprocess,datetime
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps");B=Path(__file__).resolve().parent
root=Path("/Volumes/dev_src_case_sensitive/projects/.preservation/patamaps/build-states-envelope")
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as f:return"sha256:"+hashlib.file_digest(f,"sha256").hexdigest()
for p in Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds/scheduler/requests").glob("*.json"):
 assert read(p)["state"]not in["queued","preparing","running","needs-review"],"Job activity; proposal stopped"
capacity=read(B/"capacity.json");assert capacity["requiredReleaseBytes"]>0
snapshot=Path(read(R/".tools/owner-auth-endpoint-20261029/build-0/binding.json")["snapshot"])
manifest=read(snapshot/"manifest.json");entries=manifest["entries"]
large=[(n,v)for n,v in entries.items()if v["kind"]=="file"and v["byteLength"]>=2000000 and"node_modules/"in n and not any(x.startswith(".env")for x in Path(n).parts)]
service=read(R/".tools/owner-auth-endpoint-20261029/services-0/frozen.json")
protectedInputs=set(service["inputs"])
candidates=[]
for state in root.iterdir():
 if not state.is_dir():continue
 attempts=state/"attempts"
 if not attempts.is_dir():continue
 for a in attempts.iterdir():
  artifacts=a/"artifacts.json";plan=a/"plan.json"
  if not artifacts.is_file()or not plan.is_file():continue
  protected=read(artifacts);p=read(plan);explicit=set(p.get("project",{}).get("inputs",[]))
  for group in["buildSteps","verificationSteps","verifySteps"]:
   for cmd in p.get(group,[]):explicit.update(cmd.get("invocation",{}).get("codeInputs",[]))
  outputs=p.get("outputs",[])
  for n,row in large:
   target=a/"candidate"/n
   if str(target)in protectedInputs or n in protected or n in explicit:continue
   if any(o["path"]=="."or n==o["path"]or n.startswith(o["path"]+"/")for o in outputs):continue
   if not target.is_file()or target.is_symlink():continue
   s=target.lstat()
   if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=row["byteLength"]or stat.S_IMODE(s.st_mode)!=row["mode"]:continue
   candidates.append((s.st_blocks*512,str(target),n,row,artifacts,plan))
candidates.sort(key=lambda x:(-x[0],x[1]))
targetBytes=capacity["requiredReleaseBytes"]+200000000
selected=[];total=0;backups={};excluded=0
for allocated,name,n,row,artifacts,plan in candidates:
 if total>=targetBytes:break
 p=Path(name);s=p.lstat()
 if any(not stat.S_ISDIR(parent.lstat().st_mode)for parent in[p.parent,*p.parent.parents]):excluded+=1;continue
 before=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 backup=snapshot/"data"/n
 if n not in backups:
  assert backup.is_file()and not backup.is_symlink()
  assert sha(backup)==row["digest"]and backup.stat().st_size==row["byteLength"]
  backups[n]=dict(path=str(backup),sha256=row["digest"],bytes=row["byteLength"],mode=row["mode"])
 if sha(p)!=row["digest"]:excluded+=1;continue
 after=p.lstat();assert(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==before
 selected.append(dict(path=name,device=s.st_dev,inode=s.st_ino,mode=stat.S_IMODE(s.st_mode),links=s.st_nlink,logicalBytes=s.st_size,allocatedBytes=allocated,mtimeNs=s.st_mtime_ns,ctimeNs=s.st_ctime_ns,sha256=row["digest"],backupPath=str(backup),backupRelativePath=n,artifactManifestPath=str(artifacts),artifactManifestSha256=sha(artifacts),notSelectedArtifact=True,notDeclaredProjectInput=True,notCurrentAuthInput=True))
 total+=allocated
 if len(selected)%10==0:print(json.dumps(dict(verifiedFiles=len(selected),selectedAllocatedBytes=total)),flush=True)
assert total>=targetBytes,"Insufficient verified redundant copies; no approval question yet"
with(B/"inventory.jsonl").open("x")as f:
 for row in selected:f.write(json.dumps(row,separators=(",",":"))+"\n")
summary=dict(status="awaiting-exact-list-approval",files=len(selected),allocatedBytes=total,logicalBytes=sum(x["logicalBytes"]for x in selected),inventorySha256=sha(B/"inventory.jsonl"),requiredReleaseBytes=capacity["requiredReleaseBytes"],nominalMarginBeforeNewRecordsBytes=total-capacity["requiredReleaseBytes"],backupManifestPath=str(snapshot/"manifest.json"),backupManifestSha256=sha(snapshot/"manifest.json"),retainedBackups=list(backups.values()),backupBytesActuallyRehashed=True,allProposedCandidatesRehashed=True,selectedArtifactsProjectInputsAndCurrentAuthInputsExcluded=True,filesDeleted=0,directoriesSelected=0,filesystemRestorationExercised=False,independentOffDiskBackupVerified=False,futureCandidateBuildMayRequireRestoringRawDependencies=True,physicalFreedBytesClaimed=False,excludedDigestMismatches=excluded,observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inventoryDriverSha256=sha(__file__))
with(B/"summary.json").open("x")as f:json.dump(summary,f,indent=2);f.write("\n")
print(json.dumps({k:summary[k]for k in["status","files","allocatedBytes","requiredReleaseBytes","nominalMarginBeforeNewRecordsBytes","inventorySha256","filesDeleted"]}),flush=True)
