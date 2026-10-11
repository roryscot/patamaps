"""Extend only unpublished successor schemas from byte-preserved reference defs.

This never modifies fixtures/reference or substitutes schema checks for kernel
admission. Invalid captured inputs remain evidence, not validated capabilities.
"""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMAS=ROOT/"schemas"
REF=ROOT/"fixtures/reference/schemas"
def read(path):return json.loads(path.read_text())
def save(name,value):(SCHEMAS/(name+".schema.json")).write_text(json.dumps(value,indent=2)+"\n")
def uri(name):return "urn:patamaps:draft:1:schema:"+name
def replace(value):
 if isinstance(value,list):return [replace(v) for v in value]
 if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
 if isinstance(value,str):
  for old,new in [("metamap-graph","graph"),("metamap-graph/v2","graph"),("metamap-viability","policy"),("metamap-viability-v2","semantic-policy"),("metamap-derivation","derivation")]:
   if value.startswith("https://") and value.split("#")[0].endswith("/"+old+".schema.json"):
    return uri(new)+(('#'+value.split('#',1)[1]) if '#' in value else '')
 return value
pack=read(SCHEMAS/"relation-pack.schema.json")
executable=read(REF/"relation-pack-v2.schema.json")
pack['$defs']=copy.deepcopy(executable['$defs']);pack['properties'].update({k:copy.deepcopy(executable['properties'][k]) for k in ['imports','laws']});save('relation-pack',pack)
proof=replace(read(REF/"metamap-derivation.schema.json"));proof['$id']=uri('derivation');proof['properties']['schemaVersion']={'const':'0.1.0'};proof['properties'].pop('$schema',None);proof['properties']['documentType']={'const':'derivation'};proof['required']=[k for k in proof['required'] if k!='$schema']+['documentType'];save('derivation',proof)
request=replace(read(REF/"metamap-composition-request.schema.json"));request['$id']=uri('composition-request');request['properties']['schemaVersion']={'const':'0.1.0'};request['properties']['documentType']={'const':'composition-request'};request['required'].append('documentType');save('composition-request',request)
legacy=replace(read(REF/"metamap-viability-v2.schema.json"))
defs=legacy['$defs']
sem={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':uri('semantic-policy'),'type':'object','additionalProperties':False,'required':['interpretation','derivations','derivationLimits','assessments','uncertaintyRequirements','riskBudgets'],'properties':{'interpretation':{'const':'declared-law-application'},**{k:legacy['properties'][k] for k in ['derivations','derivationLimits','assessments','uncertaintyRequirements','riskBudgets']}},'$defs':defs}
save('semantic-policy',sem)
policy=read(SCHEMAS/'policy.schema.json');policy['properties']['semantics']={'$ref':uri('semantic-policy')};save('policy',policy)
projection=read(SCHEMAS/'projection-spec.schema.json')
old=read(REF/'metamap-projection-spec.schema.json')
projection['properties']['pathTree']=old['properties']['pathTree'];projection['properties']['metadata']=old['properties']['metadata']
projection['properties']['consumer']={'$ref':'#/$defs/identifier'}
projection['$defs']['pathTree']=old['$defs']['pathTree']
projection['properties']['semantics']={'type':'object','additionalProperties':False,'required':['consumer','budget'],'properties':{'consumer':{'$ref':'#/$defs/identifier'},'budget':{'oneOf':[{'$ref':'#/$defs/identifier'},{'type':'null'}]}}};save('projection-spec',projection)
print('Extended successor law, derivation, semantic-policy and projection schemas; original reference schemas preserved.')
