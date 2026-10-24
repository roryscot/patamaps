"""Independent bounded installed-package and real Next artifact review; no extraction."""
from pathlib import Path,PurePosixPath
import base64,datetime,hashlib,io,json,re,subprocess,sys,tarfile,zipfile

ROOT=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
GH=ROOT/".tools/intel-gh-2.102.0-20261015/unpacked/gh_2.102.0_macOS_amd64/bin/gh"
RUN=40127431158
REVISION="9276b0766bb3ce842aec13da7b7556bb13060132"
BASE=ROOT/"docs/acceptance/project-adoption/g5-installed-next-dynamic-20261024"
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
assert run["status"]=="completed" and run["conclusion"]=="success" and run["head_sha"]==REVISION
jobs=api("actions/runs/"+str(RUN)+"/jobs")["jobs"]
selected=[j for j in jobs if "Pinned Chatbot dynamic page and data boundaries" in j["name"]]
assert len(selected)==1 and selected[0]["conclusion"]=="success"
assert all(s["conclusion"] in ["success","skipped"] for s in selected[0]["steps"])
artifacts=api("actions/runs/"+str(RUN)+"/artifacts")["artifacts"];assert len(artifacts)==1
meta=api("actions/artifacts/"+str(artifacts[0]["id"]))
assert meta["name"]=="installed-dynamic-next-"+REVISION and meta["workflow_run"]["head_sha"]==REVISION and meta["workflow_run"]["id"]==RUN
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
assert parent["status"]=="passed-installed-next-dynamic-workflows" and parent["sourceRevision"]==REVISION
assert parent["distribution"]==dist and set(parent["cases"])=={"source","native"}
for key in ["installedDynamicProfileAccepted","sourceCompilerBuiltFromInstalledSource","sharedCargoDependencyArtifacts",
            "checkoutCompilerUnavailableBeforeFreshSourceBuild","checkoutCompilerAndDriverUnavailableDuringOwners",
            "changedSourceRefusedBeforeCompilerMarker","restoredSourceInventoryVerified","publicCachesShared",
            "checkoutCompilerBytesRestored","checkoutDriverBytesRestored"]:
 assert parent[key] is True,key
for key in ["productionActivation","registryPublication","completeDependencyClosure","fullRetainedNextBundleAccepted","performanceAccepted","privateGeneratedOutputsPublished"]:
 assert parent[key] is False,key
assert parent["filesDeleted"]==0 and parent["maximumQualificationGrowthBytes"]==4000000000
assert parent["storageObservation"]["peakGrowthBytes"]<=4000000000
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
expected_identity=parent["sourceIdentity"]
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
assert "INSTALLED_SOURCE_BYTES_CHANGED" in read("logs/changed-installed-source-before-compiler.stderr").decode()
assert data("logs/package-engine.stdout")==expected_engine

