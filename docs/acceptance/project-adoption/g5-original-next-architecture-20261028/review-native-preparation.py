"""Independent review of native Node selection preparation, not application acceptance."""
from pathlib import Path
import hashlib,json,subprocess,tarfile
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
BASE=ROOT/".tools/project-adoption/next-runtime-architecture-20261028/native-0"
OUT=ROOT/"docs/acceptance/project-adoption/g5-original-next-architecture-20261028"
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open("rb")as stream:return "sha256:"+hashlib.file_digest(stream,"sha256").hexdigest()
r=read(BASE/"receipt.json")
assert r["status"]=="passed-native-original-next-runtime-selection-preparation"
assert r["sourceRevision"]=="d59074841c06c607816c018e2f6d38ac4a7ad4d5"
assert r["driverDigest"]==sha(BASE/"prepare.py")=="sha256:301475242453f4581a1b27b666eb3f6593218a0274656f69762dd2cc57c99524"
assert read(BASE/"frozen-source.json")["sha256"]==r["driverDigest"].split(":")[1]
labels=["native-engine","x86_64-matching-target","aarch64-matching-target","x86_64-context-capture","x86_64-retained-selection","aarch64-context-capture","aarch64-retained-selection","selected-offline-replay"]
assert [c["label"]for c in r["commands"]]==labels
for c in r["commands"]:
 assert c["exitCode"]==c["expectedExitCode"]==(1 if c["label"]=="aarch64-retained-selection"else 0)
 assert sha(BASE/(c["label"]+".stdout"))==c["stdoutDigest"]
 assert sha(BASE/(c["label"]+".stderr"))==c["stderrDigest"]
expected=r["runtimeInputs"]["digests"]
assert expected["x86_64"]=="sha256:5796fd9700e83170bc7ddfdf7f18858c794a9f91cb39dd6f9e95060b292f2563"
assert expected["aarch64"]=="sha256:9189756f81aa0d5c706826f2a7763227a5abba0b5ca8c770096a25f35cf10e55"
assert sha(BASE/"node-v24.11.1-linux-arm64.tar.xz")=="sha256:6b0863fb9f627bf4a6c5948dce1de4398174a2e05dbe717503d828e211ca01f0"
with tarfile.open(BASE/"node-v24.11.1-linux-arm64.tar.xz","r|xz")as tar:
 count=0;total=0
 for m in tar:
  total+=m.size;assert total<=1024**3
  if m.name=="node-v24.11.1-linux-arm64/bin/node":
   count+=1;assert m.isfile()and m.size<=256*1024**2
   h=hashlib.file_digest(tar.extractfile(m),"sha256").hexdigest()
   assert "sha256:"+h==expected["aarch64"]
 assert count==1
for arch,target,machine in [("x86_64","linux/amd64",62),("aarch64","linux/arm64",183)]:
 assert sha(BASE/arch/"runtime")==expected[arch]
 match=read(BASE/(arch+"-matching-target.stdout"))
 assert match["status"]=="matched-elf-target-header"and match["target"]==target
 assert match["digest"]==expected[arch]and match["header"]["machine"]==machine
 assert match["executionPerformed"]is False and match["linuxOsEstablished"]is False
 assert match["runtimeCompatibility"]=="not-established"and match["authorization"]=="not-evaluated"
 plan=read(BASE/(arch+"-plan.json"));cmd=plan["verificationSteps"][0]["invocation"]
 assert cmd["executable"]==str(ROOT/"target/debug/patamaps")
 assert cmd["arguments"]==["elf-target-check","runtime","--target","linux/amd64","--digest",expected[arch]]
 assert plan["buildSteps"][0]["invocation"]["executable"]=="/usr/bin/true"
