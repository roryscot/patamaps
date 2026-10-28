"""Review interrupted native subcase; never promote partial controls to acceptance."""
import hashlib,io,json,subprocess,zipfile
from pathlib import Path
ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
GH=ROOT/".tools/intel-gh-2.102.0-20261015/unpacked/gh_2.102.0_macOS_amd64/bin/gh"
BASE=ROOT/"docs/acceptance/project-adoption/g5-retained-dynamic-next-20261028/attempt-40764583126"
def api(endpoint,binary=False):
 b=subprocess.check_output([str(GH),"api","repos/roryscot/patamaps/"+endpoint],timeout=120,stderr=subprocess.PIPE)
 return b if binary else json.loads(b)
m=api("actions/artifacts/12850552155")
assert m["workflow_run"]["id"]==40764583126 and m["workflow_run"]["head_sha"]=="49545b1b352d58680f66c40ae632b9006c639c1f"
raw=api("actions/artifacts/12850552155/zip",True)
assert len(raw)==m["size_in_bytes"]==22062303
assert "sha256:"+hashlib.sha256(raw).hexdigest()==m["digest"]=="sha256:96d537b845d91ee815abed99ebc7eeb608765fa820fcacc687587caf67f0f793"
z=zipfile.ZipFile(io.BytesIO(raw))
assert len(z.infolist())<5000 and sum(i.file_size for i in z.infolist())<320*1024**2
assert len({i.filename for i in z.infolist()})==len(z.infolist())
def data(name):return json.loads(z.read(name))
parent=data("receipt.json");receipt=data("native/receipt.json")
runtime=data("native/runtime.json");browser=data("native/browser-auth.json");owned=data("native/retained-owned.json")
assert parent["status"]=="failed" and parent["error"]=="AssertionError: Combined installed Next qualification storage boundary"
assert receipt["status"]=="running" and runtime["status"]=="preparing" and browser["status"]=="failed"
assert len(browser["controls"])==27 and all(c["passed"] is True for c in browser["controls"])
assert browser["ownedBrowserStopped"] is True and browser["ownedHttpsProxyStopped"] is True
assert len(owned["containers"])==2 and {c["role"] for c in owned["containers"]}=={"probe","app"} and all(c["confirmedStopped"] is True for c in owned["containers"])
actual=runtime["retainedRuntime"]
assert actual["phase"]=="source-tool-unavailable-start"
assert actual["kernelLimits"]==dict(cpu="100000 100000",memory="3221225472",swap="0",pids="128")
for k in ["imageBytesModesAndLinkTargetsVerified","readonlyWriteRefused","cacheWritePassed","cacheQuotaFailurePassed","producerSourceAndToolsUnavailable"]:assert actual[k] is True
assert all(c["exitCode"]==c["expectedExitCode"] for c in receipt["commands"])
v=dict(status="verified-interrupted-native-subcontrols-only",runId=40764583126,sourceRevision=m["workflow_run"]["head_sha"],artifactDigest=m["digest"],artifactDigestVerified=True,parentFailure=parent["error"],storageObservation=parent["storageObservation"],nativeReceiptStatus=receipt["status"],nativeRuntimeStatus=runtime["status"],browserStatus=browser["status"],successfulBrowserGroupsObserved=27,requiredBrowserGroups=41,ownedBrowserStopped=True,ownedHttpsProxyStopped=True,ownedAppAndProbeContainersStopped=True,imageComparison="recorded inside CI; not independently rehashed from public artifact",kernelLimits=actual["kernelLimits"],actualQuotaFailureObserved=True,nativeCaseAccepted=False,pairAccepted=False,wholeJobPeakClaimed=False,rawArchiveRetained=False,inputDigests={n:"sha256:"+hashlib.sha256(z.read(n)).hexdigest() for n in ["receipt.json","native/receipt.json","native/runtime.json","native/browser-auth.json","native/retained-owned.json"]})
p=BASE/"native-interruption-review.json"
assert not p.exists()
p.write_text(json.dumps(v,indent=2)+"\n")
(BASE/"review-native-interruption.py").write_bytes(Path(__file__).read_bytes())
print(json.dumps(v,indent=2))
