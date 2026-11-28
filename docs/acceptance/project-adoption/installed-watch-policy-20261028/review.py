"""Read-only audit of the exact updated source/native watch installation."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,os,re,stat,subprocess,tarfile
REV="37c19bca08490bdfeec7f7db53dcc65415517d12"
BINARY="sha256:cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355"
INVENTORY="sha256:f3c9adb5c42d0fe7e38d666d8fc7b26dcc531d5f315544e95be7dc5fbc71ab81"
WATCH="sha256:69c476ee89507f08f54498d73cbad7306408658643215ea39fb721657dec676b"
def need(v,m):
 if not v:raise RuntimeError(m)
def read(p):return json.loads(p.read_text())
def stream_sha(f):
 h=hashlib.sha256()
 while b:=f.read(1048576):h.update(b)
 return "sha256:"+h.hexdigest()
def sha(p):
 with p.open("rb") as f:return stream_sha(f)
def absent(pid):
 x=subprocess.run(["/bin/ps","-p",str(pid),"-o","pid="],capture_output=True,text=True,timeout=5)
 return x.returncode==1 and not x.stdout.strip()
def archive_matches(path,installed):
 expected={p.relative_to(installed).as_posix():p for p in installed.rglob("*") if p.is_file()}
 seen=set();top=installed.name
 with tarfile.open(path,"r:gz") as archive:
  for m in archive:
   name=Path(m.name)
   need(not name.is_absolute() and ".." not in name.parts and name.parts[0]==top,"unsafe archive member")
   if m.isdir():continue
   need(m.isfile() and len(name.parts)>1,"archive special file")
   rel=Path(*name.parts[1:]).as_posix();need(rel in expected and rel not in seen,"archive membership changed")
   p=expected[rel];need(m.size==p.stat().st_size and stat.S_IMODE(p.stat().st_mode)==m.mode,"archive bytes/mode metadata")
   with archive.extractfile(m) as f:need(stream_sha(f)==sha(p),"archive/extraction byte mismatch")
   seen.add(rel)
 need(seen==set(expected),"missing archive file")
 return len(seen)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ["root","node","buildctl","output"]:p.add_argument("--"+n,type=Path,required=True)
 a=p.parse_args();root=a.root;w=root/".tools/installed-watch-policy-20261028"
 need(not a.output.exists(),"output exists")
 r=read(w/"receipt.json");frozen=read(w/"frozen.json")
 need(read(w/"supervisor-exit.json")["exitCode"]==0 and r["status"]=="passed-packaged-installed-watch-policy-controls","package not passed")
 need(r["sourceRevision"]==frozen["revision"]==REV and sha(w/"run.py")==frozen["driverDigest"]=="sha256:16ea7a1260d55af1f9eb71ccb160883276f1e187d22375ce9f92a9c6118f1c37","producer/controller binding")
 for n,d in frozen["producerInputs"].items():need(sha(root/n)==d,"producer source changed")
 for n in ["launch.json","supervisor.json"]:need(absent(read(w/n)["pid"]),"package owner still live")
 dist=read(w/"package/distribution.json");need(dist==r["distribution"],"distribution changed")
 need(dist["target"]=="x86_64-apple-darwin" and dist["buildProfile"]=="development","native target/profile")
 source=Path(r["installedSource"]);native=Path(r["installedNative"]);cli=native/"bin/patamaps"
 need(not (source/".git").exists(),"source has Git")
 need(sha(source/"source-inventory.json")==dist["sourceInventoryDigest"]==r["sourceIdentity"]["sourceInventoryDigest"]==INVENTORY,"source inventory changed")
 rows=read(source/"source-inventory.json");need(len(rows)==1255==r["sourceMembersMatchedGit"],"source member count")
 expected={e["path"] for e in rows}|{"source-inventory.json"}
 actual=set()
 for q in source.rglob("*"):
  need(not q.is_symlink(),"source symlink")
  if q.is_dir():continue
  need(q.is_file(),"source special file");actual.add(q.relative_to(source).as_posix())
 need(actual==expected,"source membership changed")
 for e in rows:
  q=source/e["path"];need(q.stat().st_size==e["bytes"] and sha(q)==e["digest"],"installed source byte mismatch")
 tree=subprocess.check_output(["git","ls-tree","-r",REV],cwd=root).splitlines();blobs={}
 for line in tree:
  metadata,name=line.split(b"\t",1);mode,kind,oid=metadata.split()
  if kind==b"blob":blobs[name.decode()]=oid
 need(all(e["path"] in blobs for e in rows),"untracked source member")
 batch=subprocess.run(["git","cat-file","--batch"],cwd=root,input=b"\n".join(blobs[e["path"]] for e in rows)+b"\n",capture_output=True,check=True).stdout
 offset=0
 for e in rows:
  end=batch.index(b"\n",offset);oid,kind,size=batch[offset:end].split();offset=end+1;size=int(size);raw=batch[offset:offset+size];offset+=size
  need(batch[offset:offset+1]==b"\n","Git batch separator");offset+=1
  need(oid==blobs[e["path"]] and kind==b"blob" and len(raw)==e["bytes"] and "sha256:"+hashlib.sha256(raw).hexdigest()==e["digest"],"Git source bytes differ")
 need(offset==len(batch),"trailing Git batch bytes")
 archives={}
 for key,installed in [("sourceArchive",source),("nativeArchive",native)]:
  item=dist[key];path=w/"package"/item["path"]
  need(sha(path)==item["digest"],"archive digest changed")
  count=archive_matches(path,installed)
  archives[key]=dict(digest=item["digest"],bytes=path.stat().st_size,regularFilesMatched=count)
 old=root/".tools/installed-original-owner-next-20261027/package-source"
 oldr=read(old/"receipt.json");olds=Path(oldr["installedSource"])
 need(sha(olds/"source-inventory.json")==frozen["previousSourceInventoryDigest"] and sha(Path(oldr["nativeCli"]))==BINARY,"old accepted pair changed")
 def rust_code(entries):return {e["path"]:e for e in entries if e["path"].startswith(("crates/","vendor/")) or e["path"] in ["Cargo.toml","Cargo.lock","rust-toolchain.toml"]}
 code=rust_code(rows);need(code==rust_code(read(olds/"source-inventory.json")) and len(code)==188,"Rust build inputs changed")
 for e in code.values():need(sha(olds/e["path"])==e["digest"],"previously compiled input changed")
 need(sha(cli)==dist["binaryDigest"]==r["nativeCliDigest"]==BINARY and stat.S_IMODE(cli.stat().st_mode)==0o755,"native binary changed")
 engine=json.loads(subprocess.check_output([str(cli),"engine"],text=True,timeout=20))
 spec=importlib.util.spec_from_file_location("installed_watch_package_identity",source/"scripts/parity/identity.py")
 identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)
 need(engine==dist["engines"]==r["engine"]=={"schemaVersion":"0.1.0","documentType":"executor-description",**identity.identities(source)},"source/native engine mismatch")
 need(sha(source/"scripts/project_watch.py")==WATCH==r["installedWatchDigest"],"watch helper changed")
 need(sha(source/"scripts/test_watch_policy_verification.py")==r["installedTestDigest"],"installed test changed")
 need(len(r["commands"])==4 and all(c["measurement"]["exitCode"]==0 for c in r["commands"]),"package command failures")
 for c in r["commands"]:
  m=c["measurement"];need(absent(m["pid"]),"package command still live")
  for stream in ["stdout","stderr"]:need(sha(w/(c["role"]+"."+stream))==m[stream+"Digest"],"retained command log changed")
 text=(w/"installed-watch-controls.stderr").read_text();need("Ran 11 tests" in text and text.rstrip().endswith("OK") and "skipped=" not in text,"installed unittest completion")
 cases=list((w/"controls").iterdir());need(len(cases)==1 and len(list(cases[0].iterdir()))==11,"installed case count")
 main=cases[0]/"test_main_queues_build_and_verification_before_completion"
 need(str(source/"scripts") in (main/"controlled-main.py").read_text(),"test main imported wrong helper")
 audit=[json.loads(x) for x in (main/"native-audit.jsonl").read_text().splitlines()]
 need([x for x in audit if x["command"] in ["project-build","project-build-verify"]]==[dict(command="project-build",reserved=True),dict(command="project-build-verify",reserved=True)],"full scan outside controlled policy")
 need((main/"runner-audit.txt").read_text().splitlines()==["call","call"],"policy call count")
 ps=subprocess.check_output(["/bin/ps","-axo","pid=,args="],text=True,timeout=20).splitlines()
 need(not any(str(w/"controls") in x for x in ps),"controlled process survived")
 status=json.loads(subprocess.check_output([str(a.node),str(a.buildctl),"status"],text=True,timeout=20))
 need(not status["parallelActivated"] and status["legacyLease"] is None and not status["transactionBlocked"],"scheduler uncertain")
 rid=re.search(r"Build reservation queued: ([0-9a-f-]{36});",(w/"supervisor.stderr").read_text()).group(1)
 req=next(x for x in status["requests"] if x["id"]==rid)
 need(req["state"]=="finished" and req["leaseReleaseCompleted"] and req["enforcement"]=="native-exclusive" and req["limits"]["diskBytes"]==4000000000,"reservation not released/changed")
 gp=Path(re.search(r"^Storage guard record: (.+)$",(w/"supervisor.stdout").read_text(),re.M).group(1));g=read(gp)
 need(g["exitCode"]==0 and g["filesDeleted"]==0 and not g.get("newSurvivingContainers") and not g.get("existingContainerUncertainty"),"guard result")
 need(subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()==REV and subprocess.check_output(["git","status","--porcelain=v1","-z"],cwd=root)==b"","producer checkout changed")
 result=dict(status="passed-independent-installed-watch-policy-review",reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewerDigest=sha(Path(__file__)),producerRevision=REV,sourceInventoryDigest=INVENTORY,sourceMembersMatchedGitArchiveAndInstallation=1255,identicalPreviouslyCompiledRustInputs=188,compilerDigest=BINARY,engine=engine,archives=archives,installedWatchDigest=WATCH,installedSourceWithoutGit=True,installedControlledCases=11,controlledMainUsesInstalledHelper=True,sourceInventoryUnchanged=True,oldPairPreserved=True,freshCompilerBuilt=False,appBuildsRun=0,reservationId=rid,reservationFinishedAndReleased=True,guardRecordDigest=sha(gp),privateReceiptDigest=sha(w/"receipt.json"),actualOwnerWatchAccepted=False,actualTwoHostReservationsAccepted=False,changedBuildWatchAccepted=False,performanceAccepted=False,completeDependencyClosureEstablished=False,parallelActivated=False,filesDeleted=0,policyChanged=False,goalComplete=False)
 a.output.write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
if __name__=="__main__":main()
