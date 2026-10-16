"""Independent compilation and wire controls for the JSON DTO HTTP profile.

This is a contract generator regression, not existing-project qualification.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import time

DIALECT="https://json-schema.org/draft/2020-12/schema"
REQUEST={
 "$schema":DIALECT,"$defs":{"Address":{"type":"object","additionalProperties":False,
  "properties":{"label":{"type":"string","minLength":1,"maxLength":5},"active":{"type":"boolean"}},
  "required":["label","active"]}},
 "type":"object","additionalProperties":False,
 "properties":{
  "name":{"type":"string","minLength":1,"maxLength":80},
  "count":{"type":"integer","format":"uint32","minimum":0,"maximum":100},
  "address":{"$ref":"#/$defs/Address"},
  "tags":{"type":"array","minItems":1,"maxItems":3,"items":{"type":"string","enum":["read","write"]}},
  "note":{"type":["string","null"],"maxLength":20},
  "metadata":{},
  "choice":{"oneOf":[
   {"type":"object","additionalProperties":False,"properties":{"kind":{"type":"string","const":"basic"},"code":{"type":"string"}},"required":["kind","code"]},
   {"type":"object","additionalProperties":False,"properties":{"kind":{"type":"string","const":"premium"},"rate":{"type":"number","minimum":0,"maximum":1}},"required":["kind","rate"]}]}
 },
 "required":["name","count","address","tags","choice"]
}
HANDLER=r'''
use serde::{Deserialize, Serialize};
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Address { pub label: String, pub active: bool }
#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all="lowercase")]
pub enum Tag { Read, Write }
#[derive(Debug, Deserialize, Serialize)]
#[serde(tag="kind", rename_all="lowercase", deny_unknown_fields)]
pub enum Choice { Basic { code: String }, Premium { rate: f64 } }
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CreateItemRequest {
 pub name: String, pub count: u32, pub address: Address, pub tags: Vec<Tag>,
 pub note: Option<String>, pub metadata: Option<serde_json::Value>, pub choice: Choice
}
#[derive(Debug, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CreateItemResponse { pub accepted: bool, pub payload: CreateItemRequest }
#[derive(Debug)]
pub enum OperationError { InvalidName, BackendFailure }
pub fn create_item(input: CreateItemRequest) -> Result<CreateItemResponse, OperationError> {
 if input.name.is_empty() { return Err(OperationError::InvalidName); }
 if input.name=="fail" { return Err(OperationError::BackendFailure); }
 Ok(CreateItemResponse { accepted:true,payload:input })
}
'''

def verify(root,work,env,run):
    fixture=root/"examples/cross-stack"
    cli=root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    node=Path(env["PATAMAPS_DEV_NODE"])
    spec=importlib.util.spec_from_file_location("http_json_build",fixture/"build.py")
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    state=work/"json-http"
    state.mkdir()
    target=root/".tools/project-adoption/g2-service-target"
    base={"name":"Widget","count":1,"address":{"label":"😀é","active":True},"tags":["read"],"choice":{"kind":"basic","code":"ok"}}
    vectors=[]
    def vector(label,path=None,value=None,valid=False,body=None,status=None,raw=None):
        data=copy.deepcopy(base if body is None else body)
        if path is not None:
            parent=data
            for k in path[:-1]:parent=parent[k]
            if value is ...:del parent[path[-1]]
            else:parent[path[-1]]=value
        vectors.append(dict(label=label,body=data,valid=valid,status=status if status is not None else (201 if valid else 400),raw=raw))
    vector("nested-array-enum-positive",valid=True)
    vector("optional-null",["note"],None,True)
    vector("optional-string",["note"],"hello",True)
    vector("premium",["choice"],{"kind":"premium","rate":0.25},True)
    vector("uint32-zero",["count"],0,True)
    vector("number-negative-zero",["choice"],{"kind":"premium","rate":-0.0},True,raw=json.dumps({**base,"choice":{"kind":"premium","rate":-0.0}}))
    vector("integer-floating-lexeme",valid=True,raw=json.dumps(base).replace('"count": 1','"count": 1.0'))
    vector("integer-exponent-lexeme",valid=True,raw=json.dumps(base).replace('"count": 1','"count": 1e0'))
    vector("missing-required",["count"],...)
    vector("fractional-integer",["count"],1.5)
    vector("negative-unsigned",["count"],-1)
    vector("maximum",["count"],101)
    vector("unsafe-integer",["count"],9007199254740992)
    vector("wrong-nested-type",["address","active"],"true")
    vector("nested-extra",["address","extra"],1)
    vector("unicode-scalar-limit",["address","label"],"😀"*6)
    vector("empty-array",["tags"],[])
    vector("array-limit",["tags"],["read"]*4)
    vector("enum-refusal",["tags"],["admin"])
    vector("optional-type",["note"],False)
    vector("union-tag",["choice"],{"kind":"unknown","code":"ok"})
    vector("union-extra",["choice"],{"kind":"basic","code":"ok","rate":0.5})
    vector("numeric-bound",["choice"],{"kind":"premium","rate":1.5})
    vector("backend-error",["name"],"fail",True,status=500)
    nested={}
    for _ in range(70):nested={"nested":nested}
    vector("transport-depth",["metadata"],nested)
    (state/"vectors.json").write_text(json.dumps(vectors,ensure_ascii=False,indent=2)+"\n")
    controls=[]

    def command(label,argv,**kwargs):
        prior=dict(env)
        try:
            env.update(CARGO_TARGET_DIR=str(target),CARGO_PROFILE_DEV_DEBUG="0",CARGO_PROFILE_TEST_DEBUG="0")
            return run("json2-"+label,argv,**kwargs)
        finally:env.clear();env.update(prior)

    def candidate(label,ambiguous=False):
        app=state/label
        builder.snapshot(fixture,app)
        request=copy.deepcopy(REQUEST)
        if ambiguous:request["properties"]["choice"]["oneOf"]=[request["properties"]["choice"]["oneOf"][0]]*2
        response_request={k:v for k,v in REQUEST.items() if k not in {"$schema","$defs"}}
        response={"$schema":DIALECT,"$defs":REQUEST["$defs"],"type":"object","additionalProperties":False,
                  "properties":{"accepted":{"type":"boolean"},"payload":response_request},"required":["accepted","payload"]}
        (app/"contracts/create-item.request.schema.json").write_text(json.dumps(request)+"\n")
        (app/"contracts/create-item.response.schema.json").write_text(json.dumps(response)+"\n")
        (app/"service/src/handlers/create_item.rs").write_text(HANDLER)
        owner=json.loads((app/"contracts/operations.json").read_bytes())
        owner["operations"][0]["httpProfile"]="patamaps-http-json-2"
        (app/"contracts/operations.json").write_text(json.dumps(owner)+"\n")
        def emit(name,argv,**kwargs):return command(label+"-"+name,argv,**kwargs)
        generated=builder.generate(app,cli,emit)
        command(label+"-cargo",["cargo","build","--manifest-path",app/"service/Cargo.toml","--locked","--offline"])
        executable=app/"service.native"
        shutil.copy2(target/"debug/catalog-service",executable)
        typed=app/"web/generated/client-types.ts"
        typed.write_text("import {callOperation, type Requests} from './operations';\nconst id='urn:example:operation:create-item';\nconst input: Requests[typeof id] = "+json.dumps(base,ensure_ascii=False)+";\nexport const invoke = () => callOperation(id,input);\n")
        for bad_label,property_name,bad_value in [("count","count","one"),("enum","tags",["admin"])]:
            invalid=copy.deepcopy(base);invalid[property_name]=bad_value
            invalid_path=app/("web/generated/bad-"+bad_label+".ts")
            invalid_path.write_text("import {type Requests} from './operations';\nconst input: Requests['urn:example:operation:create-item'] = "+json.dumps(invalid,ensure_ascii=False)+";\nexport {input};\n")
            diagnostics=command(label+"-typescript-refuse-"+bad_label,[node,fixture/"web/node_modules/typescript/lib/tsc.js","--target","ES2022","--module","commonjs","--lib","ES2022,DOM","--strict","--skipLibCheck","--noEmit",invalid_path],expected_success=False)
            assert b"TS2322" in diagnostics
            controls.append(dict(label=label+"-typescript-refuse-"+bad_label,stage="typescript",result="refused",code="TS2322"))
        client=app/"client"
        command(label+"-typescript",[node,fixture/"web/node_modules/typescript/lib/tsc.js","--target","ES2022","--module","commonjs","--lib","ES2022,DOM","--strict","--skipLibCheck","--outDir",client,app/"web/generated/operations.ts",typed])
        (app/"client-check.cjs").write_text(r'''
const fs=require('node:fs');
const api=require(process.argv[2]);
const cases=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const id='urn:example:operation:create-item';
(async()=>{
 const rows=[];
 for(const test of cases){
  const valid=api.validRequest(id,test.body);
  if(valid!==test.valid) throw new Error(test.label+': request validator '+valid);
  const response=await fetch(process.argv[4]+'/items',{method:'POST',headers:{'content-type':'application/json'},body:test.raw??JSON.stringify(test.body)});
  const body=await response.json();
  if(response.status!==test.status) throw new Error(test.label+': wire status '+response.status+' '+JSON.stringify(body));
  if(response.status===201 && (!api.validResponse(id,body) || body.payload.count!==test.body.count)) throw new Error(test.label+': response mismatch');
  if(test.label==='number-negative-zero' && !Object.is(body.payload.choice.rate,-0))throw new Error('floating negative zero changed');
  if(response.status===201){
   const call=await api.callOperation(id,test.body,{base:process.argv[4],endpoint:'backend'});
   if(call.status!==201) throw new Error(test.label+': generated client status');
  }
  rows.push({label:test.label,requestValid:valid,status:response.status});
 }
 const good=cases[0].body;
 for(const [label,bad] of [['NaN',{...good,metadata:NaN}],['undefined',{...good,metadata:undefined}],['sparse',{...good,metadata:Array(2)}],['surrogate',{...good,metadata:'\ud800'}],['unsafe-number',{...good,metadata:9007199254740992}]]){
  if(api.validRequest(id,bad))throw new Error(label+': non-JSON value accepted');
  rows.push({label,requestValid:false,wire:'not-sent'});
 }
 const cycle={};cycle.self=cycle;
 if(api.validRequest(id,{...good,metadata:cycle}))throw new Error('cyclic value accepted');
 rows.push({label:'cycle',requestValid:false,wire:'not-sent'});
 console.log(JSON.stringify(rows));
})().catch(e=>{console.error(e);process.exitCode=1;});
''')
        selected_vectors=vectors if not ambiguous else [dict(label="one-of-ambiguity",body=base,valid=False,status=400,raw=None)]
        vector_path=app/"vectors.json";vector_path.write_text(json.dumps(selected_vectors,ensure_ascii=False)+"\n")
        out=app/"service.stdout.log"
        with out.open("xb") as stdout,(app/"service.stderr.log").open("xb") as stderr:
            process=subprocess.Popen([str(executable),str(app/"config/service.toml"),"127.0.0.1:0"],stdout=stdout,stderr=stderr,start_new_session=True,env=env)
            try:
                deadline=time.monotonic()+15
                while True:
                    address=next((line.removeprefix("LISTEN ") for line in out.read_text().splitlines() if line.startswith("LISTEN 127.0.0.1:")),None)
                    if address:break
                    if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError("JSON DTO service did not start")
                    time.sleep(.05)
                rows=json.loads(command(label+"-wire",[node,app/"client-check.cjs",client/"operations.js",vector_path,"http://"+address]))
            finally:
                from cross_stack_bindings import stop
                stop(process)
        controls.extend(rows)
        assert all(builder.digest(builder.owned(app,p).read_bytes())==d for p,d in generated["sourceBytes"].items())
        return generated

    generated=candidate("rich-dto")
    candidate("ambiguous-union",True)
    receipt=dict(status="passed-json-dto-contract-regressions",profile="patamaps-http-json-2",controls=controls,
                 generated=generated,fullWorkflowAccepted=False,existingProjectQualification="not-performed",
                 framework="sync-typed-dispatch",axum="not-performed",activation="not-performed")
    (state/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt
