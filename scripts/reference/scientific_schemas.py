"""Draft transports for native scientific ingress and closed evidence packages."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def obj(properties,required=None):return {'type':'object','additionalProperties':False,'properties':properties,'required':list(properties) if required is None else required}
def arr(items,maximum,minimum=0):return {'type':'array','items':items,'maxItems':maximum,'minItems':minimum}
text={'type':'string','maxLength':16777216};name={'type':'string','minLength':1,'maxLength':4096};mapping={'type':'object'}
def save(name,value):
    d={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:patamaps:draft:1:schema:'+name,**value}
    (ROOT/'schemas'/f'{name}.schema.json').write_text(json.dumps(d,indent=2)+'\n')
source=obj({'id':name,'namespace':name,'sourceRevision':name,'recordIdColumn':name,'provenance':mapping},['id','namespace','sourceRevision'])
document=obj({'schemaVersion':{'const':'1.0.0'},'profile':{'const':'sssom-1.0-entity-tsv'},'metadata':mapping,'columns':{**arr(name,256,1),'uniqueItems':True},'rows':arr(arr(text,256,1),50000,1)})
external=obj({'id':name,'name':name,'description':name})
options=obj({'name':name,'description':name,'datePublished':{'type':'string','format':'date'},'consumer':name,'environment':name,'source':source,'tsvReceipt':name,'metadataReceipt':name,'externalSources':arr(external,64)},['name','description','datePublished','consumer','environment','source','tsvReceipt','externalSources'])
crate=obj({'metadata':mapping,'files':{'type':'object','minProperties':1,'maxProperties':256,'additionalProperties':text}})
for n,v in [('sssom-document',document),('sssom-source',source),('scientific-crate-options',options),('scientific-crate',crate)]:save(n,v)
print('Generated four closed draft scientific transports; unchanged pinned model validates effective SSSOM MappingSet independently.')
