"""Review the exact public CI artifact in memory; retain only compact records."""
from pathlib import Path, PurePosixPath
import datetime
import base64
import hashlib
import io
import json
import subprocess
import sys
import zipfile

ROOT = Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
GH = ROOT / ".tools/intel-gh-2.102.0-20261015/unpacked/gh_2.102.0_macOS_amd64/bin/gh"
RUN = 40125656603
REVISION = "0f0ce3340e4b9a823fb888c6a6d85b517aa5648a"
BASE = ROOT / "docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024"
MAX = 320 * 1024**2

def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def api(path, binary=False):
    raw = subprocess.check_output([str(GH), "api", "repos/roryscot/patamaps/" + path],
                                  cwd=ROOT, timeout=120, stderr=subprocess.PIPE)
    return raw if binary else json.loads(raw)

def git_bytes(name):
    return subprocess.check_output(["git", "show", REVISION + ":" + name],
                                   cwd=ROOT, timeout=30, stderr=subprocess.PIPE)

run = api("actions/runs/" + str(RUN))
assert run["status"] == "completed" and run["conclusion"] == "success"
assert run["head_sha"] == REVISION and run["event"] == "workflow_dispatch"
jobs = api("actions/runs/" + str(RUN) + "/jobs")["jobs"]
selected = [j for j in jobs if "Pinned Chatbot dynamic page and data boundaries" in j["name"]]
assert len(selected) == 1 and selected[0]["conclusion"] == "success"
for step in selected[0]["steps"]:
    assert step["conclusion"] in ["success", "skipped"]
artifacts = api("actions/runs/" + str(RUN) + "/artifacts")["artifacts"]
assert len(artifacts) == 1
meta = api("actions/artifacts/" + str(artifacts[0]["id"]))
assert meta["name"] == "chatbot-dynamic-" + REVISION
assert not meta["expired"] and meta["size_in_bytes"] <= MAX
assert meta["workflow_run"]["id"] == RUN and meta["workflow_run"]["head_sha"] == REVISION
raw = api("actions/artifacts/" + str(meta["id"]) + "/zip", True)
assert len(raw) == meta["size_in_bytes"] and digest(raw) == meta["digest"]
z = zipfile.ZipFile(io.BytesIO(raw))
members = z.infolist()
assert len(members) < 2000 and sum(i.file_size for i in members) <= MAX
assert len({i.filename for i in members}) == len(members)
for item in members:
    path = PurePosixPath(item.filename)
    assert not path.is_absolute() and ".." not in path.parts
    assert not item.flag_bits & 1 and item.file_size <= 64 * 1024**2

def read(name):
    return z.read(name)

def data(name):
    return json.loads(read(name))

receipt = data("receipt.json")
runtime = data("runtime.json")
browser = data("browser-auth.json")
bindings = data("dynamic-build-bindings.json")
observation = data("native-observations.json")
inventory = data("selected-source.json")
assert receipt["status"] == "passed-pinned-chatbot-source-build-auth"
assert receipt["sourceRevision"] == REVISION
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
tree = json.loads((Path(__file__).parent / "upstream-tree.json").read_bytes())
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
accepted = BASE / ("accepted-" + str(RUN))
accepted.mkdir(exist_ok=False)
retained = {}
for name in ["receipt.json", "runtime.json", "browser-auth.json", "dynamic-build-bindings.json",
             "native-observations.json", "selected-source.json"]:
    body = read(name)
    assert len(body) <= 4 * 1024**2
    (accepted / name).write_bytes(body)
    retained[name] = dict(bytes=len(body), digest=digest(body))
summary = dict(status="passed-independent-dynamic-runtime-review",
    recordedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    runId=RUN, jobId=selected[0]["id"], sourceRevision=REVISION,
    url=run["html_url"], artifact=dict(id=meta["id"], bytes=meta["size_in_bytes"],
    digest=meta["digest"], expiresAt=meta["expires_at"], digestIndependentlyVerified=True),
    sourceFiles=180, sourceFilesIndependentlyRehashed=180, textInputsRehashed=174,
    binaryInputsRehashedAgainstPublicBlobs=6, pinnedDynamicSourceFiles=9, boundPhysicalModules=3,
    browserControls=29, unchangedUpstreamPageTests=4,
    dynamicRouteWitness=witness, engine=receipt["compiler"]["engine"],
    driverDigests=runtime["driverDigests"], originalOwnerSourceAndConfigurationPreserved=True,
    manifestAndBuildReceiptDigestsRehashed=True, ownedRuntimeCleanupVerified=True,
    generatedSecretsBarrierReportedPassed=True, rawArtifactRetained=False,
    productionActivation=False, performanceAccepted=False,
    installedReplayOfThisIncrementAccepted=False, retainedCompactFiles=retained,
    retainedBytes=sum(x["bytes"] for x in retained.values()),
    scope="Pinned original-config native/source Next development engine and explicit dynamic page/data boundaries; no generation, complete dependency closure, other dynamic shapes or performance acceptance.")
(accepted / "independent-verification.json").write_text(json.dumps(summary, indent=2) + "\n")
(accepted / "review-source.py").write_bytes(Path(__file__).read_bytes())
(accepted / "upstream-tree.json").write_bytes((Path(__file__).parent / "upstream-tree.json").read_bytes())
print(json.dumps(summary, indent=2))
