"""Pinned owner-specific dynamic-route witnesses; native observations stay opaque."""
import hashlib
from pathlib import Path

SOURCE_BLOBS={'app/(chat)/chat/[id]/page.tsx': '67e08591353b913c179399d9e4808e69c5f36df5', 'components/chat/shell.tsx': '53c55676fe767b4bbfe30765cc9c360c64592f99', 'hooks/use-active-chat.tsx': 'f3b9522f7fcf900416ce073f79ca5a6164826a1d', 'app/(chat)/api/messages/route.ts': '60de354e9af1ba60f8f9709b54f1de8bfa901df7', 'app/(chat)/api/chat/[id]/stream/route.ts': '3713ec5dac7673cbc37a056cbb1b433f0cb81550', 'lib/db/schema.ts': '82d0ca04aa55a270c18d0bccd7f46442bcac9817', 'components/chat/message.tsx': '227c42ef2ff1477631fee063fb4615250b57248d', 'components/chat/multimodal-input.tsx': '987aefa66617eee567da4f5f9e70c2ca818ce887', 'hooks/use-auto-resume.ts': 'de6092e6f46b932881c359bb664c76b8fb60469f'}
DYNAMIC_CONTROLS=frozenset(['dynamic-owner-private-page-and-id-bound-data', 'dynamic-owner-second-id-replaces-visible-data', 'dynamic-cross-user-public-page-readonly', 'dynamic-cross-user-private-data-refusal', 'dynamic-guest-public-page-readonly', 'dynamic-guest-private-data-refusal', 'dynamic-unseen-id-empty-response', 'dynamic-missing-chat-id-query-refusal', 'dynamic-extra-page-segment-refusal', 'dynamic-stream-route-204', 'dynamic-stream-post-method-refusal', 'dynamic-stream-extra-segment-refusal', 'dynamic-fixtures-unchanged-and-no-generation'])
MODULES={
 '/chat/[id]':('dynamic','/(chat)/chat/[id]/page','app/(chat)/chat/[id]/page.js'),
 '/api/chat/[id]/stream':('dynamic','/(chat)/api/chat/[id]/stream/route','app/(chat)/api/chat/[id]/stream/route.js'),
 '/api/messages':('static','/(chat)/api/messages/route','app/(chat)/api/messages/route.js'),
}

def validate_mode(*,runtime,rewrites=False,standalone=False,retained=False,installed=False):
 assert runtime and not any([rewrites,standalone,retained,installed]),'DYNAMIC_QUALIFICATION_PROFILE'

def verify_sources(owner):
 owner=Path(owner);result={}
 for name,expected in SOURCE_BLOBS.items():
  path=owner/name
  assert path.is_file() and not path.is_symlink() and path.stat().st_size<=128*1024,'DYNAMIC_OWNER_SOURCE_FILE'
  raw=path.read_bytes();actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  assert actual==expected,'DYNAMIC_OWNER_SOURCE_CHANGED'
  result[name]=actual
 return dict(profile='patamaps-pinned-dynamic-source-1',sourceFiles=len(result),gitBlobs=result,sourceMutated=False)

def verify_compiled(observed):
 shard=observed['shard'];meta=shard['metadata']['observation']
 assert meta['frameworkVersionDeclared']=='16.2.10' and meta['runtimeEstablished'] is False and meta['regexExecuted'] is False,'DYNAMIC_NATIVE_OBSERVATION_SCOPE'
 bindings=[]
 for route_path,(category,app_path,module_file) in MODULES.items():
  routes=[e for e in shard['entities'] if e['kind']=='next-build-route' and e.get('attributes',{}).get('page')==route_path]
  modules=[e for e in shard['entities'] if e['kind']=='next-build-module' and e.get('attributes',{}).get('routePath')==route_path]
  assert len(routes)==len(modules)==1,'DYNAMIC_NATIVE_REQUIRED_BINDING'
  route,module=routes[0],modules[0];a,b=route['attributes'],module['attributes']
  assert a['category']==category and a['regexExecuted'] is False and a['httpMethods']=='not-observed','DYNAMIC_NATIVE_ROUTE_CLASSIFICATION'
  assert b['appPath']==app_path and b['moduleFile']==module_file and b['routePathOrigin']=='captured-app-path-routes-manifest','DYNAMIC_NATIVE_MODULE_BINDING'
  assert b['httpMethods']=='not-observed' and b['businessCorrespondence']=='not-inferred','DYNAMIC_NATIVE_METHOD_OR_SEMANTICS'
  bindings.append(dict(routePath=route_path,category=category,appPath=app_path,moduleFile=module_file,routeEntity=route['id'],moduleEntity=module['id']))
 return dict(profile='patamaps-pinned-dynamic-build-bindings-1',frameworkVersion='16.2.10',bindings=bindings,regexExecuted=False,nativeRuntimeClaim=False,runtimeWitnessRequired=True)
