"""Audit watch policy controls and non-deleting idle-image closure; no workload execution."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,plistlib,re,subprocess
EXPECTED={
"scripts/project_watch.py":"sha256:69c476ee89507f08f54498d73cbad7306408658643215ea39fb721657dec676b",
"scripts/project_watch_controls.py":"sha256:d3434bc75164a0647f53d8912d826c89c747efc5ae46ec477def87055c87daf2",
"scripts/test_watch_policy_verification.py":"sha256:81b1d75e39ef924f2b0dcbbb4bbdd8356afff3000c97306d14771c037ae21794",
"scripts/project_watch_guard_controls.py":"sha256:714fcfeffd5e4ab9cc447d2dbd9e2c331f014dd2a0dedd827600d1be6c2f2e63"}
IMAGE_ID="46900e7c-98ac-4a8e-b945-56c7e7bd6095"
def need(v,m):
 if not v:raise RuntimeError(m)
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  while b:=f.read(1048576):h.update(b)
 return "sha256:"+h.hexdigest()
def absent(pid):
 x=subprocess.run(["/bin/ps","-p",str(pid),"-o","pid="],capture_output=True,text=True,timeout=5)
 return x.returncode==1 and not x.stdout.strip()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ["root","node","buildctl","docker","database","output"]:p.add_argument("--"+n,required=True)
 a=p.parse_args();root=Path(a.root);out=Path(a.output)
 need(not out.exists(),"output exists")
 w=root/".tools/watch-policy-verification-20261028";c=root/".tools/idle-workspace-review-20261028"
 need(sha(w/"run.py")=="sha256:692e2dd09dafe34c445b78c33cb491cbf14d9a78a24b1d48d78e637d8dfe0378","control runner changed")
 need(sha(c/"close_idle.py")=="sha256:d06624654486181e07450726002e12591da180aed6ce25fd8ffb8324d4da44e2","closure runner changed")
 for rel,digest in EXPECTED.items():need(sha(root/rel)==digest,"qualified source changed")
 frozen=read(w/"frozen.json")
 need({str(Path(x["path"]).relative_to(root)):x["digest"] for x in frozen["inputs"]}==EXPECTED,"frozen source differs")
 r=read(w/"receipt.json");cl=read(c/"receipt.json")
 need(read(w/"supervisor-exit.json")["exitCode"]==0 and r["status"]=="passed-watch-policy-controls","controls not passed")
 need(r["unitCases"]==11 and r["commands"][0]["exitCode"]==0 and r["sourceUnchanged"],"unit/source evidence")
 for stream in ["stdout","stderr"]:need(sha(w/("unit."+stream))==r["commands"][0][stream+"Digest"],"unit log changed")
 unit=(w/"unit.stderr").read_text();need("Ran 11 tests" in unit and unit.rstrip().endswith("OK"),"unit counts")
 need(r["guardian"]["result"]=="passed" and r["guardian"]["ordinarySurvivors"]==[] and r["guardian"]["guardianHasIndependentGroup"],"guardian control")
 for field in ["runner","innerGuard","tool","sleep"]:need(absent(r["guardian"][field]),"guardian process survived")
 need(r["guardExits"]["result"]=="passed" and len(r["guardExits"]["cases"])==5,"ordinary exits/permissions")
 need(all(x["result"] in ["passed","refused"] for x in r["guardExits"]["cases"]),"exit control failed")
 for directory,names in [(w,["launch.json","supervisor.json"]),(c,["launch.json","process.json"])]:
  for n in names:need(absent(read(directory/n)["pid"]),"stage owner present")
 status=json.loads(subprocess.check_output([a.node,a.buildctl,"status"],text=True,timeout=20))
 need(not status["parallelActivated"] and status["legacyLease"] is None and not status["transactionBlocked"],"scheduler uncertain")
 rid=re.search(r"Build reservation queued: ([0-9a-f-]{36});",(w/"supervisor.stderr").read_text()).group(1)
 req=next(x for x in status["requests"] if x["id"]==rid)
 need(req["state"]=="finished" and req["leaseReleaseCompleted"] and req["enforcement"]=="native-exclusive" and req["limits"]["diskBytes"]==4000000000,"reservation not released/changed")
 gp=Path(re.search(r"^Storage guard record: (.+)$",(w/"supervisor.stdout").read_text(),re.M).group(1));guard=read(gp)
 need(guard["exitCode"]==0 and guard["filesDeleted"]==0 and not guard.get("newSurvivingContainers") and not guard.get("existingContainerUncertainty"),"guard result")
 need(read(c/"exit.json")["exitCode"]==0 and cl["status"]=="passed-idle-owned-image-closure","closure not passed")
 need(cl["before"]==cl["after"] and cl["before"]["entries"]==201693 and cl["before"]["files"]==181172 and cl["before"]["treeDigest"]=="sha256:8742d17dd07ff1f66c8a416e6082e4d6e0bbe5d98eb56b8cdeb712b8fe886479","read-only comparison changed")
 need(cl["filesDeleted"]==cl["servicesStopped"]==0 and not cl["policyChanged"] and cl["readonlyComparisonPassed"] and cl["imageClosedAndPreserved"],"closure scope")
 need([x["label"] for x in cl["commands"]]==["initial-normal-detach","final-normal-detach"] and all(x["exitCode"]==0 for x in cl["commands"]),"detach status")
 image=root/".tools/buildctl"/IMAGE_ID/"workspace.dmg"
 s=image.stat();need([s.st_dev,s.st_ino,s.st_size]==cl["imageIdentityBefore"] and sha(image)==cl["imageDigestAfter"],"preserved image changed")
 images=plistlib.loads(subprocess.check_output(["/usr/bin/hdiutil","info","-plist"],timeout=30))["images"]
 need(not any(x.get("image-path")==str(image) for x in images),"image remounted")
 ids=subprocess.check_output([a.docker,"ps","-q"],text=True,timeout=20).split()
 need(ids==cl["runningContainersBefore"],"running containers changed")
 ready=subprocess.run([a.docker,"exec",a.database,"pg_isready"],capture_output=True,timeout=20)
 need(ready.returncode==0,"database not ready")
 ps=subprocess.check_output(["/bin/ps","-axo","pid=,args="],text=True,timeout=20).splitlines()
 need(not any(str(w/"fixtures") in l for l in ps),"controlled process survived")
 workflow=root/".github/workflows/native-capabilities.yml"
 syntax=subprocess.run(["/usr/bin/ruby","-ryaml","-e","d=YAML.load_file(ARGV[0]); abort unless d['jobs'].key?('watch-policy-verification')",str(workflow)],capture_output=True,timeout=20)
 need(syntax.returncode==0,"workflow syntax/job")
 result=dict(status="passed-independent-watch-policy-review",reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewerDigest=sha(Path(__file__)),producerRevision=frozen["producerRevision"],sourceBindings=EXPECTED,unitCases=11,controlledMainLoopRequiresTwoPolicyCalls=True,ordinaryGuardianControl=True,exitAndPermissionCases=5,reservationId=rid,reservationFinishedAndReleased=True,enforcement="native-exclusive",guardRecordDigest=sha(gp),privateControlsReceiptDigest=sha(w/"receipt.json"),idleClosure=dict(entriesCompared=201693,filesCompared=181172,treeDigest=cl["before"]["treeDigest"],imageClosedAndPreserved=True,imageDigestAfter=cl["imageDigestAfter"],databaseReady=True,filesDeleted=0,servicesStopped=0),workflowSyntaxChecked=True,workflowDigest=sha(workflow),linuxCiAccepted=False,realOwnerWatchAccepted=False,installedNewHelperAccepted=False,changedBuildWatchAccepted=False,performanceAccepted=False,parallelActivated=False,goalComplete=False,filesDeleted=0,policyChanged=False)
 out.write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
if __name__=="__main__":main()
