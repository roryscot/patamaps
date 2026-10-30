"""Read-only review of existing Native CLI compatibility under inspection isolation."""
from pathlib import Path
import argparse, hashlib, json, subprocess

def need(v,r):
    if not v:
        raise RuntimeError(r)
def read(p):
    return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        while b:=f.read(1048576):
            h.update(b)
    return "sha256:"+h.hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    need(not a.output.exists(),"Output exists")
    root=a.root
    w=root/".tools/native-inspection-kernel-20261028/core-compatibility"
    r=read(w/"receipt.json")
    need(read(w/"exit.json")["exitCode"]==0 and
         r["status"]=="passed-readonly-native-inspection-compatibility","Compatibility failed")
    need(sha(w/"run.py")==r["coordinatorDigest"],"Coordinator changed")
    need(sha(root/"scripts/native_inspection.py")==r["helperDigest"]==
         "sha256:9e623779667f97fd53e6c84de7cade52ee9cc08aadae69b5997cfb3f6422447e","Helper changed")
    need(r["profileDigest"]=="sha256:b444e7406ca76f003a51959dd9953b47a275f81d98bcb2c2dcc3ea6a9fc11bb5",
         "Profile changed")
    package=read(root/".tools/installed-watch-policy-20261028/receipt.json")
    cli=Path(package["installedNative"])/"bin/patamaps"
    need(sha(cli)==r["nativeCliDigest"]==
         "sha256:cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355","CLI changed")
    need(sha(Path("/usr/bin/sandbox-exec"))==r["sandboxExecutableDigest"],"System tool changed")
    expected=["engine","input-key","verify-selected"]
    need([c["role"] for c in r["commands"]]==expected and r["nativeCommandsPassed"]==3,
         "Missing native command")
    fixture=Path(r["retainedFixture"])
    need(fixture.parent==Path("/private/tmp") and fixture.name.startswith("patamaps-ni-core-")
         and fixture.resolve()==fixture,"Unexpected writable fixture")
    payloads=[]
    for command in r["commands"]:
        role=command["role"]
        need(command["exitCode"]==0 and command["stopped"] and command["stderrBytes"]==0,
             "Native command failed")
        need(sha(w/(role+".stdout"))==command["stdoutDigest"] and
             sha(w/(role+".stderr"))==command["stderrDigest"],"Native output changed")
        process=read(w/(role+".process.json"))
        need(process["pid"]==command["pid"] and
             process["requestedProfile"]["profileSha256"]==r["profileDigest"][7:] and
             process["requestedProfile"]["stdinTransport"]=="pipe" and
             process["requestedProfile"]["extraDescriptorsPassed"] is False,
             "Profile/descriptor binding changed")
        info=(fixture/"job").stat()
        need(process["requestedProfile"]["workspaceIdentity"]==[info.st_dev,info.st_ino],
             "Writable root replaced")
        payloads.append(command["pid"])
    need(read(w/"engine.stdout")==package["engine"],"Engine identity mismatch")
    observed=read(w/"input-key.stdout")
    need(observed["status"]=="observed-project-build-inputs" and
         observed["commandsExecuted"] is False and
         observed["inputKey"]==r["originalSelectedInputKey"],"Input key changed")
    verified=read(w/"verify-selected.stdout")
    need(verified["status"]=="verified-selected-build-bindings" and
         verified["inputKey"]==r["originalSelectedInputKey"],"Native bindings refused")
    need(r["originalAttempts"]==["1793122875791456000-6699"] and
         r["newApplicationAttempts"]==0,"Unexpected application build attempt")
    need(len(r["statePreimages"])==3,"Missing state preimages")
    for name,digest in r["statePreimages"].items():
        path=Path(name)
        need(not path.is_relative_to(fixture/"job") and sha(path)==digest,
             "Protected state mutated or was writable")
    state=Path(read(root/".tools/installed-original-owner-next-20261027/owner-native/receipt.json")["state"])
    need(sorted(p.name for p in (state/"attempts").iterdir())==r["originalAttempts"],"Attempt count changed")
    known=[read(w/"launch.json")["monitorPid"],read(w/"process.json")["pid"],*payloads]
    for pid in known:
        result=subprocess.run(["/bin/ps","-p",str(pid),"-o","pid="],capture_output=True,text=True,timeout=5)
        need(result.returncode==1 and not result.stdout.strip(),"Known process survived")
    rid="1bf814a3-131b-439e-8b95-9861313c139b"
    js=('import {Scheduler,confirmedStopped} from "/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs";'
        'const s=new Scheduler();const r=s.requests().find(r=>r.id==='+json.dumps(rid)+');'
        'console.log(JSON.stringify({r,stopped:confirmedStopped(r),parallel:s.status().parallelActivated}));')
    actual=json.loads(subprocess.check_output(
        ["/Users/admin/.nvm/versions/node/v22.23.3/bin/node","--input-type=module","-e",js],text=True,timeout=30))
    need(actual["r"]["state"]=="finished" and actual["r"]["leaseReleaseCompleted"] and
         actual["stopped"] and actual["parallel"] is False,"Reservation cleanup incomplete")
    result=dict(status="passed-independent-readonly-native-inspection-review",
        nativeCommandsPassed=3,engineIdentityMatched=True,originalInputKeyMatched=True,
        nativeSelectedBindingsVerified=True,protectedStateOutsideWritableRoot=True,
        selectionArtifactManifestAndLedgerUnchanged=True,newApplicationAttempts=0,
        nativeCliDigest=r["nativeCliDigest"],helperDigest=r["helperDigest"],
        profileDigest=r["profileDigest"],sandboxExecutableDigest=r["sandboxExecutableDigest"],
        coordinatorDigest=r["coordinatorDigest"],knownNativePayloadsStopped=3,
        canonicalReservationFinishedAndReleased=True,reservationId=rid,
        actualOwnerWatchRetried=False,installedSupervisorChanged=False,
        automaticReservationReleaseQualified=False,fullAdoptionGoalComplete=False,
        filesDeleted=0,servicesInterrupted=0,reviewerDigest=sha(Path(__file__)))
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":
    main()
