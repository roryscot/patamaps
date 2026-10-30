"""Independent bounded installed-package and real Next artifact review; no extraction."""
from pathlib import Path,PurePosixPath
import base64,datetime,hashlib,io,json,re,subprocess,sys,tarfile,zipfile

ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
GH=ROOT/".tools/intel-gh-2.102.0-20261015/unpacked/gh_2.102.0_macOS_amd64/bin/gh"
RUN=40764583126
REVISION="49545b1b352d58680f66c40ae632b9006c639c1f"
BASE=ROOT/"docs/acceptance/project-adoption/g5-retained-dynamic-next-20261028"
MAX=320*1024**2
def digest(raw):return "sha256:"+hashlib.sha256(raw).hexdigest()
def api(path,binary=False):
 raw=subprocess.check_output([str(GH),"api","repos/roryscot/patamaps/"+path],cwd=ROOT,timeout=120,stderr=subprocess.PIPE)
 return raw if binary else json.loads(raw)
def git_bytes(name):return subprocess.check_output(["git","show",REVISION+":"+name],cwd=ROOT,timeout=30,stderr=subprocess.PIPE)
def members(raw):
 seen=set();total=0
 with tarfile.open(fileobj=io.BytesIO(raw),mode="r|gz") as tar:
  for member in tar:
   path=PurePosixPath(member.name);name=path.as_posix().rstrip("/")
   assert not path.is_absolute() and ".." not in path.parts and name not in seen and len(seen)<20000
   assert (member.isfile() or member.isdir()) and not member.mode&0o7000
   seen.add(name)
   if member.isdir():continue
   total+=member.size;assert member.size<=128*1024**2 and total<=MAX
   body=tar.extractfile(member).read();assert len(body)==member.size
   yield name,body,member.mode

run=api("actions/runs/"+str(RUN))
assert run["status"]=="completed" and run["conclusion"]=="failure" and run["head_sha"]==REVISION
jobs=api("actions/runs/"+str(RUN)+"/jobs")["jobs"]
selected=[j for j in jobs if "Pinned retained Chatbot dynamic page and data replay" in j["name"]]
assert len(selected)==1 and selected[0]["conclusion"]=="failure"
assert [s["name"] for s in selected[0]["steps"] if s["conclusion"]=="failure"]==["Qualify fresh source and native installations on real Next"]
artifacts=api("actions/runs/"+str(RUN)+"/artifacts")["artifacts"];assert len(artifacts)==1
meta=api("actions/artifacts/"+str(artifacts[0]["id"]))
assert meta["name"]=="installed-retained-dynamic-next-"+REVISION and meta["workflow_run"]["head_sha"]==REVISION and meta["workflow_run"]["id"]==RUN
assert not meta["expired"] and meta["size_in_bytes"]<=MAX
raw=api("actions/artifacts/"+str(meta["id"])+"/zip",True)
assert len(raw)==meta["size_in_bytes"] and digest(raw)==meta["digest"]
z=zipfile.ZipFile(io.BytesIO(raw));infos=z.infolist()
assert len(infos)<5000 and sum(i.file_size for i in infos)<=MAX and len({i.filename for i in infos})==len(infos)
for info in infos:
 p=PurePosixPath(info.filename)
 assert not p.is_absolute() and ".." not in p.parts and not info.flag_bits&1 and info.file_size<=MAX
def read(name):return z.read(name)
def data(name):return json.loads(read(name))
parent=data("receipt.json");dist=data("package/distribution.json")
assert parent["status"]=="failed" and parent["error"]=="AssertionError: Combined installed Next qualification storage boundary" and parent["sourceRevision"]==REVISION
assert set(parent["cases"])=={"source"}
for key in ["sourceCompilerBuiltFromInstalledSource","sharedCargoDependencyArtifacts","checkoutCompilerUnavailableBeforeFreshSourceBuild"]:
 assert parent[key] is True,key
for key in ["productionActivation","registryPublication","completeDependencyClosure","fullRetainedNextBundleAccepted","performanceAccepted"]:
 assert parent[key] is False,key