state=Path(r["selection"]["state"]);pointer=state/"selected.json"
assert sha(pointer)==r["selection"]["pointerDigest"]
selection=read(pointer);assert selection["attempt"]==r["selection"]["attempt"]
candidate=state/selection["attempt"]/"candidate/runtime"
assert sha(candidate)==expected["x86_64"]==r["selection"]["runtimeDigest"]
negative=read(BASE/"aarch64-retained-selection.stdout")
assert negative["status"]=="refused-project-build"and negative["previousSelectionPreserved"]is True
vr=read(state/negative["attempt"]/"verify-001.json")
assert vr["exitCode"]==2 and"ELF_ARCHITECTURE"in vr["stderr"]["text"]
assert r["authenticArmRefusal"]["correctDigestSupplied"]==expected["aarch64"]and r["authenticArmRefusal"]["armExecuted"]is False
assert not(BASE/"owner").exists()and(BASE/"owner.retained-offline").is_dir()
assert not(BASE/"context-x86_64").exists()and(BASE/"context-x86_64.retained-offline").is_dir()
assert read(BASE/"selected-offline-replay.stdout")["status"]=="verified-selected-build-bindings"
original=ROOT/".tools/buildctl/a96986e9-673c-4940-8d68-71e08ed53e85/mount/work"
assert sha(original/"node")==expected["x86_64"]
assert sha(original/"expected.json")=="sha256:b08b5a281185568cc48a14a533339ad49a7656bf433c060a098245ad03a88577"
assert sha(ROOT/"target/debug/patamaps")==r["nativeCompiler"]["digest"]
inventory=read(ROOT/"docs/acceptance/project-adoption/g5-retained-dynamic-next-20261028/attempt-40770841087/source-inventory.json")
inputs=[i for i in inventory if i["path"].startswith(("crates/","vendor/"))or i["path"]in ["Cargo.toml","Cargo.lock","rust-toolchain.toml"]]
for item in inputs:assert sha(ROOT/item["path"])==item["digest"],item["path"]
control=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds")
guard=control/"runs/c4493fc2-dfa4-4921-841a-b99a7a1fc6f3/run.json"
g=read(guard);assert g["completed"]is True and g["exitCode"]==0 and g["filesDeleted"]==0
request=read(control/"scheduler/requests/3be56cb9-b7d3-4d4c-b726-642b1e31f39d.json")
assert request["state"]=="finished"and request["leaseReleaseCompleted"]is True
summary=dict(status="passed-independent-native-next-runtime-selection-preparation",sourceRevision=r["sourceRevision"],driverDigest=r["driverDigest"],nativeCompiler=r["nativeCompiler"],relevantRustBuildInputsMatchedB615=len(inputs),commands=8,expectedProjectBuildRefusalExitCode=1,authenticArmVerifierExitCode=2,authenticArmDiagnostic="ELF_ARCHITECTURE",runtimeVersion="24.11.1",runtimeDigests=expected,armArchiveDigest=r["runtimeInputs"]["armArchiveDigest"],armMember=r["runtimeInputs"]["armMember"],armMemberIndependentlyRehashed=True,correctArmDigestSupplied=True,wrongArchitectureRuntimeExecuted=False,selectedPointerDigest=r["selection"]["pointerDigest"],selectedX64RuntimeIndependentlyRehashed=True,nodeProducerAndSnapshotUnavailableReplay=True,originalNodeAndExpectedManifestUnchanged=True,originalFullAppInventoryRechecked=False,nativeCompilerUnchanged=True,reservationId=request["id"],reservationReleased=True,guardRunId=guard.parent.name,guardRecordDigest=sha(guard),filesDeleted=0,managedPreparationRun=False,managedApplicationRun=False,architectureApplicationGateAccepted=False,staleContractAccepted=False,fullGoalComplete=False,scope="Original Next runtime's authentic Node selection/refusal and offline-binding preparation only. Existing application startup and complete architecture gate remain unrun.")
summary["reviewerDigest"]=sha(Path(__file__))
write=OUT/"native-preparation.json";assert not write.exists();write.write_text(json.dumps(summary,indent=2)+"\n")
(OUT/"review-native-preparation.py").write_bytes(Path(__file__).read_bytes())
(OUT/"prepare-native.py").write_bytes((BASE/"prepare.py").read_bytes())
print(json.dumps(summary,indent=2))
