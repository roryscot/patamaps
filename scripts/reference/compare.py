"""Run pinned MetaMap and Rust against independently declared shared cases."""
import argparse
import copy
import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = "399747a4ad05a37cd8db1cedd53048fad2175be4"
parser = argparse.ArgumentParser()
parser.add_argument("reference", type=Path)
parser.add_argument("--node", type=Path, required=True)
parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/patamaps")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

def run(argv, cwd):
    result = subprocess.run([str(a) for a in argv],cwd=cwd,capture_output=True,text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout

graph = json.loads((ROOT / "fixtures/routing/graph.json").read_text())
policy = json.loads((ROOT / "fixtures/routing/policy.json").read_text())
spec = json.loads((ROOT / "fixtures/routing/projection-spec.json").read_text())
cases = []
def case(identity, expected, edit=lambda g,p,s,c:None):
    g,p,s,c = copy.deepcopy(graph),copy.deepcopy(policy),copy.deepcopy(spec),{}
    edit(g,p,s,c)
    cases.append({"id":identity,"expected":expected,"graph":g,"policy":p,"spec":s,"context":c,"evaluatedAt":"2026-10-10T12:00:00Z"})
case("normal-routing","viable")
case("moved-locator","viable",lambda g,p,s,c:g["entities"][1]["locators"][0].update(uri="typescript:./moved.ts#handleCreateUser"))
case("missing-coverage","rejected",lambda g,p,s,c:p["mappings"].pop())
case("duplicate-coverage","rejected",lambda g,p,s,c:p["mappings"].append(copy.deepcopy(p["mappings"][0])))
def empty_selector(g,p,s,c):
    p["mappings"][0].pop("mapping"); p["mappings"][0]["select"] = {}
case("empty-selector","rejected",empty_selector)
def overlap(g,p,s,c):
    declaration = copy.deepcopy(p["mappings"][0]); declaration.pop("mapping"); declaration["select"]={"relations":["routing:handled_by"]}; p["mappings"].append(declaration)
case("overlapping-selector","rejected",overlap)
def context(g,p,s,c):
    p["mappings"][4]["applicability"]={"when":{"key":"environment","operator":"equals","value":"production"}}
case("missing-context","rejected",context)
def inactive(g,p,s,c):
    context(g,p,s,c); c["environment"]="development"
case("inactive-event","viable",inactive)
def owners(g,p,s,c):
    a = copy.deepcopy(g["authorities"][0]); a["id"]="urn:authority:conflicting"; g["authorities"].append(a)
case("conflicting-owners","rejected",owners)
def narrowing(g,p,s,c):
    a = copy.deepcopy(g["authorities"][0]); a.update(id="urn:authority:delegate",mode="delegated",delegatedFrom=g["authorities"][0]["id"],source=g["entities"][1]["id"]); g["authorities"].append(a)
case("narrow-delegation","viable",narrowing)
def widening(g,p,s,c):
    narrowing(g,p,s,c); g["authorities"][1]["facts"].append("new-fact")
case("widened-delegation","rejected",widening)
case("wrong-target-kind","rejected",lambda g,p,s,c:g["entities"][1].update(kind="routing:schema"))
def ambiguous(g,p,s,c):
    entity = copy.deepcopy(g["entities"][1]); entity["id"]="urn:handler:second"; entity.pop("locators",None); g["entities"].append(entity)
    mapping = copy.deepcopy(g["mappings"][0]); mapping.update(id="urn:mapping:second",targets=[entity["id"]]); g["mappings"].append(mapping)
    declaration=copy.deepcopy(p["mappings"][0]); declaration["mapping"]=mapping["id"]; p["mappings"].append(declaration); p["constraints"]=[]
case("ambiguous-slot","rejected",ambiguous)
case("lossy-slot","rejected",lambda g,p,s,c:g["mappings"][0].update(lossiness="lossy"))
case("stale-revision","rejected",lambda g,p,s,c:p["graph"].update(revision="stale"))
case("unsupported-constraint","rejected",lambda g,p,s,c:p["constraints"][0].update(kind="unknown:constraint"))
def unknown(g,p,s,c):
    subject=g["entities"][0]["id"]
    p["constraints"].append({"id":"urn:constraint:evidence","kind":"core:requires-evidence","subjects":[subject]})
    p["evidence"].append({"id":"urn:evidence:inconclusive","kind":"test","subjects":[subject],"result":"inconclusive","confidence":1,"producer":"test"})
case("inconclusive-required-evidence","rejected",unknown)
def contradiction(g,p,s,c):
    p["evidence"].append({"id":"urn:evidence:contradiction","kind":"test","subjects":[g["entities"][0]["id"]],"result":"contradicts","producer":"test"})
case("contradiction","rejected",contradiction)

def normalized(compiled,projected=None):
    if compiled["status"] != "viable" or (projected and projected["status"] not in ["projected","viable"]):
        return {"status":"rejected"}
    projection = (projected or {}).get("projection")
    return {"status":"viable","activeMappings":sorted(compiled["generation"]["activeMappings"]),
            "inactiveMappings":sorted(compiled["generation"]["inactiveMappings"],key=lambda i:i["id"]),
            "bindings":[{"subject":e["subject"],"slots":[{"name":s["name"],"relation":s["relation"],"direction":s["direction"],"cardinality":s["cardinality"],"mappings":sorted(s["mappings"]),"targets":sorted(s["targets"],key=lambda t:t["id"])} for s in sorted(e["slots"],key=lambda s:s["name"])]} for e in sorted(projection["entries"],key=lambda e:e["subject"]["id"])] if projection else None}

with tempfile.TemporaryDirectory(prefix="patamaps-reference-") as directory:
    work=Path(directory); checkout=work / "reference"; checkout.mkdir()
    archive=work / "reference.tar"
    run(["git","-C",args.reference,"archive",ENGINE,"--output",archive],ROOT)
    with tarfile.open(archive) as tar: tar.extractall(checkout,filter="data")
    (checkout / "node_modules").symlink_to(args.reference.resolve() / "node_modules",target_is_directory=True)
    build=run([args.node,checkout / "node_modules/typescript/lib/tsc.js","-p","tsconfig.build.json"],checkout)
    fixture_path=work / "cases.json"; fixture_path.write_text(json.dumps(cases))
    reference=json.loads(run([args.node,ROOT / "scripts/reference/evaluate.mjs",checkout,fixture_path],checkout))
    successor=[]; comparisons=[]
    for fixture,legacy in zip(cases,reference,strict=True):
        for name in ["graph","policy","spec","context"]: (work / f"{name}.json").write_text(json.dumps(fixture[name]))
        argv=[args.cli.resolve(),"capture","graph.json","policy.json","--spec","spec.json","--context","context.json","--as-of",fixture["evaluatedAt"],"--relation-pack",ROOT / "relation-packs/routing.json"]
        rust=json.loads(run(argv,work)); successor.append({"id":fixture["id"],"capture":rust})
        a=normalized(legacy["compiled"],legacy.get("projected"))
        result=rust["result"]; b=normalized(result,{"status":"projected","projection":result["projection"]} if result["status"]=="viable" else None)
        comparisons.append({"id":fixture["id"],"expected":fixture["expected"],"reference":a,"successor":b,"semanticPass":a==b and a["status"]==fixture["expected"],
                            "referenceDiagnostics":[{"code":i["code"],"subjectId":i.get("subjectId")} for i in legacy["compiled"].get("issues",[])]+[{"code":i["code"],"subjectId":i.get("subjectId")} for i in (legacy.get("projected") or {}).get("issues",[])],
                            "successorDiagnostics":[{"code":i["code"],"subjectId":i.get("subjectId")} for i in rust["result"].get("issues",[])]})
    for comparison,fixture in zip(comparisons,cases,strict=True):
        # One declared wire-validation difference, D004. No semantic diagnostic
        # or subject is removed to obtain agreement; both original reports stay.
        def origins(items):
            return sorted({("INVALID_POLICY_FORMAT",fixture["policy"]["id"]) if item["code"] in ["INVALID_VIABILITY_POLICY","INVALID_MAPPING_SELECTOR"] and fixture["id"]=="empty-selector" else (item["code"],item["subjectId"]) for item in items},key=str)
        comparison["normalizedReferenceOrigins"]=origins(comparison["referenceDiagnostics"])
        comparison["normalizedSuccessorOrigins"]=origins(comparison["successorDiagnostics"])
        comparison["diagnosticPass"]=comparison["normalizedReferenceOrigins"]==comparison["normalizedSuccessorOrigins"]
        comparison["pass"]=comparison["semanticPass"] and comparison["diagnosticPass"]
    report={"engineRevision":ENGINE,"executor":successor[0]["capture"]["executor"],"node":run([args.node,"--version"],ROOT).strip(),"cases":cases,"referenceOutputs":reference,"successorOutputs":successor,"comparisons":comparisons,
            "comparisonContract":"D001: exact input/output hashes and envelope versions differ; compare admission, active/inactive mappings, selected identities, cardinalities, mapping origins and target metadata. D004: the empty-selector format finding is attributed to its policy in both engines; all other code/subject origins must agree exactly. All complete outputs are retained."}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    failures=[c["id"] for c in comparisons if not c["pass"]]
    assert not failures, f"Reference disagreement: {failures}; inspect {args.output}"
    print(f"PASS: {len(comparisons)} independently declared shared routing cases against isolated reference {ENGINE}; complete outputs in {args.output}")