assert parent["filesDeleted"]==0 and parent["maximumQualificationGrowthBytes"]==4000000000
assert parent["storageObservation"]["peakGrowthBytes"]==4001755136
assert all(c["exitCode"]==c["expectedExitCode"] for c in parent["commands"])
assert dist["target"]=="x86_64-unknown-linux-gnu" and dist["buildProfile"]=="development"
source_files={};inventory=None;native_binary=None;source_prefix=None
for kind in ["sourceArchive","nativeArchive"]:
 entry=dist[kind];assert PurePosixPath(entry["path"]).name==entry["path"]
 archive=read("package/"+entry["path"]);assert digest(archive)==entry["digest"]
 for name,body,mode in members(archive):
  parts=PurePosixPath(name).parts;assert len(parts)>1
  relative="/".join(parts[1:])
  if kind=="sourceArchive":
   if source_prefix is None:source_prefix=parts[0]
   assert parts[0]==source_prefix and mode==0o644
   if relative=="source-inventory.json":
    inventory=json.loads(body);assert digest(body)==dist["sourceInventoryDigest"]
   else:source_files[relative]=dict(digest=digest(body),bytes=len(body))
  elif relative=="bin/patamaps":
   assert mode==0o755 and body[:6]==b"\x7fELF\x02\x01" and int.from_bytes(body[18:20],"little")==62
   native_binary=digest(body)
assert native_binary==dist["binaryDigest"]
expected_identity=data("source/receipt.json")["installedSourceIdentity"]
assert expected_identity["sourceInventoryDigest"]==dist["sourceInventoryDigest"] and expected_identity["sourceIsInstalled"] is True
assert inventory and len(source_files)==len(inventory)==expected_identity["sourceFiles"]
assert set(source_files)=={i["path"] for i in inventory}
for item in inventory:assert source_files[item["path"]]==dict(digest=item["digest"],bytes=item["bytes"])
names=sorted(source_files)
output=subprocess.run(["git","cat-file","--batch"],input="".join(REVISION+":"+name+"\n" for name in names).encode(),
                      cwd=ROOT,capture_output=True,timeout=120)
assert output.returncode==0
stream=io.BytesIO(output.stdout)
for name in names:
 header=stream.readline().split();assert len(header)==3 and header[1]==b"blob"
 size=int(header[2]);assert size<=128*1024**2
 body=stream.read(size);assert stream.read(1)==b"\n" and len(body)==size
 assert source_files[name]==dict(digest=digest(body),bytes=size),name
assert stream.read()==b""
sys.path.insert(0,str(ROOT/"scripts/parity"))
from identity import identities
expected_engine=dict(schemaVersion="0.1.0",documentType="executor-description",**identities(ROOT))
assert dist["engines"]==expected_engine
compile_log=read("logs/fresh-source-cargo-install.stderr").decode()
for package in ["patamaps-cli","patamaps-workspace"]:
 lines=[line for line in compile_log.splitlines() if "Compiling "+package+" v" in line]
 assert any(("/source-installation/"+source_prefix+"/crates/"+package+")") in line for line in lines),package
assert parent["freshSourcePackagesConfirmed"]==["patamaps-cli","patamaps-workspace"]
assert "logs/changed-installed-source-before-compiler.stderr" not in z.namelist()
assert data("logs/package-engine.stdout")==expected_engine

