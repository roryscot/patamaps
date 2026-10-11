"""Generate closed draft workspace/process shapes; semantic checks stay native."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
uri = lambda name: "urn:patamaps:draft:1:schema:" + name
def obj(properties, optional=()):
    return {"type":"object", "additionalProperties":False, "properties":properties, "required":[k for k in properties if k not in optional]}
def arr(value, maximum, minimum=0):
    return {"type":"array", "items":value, "maxItems":maximum, "minItems":minimum}
def header(kind):
    return {"schemaVersion":{"const":"0.1.0"}, "documentType":{"const":kind}}
def save(name, value):
    (ROOT / "schemas" / (name + ".schema.json")).write_text(json.dumps({"$schema":"https://json-schema.org/draft/2020-12/schema", "$id":uri(name), **value}, indent=2) + "\n")
text = {"type":"string"}
digest = {"type":"string", "pattern":"^sha256:[a-f0-9]{64}$"}
safe = {"type":"integer", "minimum":0, "maximum":9007199254740991}
metadata = {"type":"object"}
bounds = obj({"maximumElapsedMs":{**safe,"minimum":1,"maximum":60000}, "maximumStdoutBytes":{**safe,"minimum":1,"maximum":16777216}, "maximumStderrBytes":{**safe,"minimum":1,"maximum":65536}})
invocation = obj({"executable":text,"arguments":arr(text,128),"codeInputs":arr(text,128),"bounds":bounds})
source = {"oneOf":[obj({"id":text,"adapter":{"const":"portable-shard"},"path":text}),obj({"id":text,"adapter":{"const":"process"},"invocation":invocation,"inputs":arr(text,1024,1),"config":metadata})]}
emission = obj({"path":text,"language":{"enum":["json","rust","typescript"]},"bindingSlot":text},["bindingSlot"])
config = obj({**header("workspace-config"),"id":text,"namespace":text,"revision":text,"sources":arr(source,64,1),"packs":arr(text,64),"policy":text,"projections":arr(obj({"path":text,"emissions":arr(emission,32)}),16,1),"context":metadata,"evaluatedAt":text})
receipt = obj({"path":text,"digest":digest,"byteLength":safe})
diagnostic = obj({"severity":{"enum":["warning","error"]},"code":text,"message":text})
profile = {"const":"patamaps-workspace-draft-1"}
save("workspace-config", config)
save("adapter-request", obj({**header("adapter-request"),"profile":profile,"sourceId":text,"namespace":text,"config":metadata,"inputs":arr(obj({"receipt":receipt,"content":text}),1024),"invocationDigest":digest,"requestDigest":digest}))
save("adapter-response", obj({**header("adapter-response"),"profile":profile,"sourceId":text,"adapterVersion":text,"requestDigest":digest,"inputs":arr(receipt,1024),"shard":{"$ref":uri("graph")},"diagnostics":arr(diagnostic,1024)}))
discovery = obj({"sourceId":text,"adapter":text,"adapterVersion":text,"requestDigest":digest,"shardDigest":digest,"shard":{"$ref":uri("graph")},"diagnostics":arr(diagnostic,1024)})
save("workspace-baseline", obj({**header("workspace-baseline"),"profile":profile,"executor":digest,"workspaceExecutor":digest,"configDigest":digest,"config":{"$ref":uri("workspace-config")},"discovery":arr(discovery,64),"captures":arr({"$ref":uri("capture")},16,1),"outputs":{"type":"object","additionalProperties":text,"maxProperties":32},"digest":digest}))
print("Generated closed draft workspace and adapter schemas.")
