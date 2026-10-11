"""Generate unpublished governance schemas; never touch reference artifacts."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMAS=ROOT/'schemas'
def uri(name):return 'urn:patamaps:draft:1:schema:'+name
def save(name,value):
 value={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':uri(name),**value}
 (SCHEMAS/(name+'.schema.json')).write_text(json.dumps(value,indent=2)+'\n')
def obj(properties,optional=()):return {'type':'object','additionalProperties':False,'properties':properties,'required':[k for k in properties if k not in optional]}
def arr(value,maximum=100000,minimum=0):return {'type':'array','items':value,'minItems':minimum,'maxItems':maximum}
def ref(name):return {'$ref':uri('governance')+'#/$defs/'+name}
def nullable(value):return {'oneOf':[value,{'type':'null'}]}
def header(kind,profile=False):return {'schemaVersion':{'const':'0.1.0'},'documentType':{'const':kind},**({'profile':{'const':'patamaps-governance-draft-1'}} if profile else {})}
text={'type':'string','minLength':1,'maxLength':1024,'pattern':'^[^\u0000-\u001f\u007f-\u009f]+$'}
identifier={'type':'string','pattern':r'^[A-Za-z][A-Za-z0-9+.-]*:\S+$'}
digest={'type':'string','pattern':'^sha256:[a-f0-9]{64}$'}
timestamp={'type':'string','format':'date-time','pattern':r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$'}
integer={'type':'integer','minimum':0,'maximum':9007199254740991}
boolean={'type':'boolean'}
actions={'enum':['activate','bootstrap','rollback','rebind-implementation','change-graph','change-authority','change-policy','relax-policy','raise-budget','add-waiver','change-law','change-source','change-context','change-projection']}
binding=obj({'id':identifier,'digest':digest})
trust_binding=obj({'id':identifier,'revision':text,'digest':digest})
scope=obj({'subject':text,'fact':text})
requirement=obj({'action':actions,'subject':text,'fact':text})
principal=obj({'id':text,'role':{'enum':['owner','agent','service']},'revoked':boolean})
key=obj({'id':text,'principal':text,'algorithm':{'const':'Ed25519'},'publicKey':{'type':'string','minLength':60,'maxLength':60,'pattern':'^[A-Za-z0-9+/]{59}=$'},'validFrom':timestamp,'validUntil':timestamp,'revoked':boolean})
grant=obj({'id':text,'principal':text,'actions':{**arr(actions,14,1),'uniqueItems':True},'scopes':{**arr(scope,128,1),'uniqueItems':True},'validFrom':timestamp,'validUntil':timestamp,'revoked':boolean})
deployment_path={'type':'string','minLength':2,'maxLength':4096,'pattern':r'^/(?!.*(?:/\.\.?(?:/|$)|//))[^\u0000-\u001f\u007f-\u009f/](?:[^\u0000-\u001f\u007f-\u009f]*[^/])?$'}
deployment=obj({'profile':{'const':'patamaps-linux-root-draft-1'},'stateDirectory':deployment_path,'proposalRoots':{**arr(deployment_path,128,1),'uniqueItems':True}})
trust=obj({**header('trusted-consumer'),'mode':{'const':'governed'},'id':identifier,'revision':text,'consumer':identifier,'environment':text,'principals':arr(principal,1024,1),'keys':arr(key,4096),'grants':arr(grant,4096),'deployment':deployment},['deployment'])
source=obj({'id':identifier,'locator':identifier,'digest':digest,'byteLength':integer,'content':{'type':'string'}},['content'])
# Capture inputs may record semantically rejected data. Their strict DTO shape
# and decisions are checked by the Rust parser/evaluator, never by this schema.
capture_inputs=obj({'graph':{'type':'object'},'packs':arr({'type':'object'},64),'policy':{'type':'object'},'context':{'type':'object'},'evaluatedAt':{'type':'string'},'projectionSpec':{'$ref':uri('projection-spec')}},['projectionSpec'])
capture=obj({**header('capture'),'profile':{'enum':['patamaps-routing-draft-1','patamaps-semantic-draft-1']},'executor':digest,'id':identifier,'digest':digest,'inputs':capture_inputs,'sources':arr(source,1024),'result':{'type':'object'}})
emission=obj({'projection':identifier,'language':{'enum':['rust','typescript']},'bindingSlot':text},['bindingSlot'])
candidate=obj({'captures':arr({'$ref':uri('capture')},16,1),'emissions':arr(emission,32)})
path={'type':'string','pattern':r'^(?:graph\.json|policy\.json|relation-packs\.json|source-receipts\.json|generation\.json|(?:capture|projection|path-tree)-\d+\.json|bindings-\d+\.(?:rs|ts))$'}
file=obj({'path':path,'mediaType':{'enum':['application/json','text/typescript','text/rust']},'byteDigest':digest,'byteLength':integer})
manifest=obj({**header('artifact-manifest',True),'id':identifier,'digest':digest,'consumer':identifier,'environment':text,'captures':arr(binding,16,1),'files':arr(file,128,1)})
baseline=obj({'manifestDigest':digest,'candidate':ref('candidate')})
proposal=obj({**header('change-proposal',True),'engine':digest,'id':identifier,'digest':digest,'consumer':identifier,'environment':text,'intent':{'enum':['deploy','rollback']},'proposer':text,'trust':trust_binding,'baseline':nullable(ref('baseline')),'candidate':ref('candidate'),'artifacts':ref('manifest'),'requirements':arr(requirement,100000,1)})
payload=obj({'domain':{'const':'urn:patamaps:approval:draft:1'},'schemaVersion':{'const':'0.1.0'},'algorithm':{'const':'Ed25519'},'profile':{'const':'patamaps-governance-draft-1'},'engine':digest,'proposal':binding,'artifacts':binding,'baseline':nullable(digest),'consumer':identifier,'environment':text,'intent':{'enum':['deploy','rollback']},'trust':trust_binding,'principal':text,'key':text,'grants':{**arr(text,4096,1),'uniqueItems':True},'requirements':arr(requirement,100000,1),'issuedAt':timestamp,'expiresAt':timestamp})
approval=obj({**header('approval'),'id':identifier,'digest':digest,'payload':ref('payload'),'signature':{'type':'string','minLength':88,'maxLength':88,'pattern':'^[A-Za-z0-9+/]{86}==$'}})
prepared=obj({**header('prepared-candidate'),'proposal':ref('proposal'),'files':{'type':'object','propertyNames':path,'additionalProperties':{'type':'string'},'minProperties':1,'maxProperties':128}})
definitions={'candidate':candidate,'baseline':baseline,'manifest':manifest,'proposal':proposal,'payload':payload,'approval':approval,'prepared':prepared,'trust':trust}
save('governance',{'$defs':definitions})
save('capture',capture)
for name,definition in [('trusted-consumer','trust'),('artifact-manifest','manifest'),('change-proposal','proposal'),('approval-payload','payload'),('approval','approval'),('prepared-candidate','prepared')]:save(name,ref(definition))
activation_request=obj({**header('activation-request'),'prepared':ref('prepared'),'approval':ref('approval')})
activation_manifest=obj({**header('activation-manifest'),'profile':{'const':'patamaps-linux-root-draft-1'},'id':identifier,'digest':digest,'consumer':identifier,'environment':text,'proposal':ref('proposal'),'approval':ref('approval'),'acceptedTrust':ref('trust'),'previousManifest':nullable(digest),'authorizedAt':timestamp})
active_pointer=obj({**header('active-pointer'),'consumer':identifier,'environment':text,'manifest':binding})
for name,value in [('activation-request',activation_request),('activation-manifest',activation_manifest),('active-pointer',active_pointer)]:save(name,value)
projection=json.loads((SCHEMAS/'projection-spec.schema.json').read_text());projection['properties']['consumer']={'$ref':'#/$defs/identifier'};save('projection-spec',projection)
print('Generated local Draft 1 capture/governance schemas; original reference artifacts unchanged.')
