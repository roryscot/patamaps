"""Review interrupted native subcase; never promote partial controls to acceptance."""
import hashlib,io,json,subprocess,zipfile
from pathlib import Path
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
GH=ROOT/".tools/intel-gh-2.102.0-20261015/unpacked/gh_2.102.0_macOS_amd64/bin/gh"
BASE=ROOT/"docs/acceptance/project-adoption/g5-retained-dynamic-next-20261028/attempt-40770841087"
def api(endpoint,binary=False):
 b=subprocess.check_output([str(GH),"api","repos/roryscot/patamaps/"+endpoint],timeout=120,stderr=subprocess.PIPE)
 return b if binary else json.loads(b)
m=api("actions/artifacts/12851904399")
assert m["workflow_run"]["id"]==40770841087 and m["workflow_run"]["head_sha"]=="b6157b8a2e7a6cb5c9e01fb70d87ca6d4cdd29bc"
raw=api("actions/artifacts/12851904399/zip",True)
assert len(raw)==m["size_in_bytes"]==22053286
assert "sha256:"+hashlib.sha256(raw).hexdigest()==m["digest"]=="sha256:eecf2a8d57cc0361f427129ddce98006a9d6190b50b68810ec7dab43486589ce"
z=zipfile.ZipFile(io.BytesIO(raw))
assert len(z.infolist())<5000 and sum(i.file_size for i in z.infolist())<320*1024**2
assert len({i.filename for i in z.infolist()})==len(z.infolist())
def data(name):return json.loads(z.read(name))
parent=data("receipt.json");receipt=data("native/receipt.json")
runtime=data("native/runtime.json");browser=data("native/browser-auth.json");owned=data("native/retained-owned.json")
assert parent["status"]=="failed" and parent["error"]=="AssertionError: Combined installed Next qualification storage boundary"
assert receipt["status"]=="running" and runtime["status"]=="preparing" and browser["status"]=="failed"
assert len(browser["controls"])==31 and all(c["passed"] is True for c in browser["controls"])
assert browser["ownedBrowserStopped"] is True and browser["ownedHttpsProxyStopped"] is True
assert len(owned["containers"])==2 and {c["role"] for c in owned["containers"]}=={"probe","app"} and all(c["confirmedStopped"] is True for c in owned["containers"])
actual=runtime["retainedRuntime"]
assert actual["phase"]=="source-tool-unavailable-start"
assert actual["kernelLimits"]==dict(cpu="100000 100000",memory="3221225472",swap="0",pids="128")
for k in ["imageBytesModesAndLinkTargetsVerified","readonlyWriteRefused","cacheWritePassed","cacheQuotaFailurePassed","producerSourceAndToolsUnavailable"]:assert actual[k] is True
assert all(c["exitCode"]==c["expectedExitCode"] for c in receipt["commands"])
v=dict(status="verified-interrupted-native-subcontrols-only",runId=40770841087,sourceRevision=m["workflow_run"]["head_sha"],artifactDigest=m["digest"],artifactDigestVerified=True,parentFailure=parent["error"],storageObservation=parent["storageObservation"],nativeReceiptStatus=receipt["status"],nativeRuntimeStatus=runtime["status"],browserStatus=browser["status"],successfulBrowserGroupsObserved=31,requiredBrowserGroups=41,ownedBrowserStopped=True,ownedHttpsProxyStopped=True,ownedAppAndProbeContainersStopped=True,imageComparison="recorded inside CI; not independently rehashed from public artifact",kernelLimits=actual["kernelLimits"],actualQuotaFailureObserved=True,nativeCaseAccepted=False,pairAccepted=False,wholeJobPeakClaimed=False,rawArchiveRetained=False,inputDigests={n:"sha256:"+hashlib.sha256(z.read(n)).hexdigest() for n in ["receipt.json","native/receipt.json","native/runtime.json","native/browser-auth.json","native/retained-owned.json"]})
bootstrap=receipt["publicPnpmBootstrap"]
assert bootstrap["reused"]is True and "unchangedAfterOwner"not in bootstrap
assert bootstrap["identity"]==parent["sharedPublicPnpmBootstrap"]
assert not any(c["label"]=="pnpm-install-tool"for c in receipt["commands"])
v.update(publicPnpmBootstrapActuallyReused=True,publicBootstrapNativePostcheckCompleted=False,resourceObservationCensoredAtStop=True,runtimeRepairBudgetExhausted=True)
import struct,tarfile
meta=data("package/distribution.json");archive=z.read("package/"+meta["nativeArchive"]["path"])
assert "sha256:"+hashlib.sha256(archive).hexdigest()==meta["nativeArchive"]["digest"]
with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz")as tar:
 entries=[m for m in tar.getmembers()if m.name.endswith("/bin/patamaps")];assert len(entries)==1
 binary=tar.extractfile(entries[0]).read()
assert "sha256:"+hashlib.sha256(binary).hexdigest()==meta["binaryDigest"]
h=struct.unpack_from("<16sHHIQQQIHHHHHH",binary)
assert h[0][:6]==b"\x7fELF\x02\x01"and h[2]==62 and h[8]==64 and h[11]==64
assert 0<h[12]<4096 and 0<h[13]<h[12]and h[6]+h[11]*h[12]<=len(binary)
sections=[struct.unpack_from("<IIQQQQIIQQ",binary,h[6]+i*h[11])for i in range(h[12])]
names=sections[h[13]];assert names[4]+names[5]<=len(binary);strings=binary[names[4]:names[4]+names[5]]
symbols=[]
for row in sections:
 assert row[0]<len(strings);end=strings.find(b"\0",row[0]);assert end>=row[0]
 name=strings[row[0]:end].decode("ascii")
 if name in [".symtab",".strtab"]:
  assert row[1]in [2,3]and row[2]&2==0 and row[4]+row[5]<=len(binary)
  symbols.append(dict(name=name,type=row[1],flags=row[2],bytes=row[5]))
assert {s["name"]for s in symbols}=={".symtab",".strtab"}
v["readOnlyPublicBinaryInspection"]=dict(binaryDigest=meta["binaryDigest"],binaryBytes=len(binary),nonAllocatedSymbolSections=symbols,symbolSectionContentBytes=sum(s["bytes"]for s in symbols),strippedBuildPerformed=False,storageSavingsEstablished=False,runtimeOrSemanticEquivalenceEstablished=False,specifications=["https://gabi.xinuos.com/elf/02-eheader.html","https://gabi.xinuos.com/elf/03-sheader.html"],cargoStripDocumentation="https://doc.rust-lang.org/cargo/reference/profiles.html#strip",note="Existing artifact inspected in memory only. Section bytes are observed, not verified stripped-binary or completed-workload savings.")
p=BASE/"native-interruption-review.json"
assert not p.exists()
p.write_text(json.dumps(v,indent=2)+"\n")
(BASE/"review-native-interruption.py").write_bytes(Path(__file__).read_bytes())
print(json.dumps(v,indent=2))