def review_source():
 def read(name):return z.read("source/"+name)
 def data(name):return json.loads(read(name))
 receipt=data("receipt.json");runtime=data("runtime.json");browser=data("browser-auth.json")
 probe=data("standalone-probe.json");owned=data("retained-owned.json")
 overlay=data("rewrite-overlay.json");derived=data("derived-source.json");original=data("selected-source.json")
 bindings=data("dynamic-build-bindings.json");observed=data("native-observations.json")
 assert receipt["status"]=="passed-pinned-chatbot-source-build-auth" and runtime["status"]==browser["status"]=="passed"
 assert receipt["installedSourceIdentity"]==expected_identity and receipt["installedSourceInventoryUnchanged"]
 assert receipt["sourceRevision"] is None and receipt["upstreamCommit"]=="c2f8235e1f3ea903ad8b7f61447c4f74164b5c58" and receipt["frameworkVersion"]=="16.2.10"
 assert all(c["exitCode"]==c["expectedExitCode"]for c in receipt["commands"])
 assert receipt["retainedDynamicProfile"]==runtime["retainedDynamicProfile"]=="patamaps-pinned-retained-dynamic-next-1"
 sys.path.insert(0,str(ROOT/"scripts"))
 from qualify_installed_next import retained_dynamic_case_result
 accepted_flags=retained_dynamic_case_result(receipt,runtime,browser,probe,owned)
 assert accepted_flags["retainedDynamicProfileAccepted"] and not accepted_flags["originalOwnerConfigurationPreserved"]
 assert receipt["filesDeleted"]==0 and receipt["productionActivation"]is False and receipt["applicationAcceptance"]is False
 assert receipt["compiler"]["engine"]==expected_engine and receipt["compiler"]["sha256"]==native_binary
 assert parent["cases"]["source"]["compilerDigest"]==native_binary and parent["cases"]["source"]["runtimeGroupsPassed"]==41
 assert receipt["dynamicRouteQualification"]["nativeObservationDigest"]==bindings["nativeObservationDigest"]==digest(read("native-observations.json"))
 assert receipt["dynamicRouteQualification"]["derivedSourceContextDigest"]==receipt["rewriteQualification"]["derivedSourceContextDigest"]
 assert receipt["rewriteQualification"]["originalRulesPreserved"]==4
 tree=json.loads(git_bytes("docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024/accepted-40125656603/upstream-tree.json"))
 assert not tree["truncated"]
 upstream={e["path"]:e for e in tree["tree"]if e["type"]=="blob"and e["path"]!=".env.example"}
 u={e["path"]:e for e in original};d={e["path"]:e for e in derived}
 assert len(u)==len(upstream)==receipt["sourceFiles"]==180 and set(u)==set(upstream)
 assert len(d)==181 and set(d)==set(u)|{"patamaps-rewrite-profile.json"}
 assert all(d[n]==row for n,row in u.items()if n!="next.config.ts")
 capture=data("logs/text-source-capture.stdout");assert capture["digest"]==receipt["textSourceDigest"]
 texts={e["receipt"]["path"]:e for e in capture["inputs"]}
 assert len(texts)==len(capture["inputs"])==receipt["sourceTextFiles"]==175
 for name,row in texts.items():
  body=row["content"].encode();assert digest(body)==row["receipt"]["digest"]==d[name]["digest"]and len(body)==row["receipt"]["byteLength"]
 for name,row in u.items():
  entry=upstream[name];assert row["gitBlob"]==entry["sha"]and row["mode"]==entry["mode"]and row["bytes"]==entry["size"]
  if name in texts and name!="next.config.ts":body=texts[name]["content"].encode()
  else:
   blob=json.loads(subprocess.check_output([str(GH),"api","repos/vercel/chatbot/git/blobs/"+row["gitBlob"]],cwd=ROOT,timeout=60,stderr=subprocess.PIPE))
   assert blob["encoding"]=="base64"and blob["sha"]==row["gitBlob"]
   body=base64.b64decode("".join(blob["content"].split()),validate=True)
  assert digest(body)==row["digest"]and len(body)==row["bytes"]and hashlib.sha1(b"blob "+str(len(body)).encode()+b"\0"+body).hexdigest()==row["gitBlob"]
 intake=json.loads(git_bytes("docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024/intake.json"))
 assert receipt["dynamicSourceBindings"]["gitBlobs"]==intake["publicGitBlobs"] and receipt["dynamicSourceBindings"]["sourceMutated"]is False
 assert bindings["ownerSourceBindings"]==receipt["dynamicSourceBindings"]
 for name,blob in intake["publicGitBlobs"].items():
  body=texts[name]["content"].encode();assert hashlib.sha1(b"blob "+str(len(body)).encode()+b"\0"+body).hexdigest()==blob
 profile=overlay["profile"];assert profile["profile"]=="patamaps-chatbot-standalone-proxy-3"
 assert overlay["originalConfigDigest"]==u["next.config.ts"]["digest"] and overlay["derivedConfigDigest"]==d["next.config.ts"]["digest"]!=overlay["originalConfigDigest"]
 assert digest(texts["patamaps-rewrite-profile.json"]["content"].encode())==overlay["profileDigest"]and json.loads(texts["patamaps-rewrite-profile.json"]["content"])==profile
 assert profile["canonicalOwnerOrigin"]==runtime["canonicalRewriteOwnerOrigin"]=="http://127.0.0.1:"+str(profile["canonicalOwnerPort"])
 request=data("logs/native-compiled-next-observations.input")
 assert observed["requestDigest"]==request["requestDigest"]==data("logs/manifest-request-digest.stdout")
 inputs={e["receipt"]["path"]:e for e in request["inputs"]};assert set(inputs)=={"config.json","routes.json","app-paths.json","app-routes.json"}
 for entry in inputs.values():
  body=entry["content"].encode();assert digest(body)==entry["receipt"]["digest"]and len(body)==entry["receipt"]["byteLength"]
 projection=json.loads(inputs["config.json"]["content"]);assert projection["configuration"]["output"]=="standalone"and projection["frameworkVersion"]=="16.2.10"
 assert projection["buildReceiptDigest"]==digest(read("logs/owner-production-build.stdout"))
 for field,name in [("routesDigest","routes.json"),("appPathsDigest","app-paths.json"),("appPathRoutesDigest","app-routes.json")]:assert projection[field]==inputs[name]["receipt"]["digest"]
 from chatbot_dynamic_profile import verify_compiled
 expected=verify_compiled(observed);assert expected["bindings"]==bindings["bindings"]and len(expected["bindings"])==3
 from chatbot_rewrite_profile import verify_compiled as verify_rules
 baseline=json.loads(git_bytes("docs/acceptance/project-adoption/g3-chatbot-source-20261023/native-observations.json"))
 rules=verify_rules(json.loads(inputs["routes.json"]["content"]),observed,baseline,profile=profile)
 assert rules["originalRulesPreserved"]==4 and rules["addedRules"]==2 and data("rewrite-compiled.json")["rules"]==rules["rules"]
 base=set(c["name"]for c in json.loads(git_bytes("docs/acceptance/project-adoption/g3-chatbot-production-auth-20261023/browser-auth.json"))["controls"])
 rewrites={"rewrite-login-url-preserved","rewrite-register-url-preserved","rewrite-missing-header-refused","rewrite-wrong-header-refused","rewrite-blocked-query-refused","rewrite-prefix-refused","rewrite-extra-segment-refused","rewrite-page-parameter-refused","rewrite-session-query-positive","rewrite-session-query-missing-refused","rewrite-session-query-wrong-refused","rewrite-session-block-header-refused"}
 expected_controls=base|rewrites|set(intake["runtimeControls"]);assert len(expected_controls)==41
 for controls in [runtime["browserControls"],browser["controls"]]:assert len(controls)==41 and{c["name"]for c in controls}==expected_controls and all(c["passed"]is True for c in controls)
 assert runtime["upstreamPageTests"]==browser["upstreamPageTests"]==4
 assert browser["ownedBrowserStopped"]and browser["ownedHttpsProxyStopped"]and not browser["credentialsCaptured"]and not browser["rawHttpUploaded"]
 assert runtime["databaseUnixSocketsDisabled"]and runtime["databaseTransportVerified"]=="authenticated IPv4 loopback TCP"
 for key in ["generatedOwnerSecretsAbsentFromEvidence","ownedListenersStopped","ownedProcessGroupsStopped"]:assert runtime[key]is True
 for key in ["sourceMutationRequested","qualificationConfigurationOverlay"]:assert runtime[key]is True
 for key in ["credentialsCaptured","rawRuntimeLogsUploaded","productionActivation","externalModelAccepted"]:assert runtime[key]is False
 for name,value in runtime["driverDigests"].items():assert digest(git_bytes("scripts/"+name))==value
 assert len(runtime["driverDigests"])==9
 actual=runtime["retainedRuntime"];limits=dict(cpu="100000 100000",memory="3221225472",swap="0",pids="128")
 assert actual["kernelLimits"]==actual["enforcementObservation"]["limits"]==actual["applicationCache"]["limits"]==limits
 enforcement=actual["enforcementObservation"]
 assert enforcement["uid"]==1000 and enforcement["readonly"]and enforcement["quotaRefused"]and enforcement["cacheWritable"]and enforcement["cacheQuotaBytes"]==67108864
 assert actual["imageBundle"]==probe["producedTree"] and actual["imageDifference"]["changedEntries"]==0
 assert actual["imageContext"]=="native-selected-candidate"and actual["nodeVersion"]=="v22.23.3"
 assert actual["unavailableProducerPaths"]==8 and not actual["hostSourceOrCompilerMount"] and not actual["networkIsolationClaimed"]
 assert actual["base"]=="node@sha256:bbf39cb344bb33c1f2eedb3b45b4a890eecfbac91a4f7bac020a95d4e4ea147e"
 assert actual["applicationCache"]["files"]>0 and 0<actual["applicationCache"]["bytes"]<67108864
 assert receipt["generatedOutputObservation"]["before"]==receipt["generatedOutputObservation"]["after"]and receipt["generatedOutputObservation"]["changedFiles"]==0
 controls=probe["retainedDynamicProfileRefusals"];assert controls["selectionPointerUnchanged"]
 for suffix in ["strippedProfileRefused","strippedModeRefused","disabledDynamicRefused","missingDriverRefused","changedDriverRefused"]:
  records=[c for c in receipt["commands"]if c["label"]=="retained-dynamic-"+suffix];assert len(records)==1 and records[0]["exitCode"]==records[0]["expectedExitCode"]==2
 assert len(owned["containers"])==2 and all(c["confirmedStopped"]is True for c in owned["containers"])
 return dict(sourceInstallationRuntimeSubcontrolsVerified=True,originalSourceMembersRehashed=180,derivedMembersBound=181,textMembersRehashed=175,originalDynamicGitBlobsRehashed=9,physicalModuleBindings=3,runtimeGroupsPassed=41,unchangedOwnerPageTestsPassed=4,realProfileDriverRefusals=5,allOwnedRuntimesStopped=True,originalConfigurationPreserved=False,retainedDynamicPairAccepted=False)