def review_case(label):
 def read(name):return z.read(label+"/"+name)
 def data(name):return json.loads(read(name))
 receipt = data("receipt.json")
 runtime = data("runtime.json")
 browser = data("browser-auth.json")
 bindings = data("dynamic-build-bindings.json")
 observation = data("native-observations.json")
 inventory = data("selected-source.json")
 assert receipt["status"] == "passed-pinned-chatbot-source-build-auth"
 assert receipt["sourceRevision"] is None and receipt["installedSourceIdentity"] == expected_identity
 assert receipt["installedSourceInventoryUnchanged"] is True
 assert receipt["upstreamCommit"] == "c2f8235e1f3ea903ad8b7f61447c4f74164b5c58"
 assert receipt["frameworkVersion"] == "16.2.10"
 for key in ["frameworkBuildEstablished", "runtimeEstablished", "authenticationAccepted",
             "ownerRuntimeMigrationExecuted", "selectedSourceBytesAndModesUnchanged",
             "sourceExclusionAudited", "nativeCompiledObservation"]:
     assert receipt[key] is True, key
 for key in ["dependencyClosureEstablished", "applicationAcceptance", "productionActivation",
             "dependencyLifecycleScriptsExecuted"]:
     assert receipt[key] is False, key
 assert receipt["filesDeleted"] == 0 and receipt["maximumWorkflowGrowthBytes"] == 4000000000
 assert all(c["exitCode"] == c["expectedExitCode"] for c in receipt["commands"])
 assert receipt["dynamicRouteQualification"] == dict(buildBindingsVerified=True,
     nativeObservationDigest=digest(read("native-observations.json")), runtimeAccepted=True,
     sourceBytesUnchanged=True, privateEvidenceBarrierPassed=True, ownedRuntimesStopped=True)
 tree = json.loads(git_bytes("docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024/accepted-40125656603/upstream-tree.json"))
 assert tree["truncated"] is False
 original = {e["path"]: e for e in tree["tree"] if e["type"] == "blob" and e["path"] != ".env.example"}
 assert len(inventory) == receipt["sourceFiles"] == len(original) == 180
 assert {row["path"] for row in inventory} == set(original)
 text_capture = data("logs/text-source-capture.stdout")
 assert text_capture["digest"] == receipt["textSourceDigest"]
 texts = {e["receipt"]["path"]: e for e in text_capture["inputs"]}
 assert len(texts) == len(text_capture["inputs"]) == receipt["sourceTextFiles"] == 174
 assert data("logs/source-context-capture.stdout")["digest"] == receipt["sourceContextDigest"]
 binary_members = 0
 for row in inventory:
     entry = original[row["path"]]
     assert entry["sha"] == row["gitBlob"] and entry["mode"] == row["mode"] and entry["size"] == row["bytes"]
     if row["path"] in texts:
         captured = texts[row["path"]]
         body = captured["content"].encode()
         assert captured["receipt"]["digest"] == row["digest"]
         assert captured["receipt"]["byteLength"] == row["bytes"]
     else:
         blob_raw = subprocess.check_output([str(GH), "api", "repos/vercel/chatbot/git/blobs/" + row["gitBlob"]],
                                           cwd=ROOT, timeout=60, stderr=subprocess.PIPE)
         blob = json.loads(blob_raw)
         assert blob["encoding"] == "base64" and blob["sha"] == row["gitBlob"]
         body = base64.b64decode("".join(blob["content"].split()), validate=True)
         binary_members += 1
     assert len(body) == row["bytes"] and digest(body) == row["digest"]
     assert hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest() == row["gitBlob"]
 assert binary_members == 6
 intake = json.loads(git_bytes("docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024/intake.json"))
 source = receipt["dynamicSourceBindings"]
 assert source["gitBlobs"] == intake["publicGitBlobs"] and source["sourceFiles"] == 9
 assert source["sourceMutated"] is False and bindings["ownerSourceBindings"] == source
 assert all(next(row for row in inventory if row["path"] == name)["gitBlob"] == blob
            for name, blob in intake["publicGitBlobs"].items())
 assert bindings["nativeObservationDigest"] == digest(read("native-observations.json"))
 assert bindings["regexExecuted"] is False and bindings["nativeRuntimeClaim"] is False
 assert bindings["runtimeWitnessRequired"] is True
 expected_bindings = {
     "/chat/[id]": ("dynamic", "/(chat)/chat/[id]/page", "app/(chat)/chat/[id]/page.js"),
     "/api/chat/[id]/stream": ("dynamic", "/(chat)/api/chat/[id]/stream/route", "app/(chat)/api/chat/[id]/stream/route.js"),
     "/api/messages": ("static", "/(chat)/api/messages/route", "app/(chat)/api/messages/route.js"),
 }
 request = data("logs/native-compiled-next-observations.input")
 assert observation["requestDigest"] == request["requestDigest"] == data("logs/manifest-request-digest.stdout")
 inputs = {}
 for entry in request["inputs"]:
     body = entry["content"].encode()
     assert entry["receipt"]["digest"] == digest(body) and entry["receipt"]["byteLength"] == len(body)
     inputs[entry["receipt"]["path"]] = json.loads(body)
 assert len(inputs) == 4
 config = inputs["config.json"]
 assert config["buildReceiptDigest"] == digest(read("logs/owner-production-build.stdout"))
 for field, name in [("routesDigest", "routes.json"), ("appPathsDigest", "app-paths.json"), ("appPathRoutesDigest", "app-routes.json")]:
     item = next(e for e in request["inputs"] if e["receipt"]["path"] == name)
     assert config[field] == digest(item["content"].encode())
 assert config["frameworkVersion"] == "16.2.10" and config["configuration"]["output"] == "server"
 meta_observed = observation["shard"]["metadata"]["observation"]
 assert meta_observed["regexExecuted"] is False and meta_observed["runtimeEstablished"] is False
 assert len(bindings["bindings"]) == 3
 for route, (category, app_path, module_file) in expected_bindings.items():
     records = [b for b in bindings["bindings"] if b["routePath"] == route]
     assert len(records) == 1
     record = records[0]
     assert (record["category"], record["appPath"], record["moduleFile"]) == (category, app_path, module_file)
     actual_route = [e for e in observation["shard"]["entities"] if e["id"] == record["routeEntity"]]
     actual_module = [e for e in observation["shard"]["entities"] if e["id"] == record["moduleEntity"]]
     assert len(actual_route) == len(actual_module) == 1
     a, b = actual_route[0]["attributes"], actual_module[0]["attributes"]
     assert a["page"] == route and a["category"] == category and a["regexExecuted"] is False
     assert a["httpMethods"] == b["httpMethods"] == "not-observed"
     assert b["appPath"] == app_path and b["moduleFile"] == module_file
     assert b["businessCorrespondence"] == "not-inferred"
     manifest_routes = inputs["routes.json"]["dynamicRoutes" if category == "dynamic" else "staticRoutes"]
     assert len([x for x in manifest_routes if x["page"] == route]) == 1
     assert inputs["app-paths.json"][app_path] == module_file
     assert inputs["app-routes.json"][app_path] == route
 sys.path.insert(0, str(ROOT / "scripts/parity"))
 from identity import identities
 assert receipt["compiler"]["engine"] == dict(schemaVersion="0.1.0", documentType="executor-description", **identities(ROOT))
 assert runtime["status"] == browser["status"] == "passed"
 for key in ["runtimeEstablished", "authenticationAccepted", "ownerMigrationExecuted",
             "generatedOwnerSecretsAbsentFromEvidence", "ownedListenersStopped", "ownedProcessGroupsStopped"]:
     assert runtime[key] is True, key
 for key in ["credentialsCaptured", "rawRuntimeLogsUploaded", "productionActivation",
             "externalModelAccepted", "sourceMutationRequested", "qualificationConfigurationOverlay"]:
     assert runtime[key] is False, key
 base_controls = {
     "unchanged-upstream-four-auth-page-tests", "invalid-registration-action",
     "successful-registration-action", "production-secure-session-cookie",
     "duplicate-registration-action-refusal", "invalid-login-action",
     "wrong-password-action-refusal", "successful-login-action",
     "off-origin-action-refusal-before-database-effect", "same-request-valid-origin-positive-control",
     "independent-second-user-registration", "owner-private-document-create-and-read",
     "cross-user-private-document-read-refusal", "cross-user-private-document-write-refusal",
     "guest-private-document-read-refusal", "credential-and-cookie-evidence-barrier",
 }
 expected_controls = base_controls | set(intake["runtimeControls"])
 for controls in [browser["controls"], runtime["browserControls"]]:
     assert len(controls) == 29 and {c["name"] for c in controls} == expected_controls
     assert all(c["passed"] is True for c in controls)
 assert runtime["upstreamPageTests"] == browser["upstreamPageTests"] == 4
 for key in ["ownedBrowserStopped", "ownedHttpsProxyStopped"]:
     assert browser[key] is True, key
 assert browser["credentialsCaptured"] is False and browser["rawHttpUploaded"] is False
 witness = runtime["dynamicRouteWitness"]
 assert witness == browser["dynamicRouteWitness"]
 for key in ["fixturesUnchanged", "ownerPathAndQueryIdMatched", "ownerPrivateMessageRendered",
             "distinctSecondIdRendered", "crossUserPublicReadonly", "guestPublicReadonly",
             "unseenIdEmptyAndNotPersisted"]:
     assert witness[key] is True, key
 for key, status in [("crossUserPrivateStatus", 403), ("guestPrivateStatus", 403),
                     ("missingQueryStatus", 400), ("extraPageSegmentStatus", 404),
                     ("streamGetStatus", 204), ("streamPostStatus", 405),
                     ("extraStreamSegmentStatus", 404)]:
     assert witness[key] == status, key
 assert witness["generationPostAttempts"] == 0 and witness["rawFixtureValuesPublished"] is False
 assert len(witness["fixtureDigest"]) == 71 and witness["fixtureDigest"].startswith("sha256:")
 for name, expected in runtime["driverDigests"].items():
     assert digest(git_bytes("scripts/" + name)) == expected, name

 case=parent["cases"][label]
 assert case["compilerDigest"]==receipt["compiler"]["sha256"]
 assert case["engine"]==expected_engine and case["sourceInventoryDigest"]==dist["sourceInventoryDigest"]
 assert case["sourceFiles"]==expected_identity["sourceFiles"]
 assert case["runtimeGroupsPassed"]==29 and case["upstreamPageTestsPassed"]==4
 for key in ["sourceWithoutGit","checkoutCompilerAndDriverUnavailable","allOwnedRuntimesStopped","originalOwnerConfigurationPreserved"]:
  assert case[key] is True,key
 assert case["dynamicRouteQualification"]==receipt["dynamicRouteQualification"]
 assert case["dynamicRouteWitness"]==witness
 assert data("logs/current-engine.stdout")==expected_engine
 assert json.loads(z.read("logs/"+label+"-installed-engine.stdout"))==expected_engine
 return dict(compilerDigest=case["compilerDigest"],engine=expected_engine,sourceFilesRehashed=180,
             textInputsRehashed=174,binaryInputsRehashedAgainstPublicBlobs=6,physicalModuleBindings=3,
             runtimeGroupsPassed=29,upstreamPageTestsPassed=4,dynamicRouteWitness=witness,
             driverDigests=runtime["driverDigests"],installedSourceUnchanged=True,
             ownedRuntimesStopped=True,originalOwnerSourceAndConfigurationPreserved=True)

