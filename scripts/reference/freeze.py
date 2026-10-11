"""Freeze the reviewed reference by commit; never rewrite the source checkout."""
import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

ENGINE = "399747a4ad05a37cd8db1cedd53048fad2175be4"
RECORD = "6a6a9d2415df85504a83fce4fd7291d0391c0d17"
ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("reference", type=Path)
parser.add_argument("--schemas-only", action="store_true", help="Regenerate base draft schemas without freezing or replacing conformance records")
args = parser.parse_args()

def git(*argv):
    return subprocess.check_output(["git", "-C", str(args.reference), *argv])

def original(path):
    return git("show", f"{ENGINE}:{path}")

def write_json(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

def write_schemas():
    schemas = {"graph": "metamap-graph", "policy": "metamap-viability",
               "relation-pack": "relation-pack", "projection-spec": "metamap-projection-spec"}
    for name, source in schemas.items():
        value = copy.deepcopy(json.loads(original(f"schemas/{source}.schema.json")))
        value["$id"] = f"urn:patamaps:draft:1:schema:{name}"
        value["title"] = f"Patamaps draft {name}"
        value["properties"]["schemaVersion"] = {"const": "0.1.0"}
        value["properties"]["documentType"] = {"const": name}
        value["required"].append("documentType")
        if name == "projection-spec":
            value["properties"].pop("pathTree", None)
            value["properties"].pop("metadata", None)
            value["$defs"].pop("pathTree", None)
        write_json(f"schemas/{name}.schema.json", value)

if args.schemas_only:
    write_schemas()
    print("Regenerated four base Patamaps draft schemas; preserved sources and conformance records untouched.")
    raise SystemExit(0)

files = git("ls-tree", "-r", "--name-only", ENGINE).decode().splitlines()
preserved = []
for path in files:
    if (path.startswith(("schemas/", "relation-packs/", "examples/routing/"))
        or path in ["LICENSE", "NOTICE", "evaluation/README.md", "evaluation/capability-corpus.json",
                    "evaluation/legacy-compatibility.json", "evaluation/first-release-acceptance.json",
                    "src/__tests__/canonical.test.ts"]):
        data = original(path)
        target = ROOT / "fixtures/reference" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        preserved.append({"path": path, "sha256": hashlib.sha256(data).hexdigest()})
for path in ["LICENSE", "NOTICE"]:
    (ROOT / path).write_bytes(original(path))

write_schemas()
for path in files:
    if path.startswith("relation-packs/") and path.endswith(".json"):
        value = json.loads(original(path))
        if value["schemaVersion"] == "1.0.0":
            value.pop("$schema", None)
            value.update(schemaVersion="0.1.0", documentType="relation-pack")
            write_json(path, value)
for name, source, kind in [("graph", "graph", "graph"), ("policy", "viability-policy", "policy"),
                           ("projection-spec", "projection", "projection-spec")]:
    value = json.loads(original(f"examples/routing/{source}.json"))
    value.pop("$schema", None)
    value.update(schemaVersion="0.1.0", documentType=kind)
    write_json(f"fixtures/routing/{name}.json", value)

stages = {}
for stage, names in {
    "R1": "canonical schema-contract validator graph composer relation-pack",
    "R2": "viability projection consumer-bindings typed-native",
    "R3": "diff replay counterfactual source-replay current-sources source-cli provenance typed-replay",
    "R4": "path-tree derivation semantic executable-pack semantic-projection semantic-replay semantic-counterfactual",
    "R5": "uncertainty risk",
    "R6": "governance governance-native",
    "R7": "activation governed-activation protected-activation",
    "R8": "repair repair-native explanation explanation-native debugger debugger-native",
    "R9": "config adapter-registry adapters metamap-shard workspace legacy-adapter correspondence nextjs-app-router application-topology",
    "R10": "sssom scientific-source scientific-source-native scientific-crate",
    "R11": "lifecycle-native legacy-compatibility",
}.items():
    for name in names.split():
        stages[name] = stage
suites = []
for path in files:
    if path.startswith("src/__tests__/") and path.endswith(".test.ts"):
        name = Path(path).name.removesuffix(".test.ts")
        suites.append({"suite": name, "path": path, "sha256": hashlib.sha256(original(path)).hexdigest(),
                       "milestone": stages[name], "status": "pending-successor-acceptance"})
assert len(suites) == 53
corpus=json.loads(original("evaluation/capability-corpus.json"))
destinations={"normal-binding":"R2","moved-implementation":"R2","development-context":"R2","missing-handler":"R2","ambiguous-handler":"R2","missing-endpoint":"R2","ambiguous-endpoint":"R2","missing-context":"R2","conflicting-owners":"R1","narrow-delegation":"R1","widened-delegation":"R1","conflicting-shards":"R1","unmapped-leaf":"R9","owned-exclusion":"R9","invalid-native-export":"R2","locator-escape":"R9","symlink-escape":"R9","native-byte-drift":"R9","stale-generation":"R2","new-implementation-identity":"R2","invalid-runtime-input":"R9","runtime-structure-change":"R4"}
native_cases=[{"referenceCase":case["id"],"originalExpectation":case,"milestone":destinations[case["id"]],"status":"pending-successor-profile-acceptance"} for case in corpus["consumerBindings"]]
assert len(native_cases)==22
write_json("fixtures/conformance.json", {
    "schemaVersion": "0.1.0", "referenceRepository": "https://github.com/roryscot/metamap",
    "engineRevision": ENGINE, "buildRecordRevision": RECORD,
    "profile": "patamaps-routing-draft-1", "preservedFiles": preserved, "suites": suites,
    "nativeBindingCases":native_cases,
    "intentionalDifferences": [
        {"id": "D001", "description": "New draft envelopes and JCS addresses; reference records, hashes and approvals remain original evidence."},
        {"id": "D002", "description": "Initial native dispatch demo explicitly supports string-to-string functions; other signatures require later emitter profiles."},
        {"id": "D003", "description": "Draft waivers cover listed policy findings only; malformed, unsupported and authentication inputs cannot be waived."},
        {"id":"D004","description":"An empty mapping selector is a policy-format error. Rust attributes INVALID_MAPPING_SELECTOR to the policy ID; the reference reports INVALID_VIABILITY_POLICY with a policy JSON path. Differential checks normalize only this declared formatting control; semantic finding codes and subjects stay exact."},
    ],
    "visionCoverage": {"coherence": ["R1", "R2"], "checked-inference": ["R4"], "consumer-uncertainty": ["R5"],
                       "evidence-replay": ["R3"], "external-governance": ["R6", "R7"],
                       "bounded-inspection": ["R8"], "interoperable-lifecycle": ["R9", "R10", "R11"]},
})
print(f"Preserved {len(preserved)} original files and pinned {len(suites)} suites at {ENGINE}")