source_case=review_source()
accepted=BASE/("attempt-"+str(RUN));accepted.mkdir(exist_ok=False)
for name in ["receipt.json","package/distribution.json"]:
 p=accepted/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
for name in ["receipt.json","runtime.json","browser-auth.json","dynamic-build-bindings.json","native-observations.json","selected-source.json","derived-source.json","rewrite-overlay.json","rewrite-compiled.json","standalone-probe.json"]:
 p=accepted/"source"/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read("source/"+name))
(accepted/"source-inventory.json").write_text(json.dumps(inventory,indent=2)+"\n")
summary=dict(status="verified-source-subcontrols-in-failed-derived-run",runId=RUN,sourceRevision=REVISION,url=run["html_url"],artifact=dict(id=meta["id"],bytes=meta["size_in_bytes"],digest=meta["digest"],expiresAt=meta["expires_at"],digestIndependentlyVerified=True),allPackagedSourceFilesMatchedGit=len(source_files),nativeArchiveExecutableDigest=native_binary,sourceCase=source_case,parentStatusPreserved="failed",parentFailure=parent["error"],nativeInstallationStarted=True,nativeInstallationCompleted=False,retainedDynamicPairAccepted=False,sourceInventoryDigest=dist["sourceInventoryDigest"],storageObservation=parent["storageObservation"],rawArtifactRetainedOnIntel=False,wholeJobPeakClaimed=False,productionActivation=False,scope="Source495 installed-source41-group retained subcontrols only; combined storage stop preserved; native case incomplete.")
(accepted/"independent-verification.json").write_text(json.dumps(summary,indent=2)+"\n")
(accepted/"review-source.py").write_bytes(Path(__file__).read_bytes())
print(json.dumps(summary,indent=2))
