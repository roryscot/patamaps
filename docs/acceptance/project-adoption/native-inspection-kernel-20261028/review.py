"""Independent read-only review of the fixed single-process inspection probe."""
from pathlib import Path
import argparse, ast, hashlib, json, subprocess

EXPECTED = {
    "initialTcp4Denied", "initialTcp6Denied", "initialUnixDenied", "initialMachLookupDenied",
    "sessionLeader", "sessionCannotDetach", "canReadSelectedFixture", "ownedWriteAllowed",
    "outsideWriteDenied", "symlinkWriteDenied", "externalSignalDenied", "extraFdClosed",
    "stdinIsPipe", "forkDenied", "posixSpawnDenied", "afterExecTcp4Denied",
    "afterExecTcp6Denied", "afterExecUnixDenied", "afterExecMachLookupDenied", "execPreservedPid"
}
PROFILE_SHA = "b444e7406ca76f003a51959dd9953b47a275f81d98bcb2c2dcc3ea6a9fc11bb5"

def need(value, reason):
    if not value:
        raise RuntimeError(reason)
def read(path):
    return json.loads(path.read_text())
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    need(not a.output.exists(), "Output exists")
    base = a.root / ".tools/native-inspection-kernel-20261028"
    control, work = base / "control", base / "attempt-0"
    r = read(work / "receipt.json")
    need(read(control / "exit.json")["exitCode"] == 0 and
         r["status"] == "passed-native-inspection-kernel-qualification", "Qualification failed")
    payload = read(work / "payload.stdout")
    need(payload["status"] == "completed-kernel-probe" and
         payload["checks"] == r["checks"] and set(payload["checks"]) == EXPECTED and
         all(payload["checks"].values()) and r["checkCount"] == 20, "Controls incomplete")
    need((work / "payload.stderr").stat().st_size == 0, "Probe stderr changed")
    need(set(r["rootRefusals"]) == {"relative","whole-owner-root","alias","outside-owner-root"}
         and r["unsandboxedBaselinesPassed"] == ["tcp4","tcp6","unix","mach"], "Baselines/refusals missing")
    for label, name in [("helper","native_inspection.py"),("qualifier","qualify_native_inspection.py")]:
        source = a.root / "scripts" / name
        need(digest(source) == r["sourceHashesBefore"][label] ==
             digest(work / (label + ".executed.py")), "Working/executed source changed")
        ast.parse(source.read_text())
    helper = ast.parse((a.root / "scripts/native_inspection.py").read_text())
    profile = next(ast.literal_eval(n.value) for n in helper.body if isinstance(n,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id == "PROFILE" for t in n.targets))
    need(hashlib.sha256(profile.encode()).hexdigest() == r["profileSha256"] ==
         r["requestedProfile"]["profileSha256"] == PROFILE_SHA, "Profile changed")
    fixture = Path(r["retainedFixture"])
    need(fixture.parent == Path("/private/tmp") and fixture.name.startswith("patamaps-ni-")
         and fixture.resolve() == fixture and not fixture.is_symlink(), "Unexpected fixture")
    need((fixture / "supervisor/sentinel").read_bytes() == b"unchanged-fixture" and
         (fixture / "job/allowed-output").read_bytes() == b"owned-output" and
         r["supervisorSentinelUnchanged"] and r["unrelatedSignalHits"] == 0, "Fixture affected supervisor")
    s = (fixture / "job").stat()
    need([s.st_dev,s.st_ino] == r["requestedProfile"]["workspaceIdentity"], "Workspace replaced")
    need(r["requestedProfile"]["stdinTransport"] == "pipe" and
         r["requestedProfile"]["extraDescriptorsPassed"] is False, "Descriptor scope changed")
    processes = [read(control / "launch.json")["monitorPid"],
                 read(control / "process.json")["pid"],r["requestedProfile"]["pid"]]
    for pid in processes:
        x = subprocess.run(["/bin/ps","-p",str(pid),"-o","pid="],capture_output=True,text=True,timeout=5)
        need(x.returncode == 1 and not x.stdout.strip(), "Known test process still live")
    node = "/Users/admin/.nvm/versions/node/v22.23.3/bin/node"
    rid = "e7a0fc62-259c-4f0b-a020-207113921550"
    js = ('import {Scheduler,confirmedStopped} from "/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs";'
          'const s=new Scheduler();const r=s.requests().find(r=>r.id==='+json.dumps(rid)+');'
          'console.log(JSON.stringify({r,stopped:confirmedStopped(r),parallel:s.status().parallelActivated}));')
    actual = json.loads(subprocess.check_output([node,"--input-type=module","-e",js],text=True,timeout=30))
    need(actual["r"]["state"] == "finished" and actual["r"]["leaseReleaseCompleted"] is True and
         actual["stopped"] and actual["parallel"] is False, "Canonical reservation not released")
    need(r["automaticReservationReleaseQualified"] is False and r["supervisorPolicyChanged"] is False,
         "Prototype overclaims production integration")
    result = {
        "status":"passed-independent-native-inspection-kernel-review",
        "kind":r["kind"],"platform":r["platform"],"kernelControlsPassed":20,"rootRefusalsPassed":4,
        "unsandboxedEndpointBaselinesPassed":4,"execRetainedRestrictions":True,
        "forkAndSpawnDenied":True,"connectedStdinAndExtraDescriptorControlsPassed":True,
        "outsideWritesAndSignalsDenied":True,"ownedWriteAndReadPassed":True,
        "helperSha256":r["sourceHashesBefore"]["helper"],
        "qualifierSha256":r["sourceHashesBefore"]["qualifier"],"profileSha256":PROFILE_SHA,
        "reservationId":rid,"canonicalReservationFinishedAndReleased":True,
        "knownProcessesStopped":True,"filesDeleted":0,"servicesInterrupted":0,
        "installedSupervisorChanged":False,"parallelActivated":False,
        "usesDeprecatedSystemTool":True,"arbitraryBuildsSupported":False,
        "nativeCpuMemoryLimitsClaimed":False,"automaticReservationReleaseQualified":False,
        "fullAdoptionGoalComplete":False,"reviewerSha256":digest(Path(__file__))
    }
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__ == "__main__":
    main()