cases={label:review_case(label) for label in ["source","native"]}
assert cases["native"]["compilerDigest"]==native_binary
assert cases["source"]["compilerDigest"]==native_binary
accepted=BASE/("accepted-"+str(RUN));accepted.mkdir(exist_ok=False)
retained={}
for name in ["receipt.json","package/distribution.json"]:
 body=z.read(name);p=accepted/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
 retained[name]=dict(digest=digest(body),bytes=len(body))
for label in cases:
 for name in ["receipt.json","runtime.json","browser-auth.json","dynamic-build-bindings.json","native-observations.json","selected-source.json"]:
  path=label+"/"+name;body=z.read(path);assert len(body)<=4*1024**2
  target=accepted/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
  retained[path]=dict(digest=digest(body),bytes=len(body))
(accepted/"source-inventory.json").write_text(json.dumps(inventory,indent=2)+"\n")
summary=dict(status="passed-independent-installed-next-dynamic-review",
 observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),runId=RUN,jobId=selected[0]["id"],
 url=run["html_url"],sourceRevision=REVISION,artifact=dict(id=meta["id"],bytes=meta["size_in_bytes"],digest=meta["digest"],expiresAt=meta["expires_at"],digestIndependentlyVerified=True),
 allPackagedSourceFilesMatchedGit=len(source_files),sourceInventoryDigest=dist["sourceInventoryDigest"],
 nativeArchiveExecutableDigestIndependentlyRehashed=native_binary,reportedFreshSourceCompilerDigest=cases["source"]["compilerDigest"],
 installedSourceCompilerRecompilationWitnessVerified=True,checkoutCompilerUnavailableBeforeSourceCompilation=True,
 checkoutCompilerAndDriverUnavailableDuringOwners=True,checkoutCompilerAndDriverBytesRestored=True,
 changedInstalledSourceRefusedBeforeEffects=True,restoredInstalledSourceInventoryVerified=True,
 cases=cases,engine=expected_engine,parentMonitoredStorageObservation=parent["storageObservation"],
 wholeJobResourcePeakClaimed=False,rawArtifactRetainedOnIntel=False,retainedCompactReceipts=retained,
 performanceAccepted=False,retainedDynamicReplayAccepted=False,completeDependencyClosure=False,productionActivation=False,
 scope="Exact fresh source/native development-profile pair, unchanged pinned owner and original-config29-group dynamic/auth workflow; other owner, retained, closure and performance gates remain open.")
(accepted/"independent-verification.json").write_text(json.dumps(summary,indent=2)+"\n")
(accepted/"review-source.py").write_bytes(Path(__file__).read_bytes())
print(json.dumps(summary,indent=2))
