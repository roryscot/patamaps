"""Exact decision/origin comparison for the declared shared semantic profile.

The engines independently construct proofs. D001 removes only different wire
envelopes/content addresses from comparison; complete records are retained.
"""
import argparse,copy,json,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ENGINE="399747a4ad05a37cd8db1cedd53048fad2175be4"
parser=argparse.ArgumentParser()
parser.add_argument("reference",type=Path)
parser.add_argument("--node",type=Path,required=True)
parser.add_argument("--cli",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
def run(argv,cwd,accepted=(0,)):
 p=subprocess.run([str(a) for a in argv],cwd=cwd,capture_output=True,text=True)
 assert p.returncode in accepted,p.stdout+p.stderr
 return p.stdout
base={key:json.loads((ROOT/"fixtures/laws"/f"{name}.json").read_text()) for key,name in [("graph","graph"),("pack","pack"),("request","request"),("policy","policy"),("spec","projection-spec")]}
cases=[]
def case(id,expected,edit=lambda v:None,after=None):
 v=copy.deepcopy(base);v.update(id=id,expected=expected,evaluatedAt="2026-10-10T12:00:00Z",after=after);edit(v);cases.append(v)
def assess(v,subject,dimension="identity",state="supported",result="supports",model=None):
 r=v["request"];i=len(r["assessments"]);eid=f"urn:evidence:{i}"
 a={"id":f"urn:assessment:{i}","subject":subject,"dimension":dimension,"status":state,"evidence":[eid],"assessor":"recorded-assessor","sourceRevision":"1"}
 if model:a["measurementModel"]=model
 if state=="not-applicable":a["notApplicableReason"]="Explicitly outside this subject's declared applicability."
 r["assessments"].append(a);r["evidence"].append({"id":eid,"subjects":[subject],"kind":"uncertainty:"+dimension,"result":result,"producer":"source-owner","confidence":0.99})
def require(v,states=("supported",),evidence=True):
 v["policy"]["semantics"]["uncertaintyRequirements"]=[{"id":"urn:requirement:identity","select":{"ids":["urn:m:ac"]},"dimension":"identity","allowedStates":list(states),"requireEvidence":evidence}]
def supported(v,dimension="identity"):
 for id in ["urn:m:ab","urn:m:bc"]:assess(v,id,dimension)
def budget(v,limit=5,costs=(2,3,0)):
 v["policy"]["semantics"]["riskBudgets"]=[{"id":"urn:budget:example","consumer":"urn:consumer:example","maximumTotalCost":limit,"requireCompleteClassification":True,"requireCompleteDependencies":True,"classifications":[{"id":f"urn:cost:{i}","select":{"ids":[id]},"classification":"declared" if i<2 else "inference","cost":cost} for i,(id,cost) in enumerate(zip(["urn:m:ab","urn:m:bc","urn:m:ac"],costs,strict=True))]}]
 v["spec"]["semantics"]["budget"]="urn:budget:example"
case("allowed-binary-chain","projected")
def reverse(v):v["request"].update(law="urn:example:law:reverse",premises=["urn:m:ab"]);v["spec"]["slots"][0].update(relation="example:s",direction="incoming")
case("allowed-reverse","projected",reverse)
case("unknown-close-chain","unsupported",lambda v:v["request"].update(law="urn:example:law:close-chain"))
case("missing-premise","unknown",lambda v:v["request"]["premises"].__setitem__(1,"urn:missing"))
case("ordered-roles","rejected",lambda v:v["request"]["premises"].reverse())
case("wrong-middle-identity","rejected",lambda v:v["graph"]["mappings"][1].update(sources=["urn:d"]))
case("zero-depth","incomplete",lambda v:v["request"]["bounds"].update(maxDepth=0))
case("zero-derivations","incomplete",lambda v:v["request"]["bounds"].update(maxDerivations=0))
case("stale-context","rejected",after="stale-context")
case("changed-premise","rejected",after="changed-premise")
case("missing-proof","rejected",after="missing-proof")
def declarations(v):
 v["policy"]["mappings"]=[{"mapping":id,"coverage":"total","determinism":"deterministic","reversibility":"reversible"} for id in ["urn:m:ab","urn:m:bc","urn:m:ac"]]
def inactive(v):declarations(v);v["policy"]["mappings"][0]["applicability"]={"when":{"key":"environment","operator":"equals","value":"production"}}
case("inactive-premise","rejected",inactive)
def strengthened(v):declarations(v);v["policy"]["mappings"][0]["coverage"]="partial"
case("partial-premise","rejected",strengthened)
def irreversible(v):reverse(v);v["policy"]["mappings"][0]["reversibility"]="irreversible"
case("irreversible-reverse","rejected",irreversible)
for dimension in ["identity","context","provenance","completeness","causal-relevance","conflicting-authority"]:
 case("supported-"+dimension,"projected",lambda v,d=dimension:supported(v,d))
case("strict-unknown","rejected",lambda v:require(v))
case("tolerant-unknown","projected",lambda v:require(v,["supported","unknown"],False))
def direct_unknown(v):assess(v,"urn:m:ab");assess(v,"urn:m:ac");require(v)
case("direct-support-keeps-unknown","rejected",direct_unknown)
def inconclusive(v):supported(v);v["request"]["evidence"][0]["result"]="inconclusive";require(v)
case("inconclusive-remains-unknown","rejected",inconclusive)
def contradiction(v):supported(v);v["request"]["evidence"][0]["result"]="contradicts";require(v,["contradicted"])
case("explicitly-tolerated-contradiction","projected",contradiction)
def models(v):assess(v,"urn:m:ab",model="urn:model:first");assess(v,"urn:m:bc",model="urn:model:second");require(v)
case("incompatible-models","rejected",models)
def na(v):assess(v,"urn:m:ab",state="not-applicable");assess(v,"urn:m:bc");require(v)
case("not-applicable-contributor","rejected",na)
case("changed-full-evidence","rejected",supported,after="changed-evidence")
for limit in [4,5,6]:case("budget-limit-"+str(limit),"rejected" if limit==4 else "projected",lambda v,n=limit:budget(v,n))
def repeated(v):budget(v);v["spec"]["slots"].append({**v["spec"]["slots"][0],"name":"second-name"})
case("shared-cost-once","projected",repeated)
def missing(v):budget(v);v["policy"]["semantics"]["riskBudgets"][0]["classifications"].pop()
case("missing-zero-classification","rejected",missing)
def ambiguous(v):budget(v);b=v["policy"]["semantics"]["riskBudgets"][0];b["classifications"].append({**b["classifications"][0],"id":"urn:cost:overlap"})
case("ambiguous-classification","rejected",ambiguous)
case("cost-overflow","rejected",lambda v:budget(v,9007199254740991,[9007199254740991,3,0]))
def optout(v):budget(v);v["spec"]["semantics"]["budget"]=None
case("consumer-budget-opt-out","rejected",optout)
def provenance(v):
 for i in [0,2]:v["graph"]["entities"][i]["provenance"]={"status":"declared","assertedBy":"source-owner","sourceRevision":"1"}
case("projected-provenance-contract","projected",provenance)
def tree(v):v["graph"]["entities"][0]["attributes"]={"path":"/catalog/:id"};v["spec"]["pathTree"]={}
case("semantic-path-tree","projected",tree)
case("missing-authored-path","rejected",lambda v:v["spec"].update(pathTree={}))
def collision(v):
 tree(v);v["graph"]["entities"][3]["attributes"]={"path":"/catalog/:id"};v["spec"]["select"]={"ids":["urn:a","urn:d"]};v["spec"]["slots"][0]["cardinality"]="zero-or-one"
case("tree-path-collision","rejected",collision)

def normalized(report):
 proof=report["proposed"].get("derivation");proof_ids={proof["id"]:proof["result"]["id"]} if proof else {}
 def identity(id):return "proof-for:"+proof_ids[id] if id in proof_ids else id
 def mapping(m):
  m=copy.deepcopy(m);a=m.get("attributes",{});a.pop("metamap:derivation",None)
  if not a:m.pop("attributes",None)
  return m
 def origins(value):return sorted({(i["code"],identity(i.get("subjectId"))) for i in value.get("issues",[])},key=str)
 result={"proposalStatus":report["proposed"]["status"],"proposalOrigins":origins(report["proposed"])}
 if proof:
  result["proof"]={"result":mapping(proof["result"]),"rule":proof["rule"]["id"],"pack":{"id":proof["rule"]["pack"]["id"],"version":proof["rule"]["pack"]["version"]},"premises":[p["mapping"] for p in proof["premises"]],"context":proof["context"],"contextDigest":proof["contextDigest"],"dependencies":sorted(identity(d["id"]) for d in proof["dependencies"]),"depth":proof["depth"],"count":proof["derivationCount"],"uncertainty":proof["uncertainty"]}
 if "compiled" in report:
  c=report["compiled"];result.update(compilationStatus=c["status"],compilationOrigins=origins(c))
  if c["status"]=="viable":
   g=c["generation"];s=g.get("semantic",g.get("semantics"));result.update(active=sorted(g["activeMappings"]),inactive=g["inactiveMappings"],uncertainty=sorted(s["uncertainty"],key=lambda u:u["mapping"]))
 if "projected" in report:
  p=report["projected"];result.update(projectionStatus=p["status"],projectionOrigins=origins(p))
  if p["status"]=="projected":
   p=p["projection"];s=p.get("semantic",p.get("semantics"));risk=copy.deepcopy(s["risk"])
   if risk["budget"]:risk["budget"].pop("digest")
   result.update(bindings=[{"subject":e["subject"],"slots":[{"name":s["name"],"relation":s["relation"],"direction":s["direction"],"cardinality":s["cardinality"],"mappings":sorted(s["mappings"]),"targets":s["targets"]} for s in sorted(e["slots"],key=lambda s:s["name"])]} for e in p["entries"]],usedMappings=s["usedMappings"],risk=risk,dependencies=[{"mapping":d["mapping"],"premises":d["premises"],"derived":bool(d.get("derivation"))} for d in s["dependencies"]])
 if "tree" in report:
  t=report["tree"];result.update(treeStatus=t["status"],treeOrigins=origins(t))
  if t["status"]=="projected":
   t=t["pathTree"];result["tree"]={key:t[key] for key in ["tree","delimiter","attribute","params"]}
 result["finalStatus"]=result.get("treeStatus",result.get("projectionStatus",result.get("compilationStatus",result["proposalStatus"])))
 return result

with tempfile.TemporaryDirectory(prefix="patamaps-semantic-reference-") as directory:
 work=Path(directory);checkout=work/"reference";checkout.mkdir();archive=work/"reference.tar"
 run(["git","-C",args.reference,"archive",ENGINE,"--output",archive],ROOT)
 with tarfile.open(archive) as tar:tar.extractall(checkout,filter="data")
 (checkout/"node_modules").symlink_to(args.reference.resolve()/"node_modules",target_is_directory=True)
 run([args.node,checkout/"node_modules/typescript/lib/tsc.js","-p","tsconfig.build.json"],checkout)
 case_file=work/"cases.json";case_file.write_text(json.dumps(cases));reference=json.loads(run([args.node,ROOT/"scripts/reference/evaluate_semantic.mjs",checkout,case_file],ROOT))
 rust=[];comparisons=[]
 for v,legacy in zip(cases,reference,strict=True):
  g,p,request,spec,pack=copy.deepcopy(v["graph"]),copy.deepcopy(v["policy"]),copy.deepcopy(v["request"]),v["spec"],v["pack"]
  def write(name,value):file=work/(name+".json");file.write_text(json.dumps(value));return file
  write("graph",g);write("pack",pack);write("request",request)
  proposed=json.loads(run([args.cli.resolve(),"derive","graph.json","request.json","--relation-pack","pack.json"],work,(0,1)))
  actual={"id":v["id"],"proposed":proposed}
  if proposed["status"]=="proposed":
   g["mappings"].append(proposed["mapping"]);p["semantics"]["derivations"]=[proposed["derivation"]];p["semantics"]["assessments"]=request["assessments"];p["evidence"]=request["evidence"];context=request["context"]
   if v["after"]=="stale-context":context={"environment":"changed"}
   if v["after"]=="changed-premise":g["mappings"][0]["provenance"]["confidence"]=0.8
   if v["after"]=="changed-evidence":p["evidence"][0]["producer"]="changed"
   if v["after"]=="missing-proof":p["semantics"]["derivations"]=[]
   for name,value in [("graph",g),("policy",p),("spec",spec),("context",context)]:write(name,value)
   common=[args.cli.resolve(),"compile","graph.json","policy.json","--relation-pack","pack.json","--context","context.json","--as-of",v["evaluatedAt"]]
   generation=json.loads(run(common,work,(0,1)));actual["compiled"]=generation if generation.get("status")=="rejected" else {"status":"viable","issues":[],"generation":generation}
   if actual["compiled"]["status"]=="viable":
    result=json.loads(run([args.cli.resolve(),"link","graph.json","policy.json","spec.json",*common[4:]],work,(0,1)));actual["projected"]=result if result.get("status")=="rejected" else {"status":"projected","issues":[],"projection":result}
    if actual["projected"]["status"]=="projected" and "pathTree" in spec:
     result=json.loads(run([args.cli.resolve(),"path-tree","graph.json","policy.json","spec.json",*common[4:]],work,(0,1)));actual["tree"]=result if result.get("status")=="rejected" else {"status":"projected","issues":[],"pathTree":result}
  a,b=normalized(legacy),normalized(actual);passed=a==b and a["finalStatus"]==v["expected"]
  comparisons.append({"id":v["id"],"expected":v["expected"],"pass":passed,"reference":a,"successor":b});rust.append(actual)
 report={"engineRevision":ENGINE,"comparisonContract":"D001: declared draft envelopes and content addresses differ. Compare fixed expected decisions, all issue codes/subjects (proof subjects by stable result identity), full result mapping/provenance, ordered premises, rule/pack identity/version, context/digest, dependency identities, depth/count, six-dimensional uncertainty, projection metadata/roles/cardinality, complete used closure and risk accounting. Full engine records are retained.","cases":cases,"referenceOutputs":reference,"successorOutputs":rust,"comparisons":comparisons}
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 failures=[v["id"] for v in comparisons if not v["pass"]]
 assert not failures,f"Semantic disagreements: {failures}; inspect {args.output}"
 print(f"PASS: {len(cases)} independently declared law, uncertainty and budget cases against isolated reference {ENGINE}; complete records in {args.output}")
