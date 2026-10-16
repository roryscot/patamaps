"""Compiled Axum and HTTP transport controls; not existing-project qualification."""
from pathlib import Path
import copy
import hashlib
import json
import shutil
import subprocess
import time

DIALECT="https://json-schema.org/draft/2020-12/schema"
def schema(kind,**keywords):return {"$schema":DIALECT,"type":kind,**keywords}
def obj(properties,required=None):return schema("object",properties=properties,required=list(properties) if required is None else required,additionalProperties=False)
PROBLEM=obj({"error":{"type":"string","minLength":1},"issues":{"type":"array","maxItems":100,"items":{
 "type":"object","additionalProperties":False,"properties":{"path":{"type":"string"},"message":{"type":"string"}},"required":["path","message"]}}})
REPLY=obj({"state":{"type":"string"},"kind":{"type":"string"},"value":{"type":"string","maxLength":70000},
 "limit":{"type":["integer","null"],"format":"uint32"},"verbose":{"type":["boolean","null"]}})
EVALUATE=obj({"message":{"type":"string","maxLength":70000},"fail":{"type":"boolean"}},["message"])
REPLAY=obj({"expected_report":{"type":"string","maxLength":70000}})
SCALARS=obj({"uuid":{"type":"string","format":"uuid"},
 "quantity":{"type":"string","pattern":"^(0|[1-9][0-9]*)$"},
 "count":{"type":"integer","format":"uint64"},"delta":{"type":"integer","format":"int64"}})
HEALTH=obj({"ok":{"type":"boolean"}})
NULL=schema("null")
PREFIX="urn:transport:operation:"

def definitions():
    state={"extractor":"state","type":"Context"}
    output={"mode":"result-json","successType":"Fut","errorType":"Problem"}
    rows=[]
    for name,request,ty in [("evaluate",EVALUATE,"F"),("replay",REPLAY,"Replay")]:
        rows.append(dict(name=name,frontend={"method":"POST","path":"/api/evaluate"},
            backend={"method":"POST","path":"/"+name,"successStatus":200},handler=name,request=request,response=REPLY,
            arguments=[state,{"extractor":"json-result","type":ty}],output=output,frontendGroup="execution"))
    for method in ["GET","PUT","PATCH"]:
        rows.append(dict(name=method.lower()+"-item",frontend={"method":method,"path":"/api/items/:id"},
            backend={"method":method,"path":"/items/{id}","successStatus":200},handler="fetch_item",request=NULL,response=REPLY,
            arguments=[state,{"extractor":"path","type":"String"},{"extractor":"query","type":"Filter"},{"extractor":"headers"}],
            output=output,pathParameters=obj({"id":{"type":"string","minLength":1,"maxLength":256}}),
            queryParameters=obj({"limit":{"type":"integer","minimum":0,"maximum":10},"verbose":{"type":"boolean"}},[]),
            headerParameters=obj({"x-proof":{"type":"string","minLength":1,"maxLength":80}})))
    rows.append(dict(name="delete-item",frontend={"method":"DELETE","path":"/api/items/:id"},
        backend={"method":"DELETE","path":"/items/{id}","successStatus":204},handler="remove_item",request=NULL,response=NULL,
        arguments=[state,{"extractor":"path","type":"String"}],output={"mode":"native","successType":"StatusCode"},
        pathParameters=obj({"id":{"type":"string","minLength":1,"maxLength":256}}),errors=[]))
    for method in ["GET","HEAD","OPTIONS"]:
        rows.append(dict(name=method.lower()+"-health",frontend={"method":method,"path":"/api/health"},
            backend={"method":method,"path":"/health","successStatus":200},handler="health",request=NULL,
            response=NULL if method=="HEAD" else HEALTH,arguments=[],output={"mode":"json","successType":"serde_json::Value"}))
    rows.append(dict(name="scalars",frontend={"method":"POST","path":"/api/scalars"},
        backend={"method":"POST","path":"/scalars","successStatus":200},handler="scalars",request=SCALARS,response=SCALARS,
        arguments=[state,{"extractor":"json-result","type":"Scalars"}],
        output={"mode":"result-json","successType":"Scalars","errorType":"Problem"}))
    return rows

def verify(root,work,env,run):
    fixture=root/"examples/http-transport/service"
    cli=root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    node=Path(env["PATAMAPS_DEV_NODE"])
    compiler=root/"examples/cross-stack/web/node_modules/typescript/lib/tsc.js"
    state=work/"http-transport";state.mkdir()
    lock=(fixture/"Cargo.lock").read_bytes()
    (state/"dependency-lock.json").write_text(json.dumps({"sha256":hashlib.sha256(lock).hexdigest(),
        "trackedAtSourceRevision":subprocess.run(["git","ls-files","--error-unmatch","examples/http-transport/service/Cargo.lock"],cwd=root,capture_output=True).returncode==0},indent=2)+"\n")
    target=root/".tools/project-adoption/transport-target"
    controls=[]
    def save_controls():
        (state/"controls.json").write_text(json.dumps(dict(status="partial-until-final-receipt",controls=controls,fullWorkflowAccepted=False),indent=2)+"\n")
    save_controls()
    def command(label,argv,**kwargs):
        old=dict(env)
        try:
            env.update(CARGO_TARGET_DIR=str(target),CARGO_PROFILE_DEV_DEBUG="0",CARGO_PROFILE_TEST_DEBUG="0")
            return run("transport-"+label,argv,**kwargs)
        finally:env.clear();env.update(old)
    def prepare(label,mutation=None,refusal=None):
        app=state/label
        shutil.copytree(fixture,app,ignore=shutil.ignore_patterns("target"))
        definitions_rows=[copy.deepcopy(row) for row in definitions()]
        if mutation:mutation(definitions_rows)
        digest="sha256:"+hashlib.sha256((app/"src/api.rs").read_bytes()).hexdigest()
        graph=dict(schemaVersion="0.1.0",documentType="graph",id="urn:transport:graph",revision="1",namespace="transport-controls",
                   relationPacks=[{"id":"urn:metamap:relation-pack:core","version":"1.0.0"},{"id":"urn:metamap:relation-pack:routing","version":"1.0.0"}],
                   entities=[],mappings=[],authorities=[])
        policy=dict(schemaVersion="0.1.0",documentType="policy",id="urn:transport:policy",graph={"id":graph["id"],"revision":"1"},mappings=[],constraints=[],evidence=[])
        for row in definitions_rows:
            identity=PREFIX+row["name"]
            http=dict(profile="patamaps-http-transport-1",modulePath="src/api.rs",arguments=row["arguments"],output=row["output"],
                responseSchema=row["response"],errors=row.get("errors",[] if row["handler"]=="health" else [{"status":s,"schema":PROBLEM} for s in [400,413,422]]),
                limits={"requestBytes":65536,"responseBytes":16 if row["handler"]=="health" else 131072,"depth":64,"values":100000})
            for k in ["frontendGroup","pathParameters","queryParameters","headerParameters"]:
                if k in row:http[k]=row[k]
            graph["entities"].extend([
                {"id":identity,"kind":"routing:command","attributes":{"http":row["frontend"]}},
                {"id":identity+":handler","kind":"routing:handler","locators":[{"uri":"rust:crate::api::"+row["handler"],"digest":digest}],"attributes":{"http":http}},
                {"id":identity+":input","kind":"routing:schema","attributes":{"jsonSchema":row["request"]}},
                {"id":identity+":endpoint","kind":"routing:endpoint","attributes":{"http":row["backend"]}}])
            for slot,relation in [("handler","routing:handled_by"),("input","routing:accepts"),("endpoint","routing:exposed_as")]:
                mid=identity+":mapping:"+slot
                graph["mappings"].append(dict(id=mid,relation=relation,sources=[identity],targets=[identity+":"+slot],cardinality="one-to-one",lossiness="lossless",provenance={"status":"declared","assertedBy":"transport-fixture-owner"}))
                policy["mappings"].append(dict(mapping=mid,coverage="total",determinism="deterministic",reversibility="irreversible"))
                for kind in ["core:requires-mapping","core:unique-target"]:
                    policy["constraints"].append(dict(id=mid+":"+kind,kind=kind,subjects=[identity],parameters={"relation":relation,"direction":"source"}))
            graph["authorities"].append(dict(id=identity+":authority",concept=identity,source=identity,facts=["transport-identity"],mode="canonical",provenance={"status":"declared","assertedBy":"transport-fixture-owner"}))
        projection=dict(schemaVersion="0.1.0",documentType="projection-spec",id="urn:transport:projection",
            select={"ids":[PREFIX+row["name"] for row in definitions_rows]},
            slots=[dict(name=slot,relation=relation,direction="outgoing",cardinality="exactly-one",targetKinds=[kind])
                for slot,relation,kind in [("handler","routing:handled_by","routing:handler"),("input","routing:accepts","routing:schema"),("endpoint","routing:exposed_as","routing:endpoint")]])
        for filename,value in [("graph.json",graph),("policy.json",policy),("projection.json",projection)]:
            (app/filename).write_text(json.dumps(value,indent=2)+"\n")
        common=[cli,"link",app/"graph.json",app/"policy.json",app/"projection.json","--relation-pack",root/"relation-packs/routing.json","--as-of","2026-10-15T00:00:00Z"]
        result=command(label+"-client",[*common,"--format","http-client"],expected_success=refusal is None)
        if refusal:
            rejection=json.loads(result)
            assert rejection["status"]=="rejected"
            assert refusal in {issue["code"] for issue in rejection["issues"]},(label,rejection)
            controls.append(dict(label=label,stage="emission",result="refused",code=refusal))
            save_controls()
            return None
        (app/"client.ts").write_bytes(result)
        (app/"witness.rs").write_bytes(command(label+"-witness",[*common,"--format","axum-witness"]))
        assert digest=="sha256:"+hashlib.sha256((app/"src/api.rs").read_bytes()).hexdigest()
        return app
    app=prepare("positive")
    # The real positive consumer now compiles workspace-derived framework bytes.
    api_digest=hashlib.sha256((app/"src/api.rs").read_bytes()).hexdigest()
    shutil.copyfile(root/"relation-packs/routing.json",app/"workspace-routing-pack.json")
    workspace_config={"schemaVersion":"0.1.0","documentType":"workspace-config","id":"urn:transport:graph","namespace":"transport-controls","revision":"1",
        "sources":[{"adapter":"portable-shard","id":"urn:transport:workspace-source","path":"graph.json"}],
        "packs":["workspace-routing-pack.json"],"policy":"policy.json",
        "projections":[{"path":"projection.json","emissions":[{"path":"generated/client.ts","language":"http-client"},{"path":"generated/witness.rs","language":"axum-witness"}]}],
        "context":{},"evaluatedAt":"2026-10-15T00:00:00Z"}
    (app/"workspace.json").write_text(json.dumps(workspace_config,indent=2)+"\n")
    generated=json.loads(command("workspace-generate",[cli,"generate","workspace.json","--root",app],cwd=app))
    baseline=generated["baseline"];assert set(baseline["outputs"])=={"generated/client.ts","generated/witness.rs"}
    saved=app/"workspace-baseline.json";saved.write_text(json.dumps(baseline,indent=2)+"\n")
    composed=app/"workspace-composed-graph.json";composed.write_text(json.dumps(baseline["captures"][0]["inputs"]["graph"],indent=2)+"\n")
    common=[cli,"link",composed,app/"policy.json",app/"projection.json","--relation-pack",app/"workspace-routing-pack.json","--as-of","2026-10-15T00:00:00Z"]
    for fmt,path,name in [("http-client","generated/client.ts","client.ts"),("axum-witness","generated/witness.rs","witness.rs")]:
        direct=command("workspace-direct-"+fmt,[*common,"--format",fmt])
        assert direct==baseline["outputs"][path].encode()+b"\n",(fmt,"composed checked emission differs")
        (app/name).write_text(baseline["outputs"][path])
    controls.append(dict(label="workspace-framework-emissions",stage="workspace",result="generated",outputs=2,directComposedEmissionBytesEqual=True,consumer="workspace-derived-bytes-used-by-subsequent-real-build"))
    save_controls()
    bad_config=copy.deepcopy(workspace_config);bad_config["projections"][0]["emissions"][0]["bindingSlot"]="handler"
    (app/"workspace-bad-slot.json").write_text(json.dumps(bad_config)+"\n")
    command("workspace-binding-slot",[cli,"generate","workspace-bad-slot.json","--root",app],cwd=app,expected_success=False)
    assert "WORKSPACE_HTTP_BINDING_SLOT" in (work/"transport-workspace-binding-slot.stderr.log").read_text()
    controls.append(dict(label="workspace-framework-binding-slot",stage="workspace",result="refused",code="WORKSPACE_HTTP_BINDING_SLOT"));save_controls()
    moves=[]
    for name in ["graph.json","policy.json","projection.json","workspace-routing-pack.json"]:
        path=app/name;destination=path.with_name(path.name+".retained");path.rename(destination)
        moves.append(dict(configuredPath=str(path),preservedAt=str(destination)))
    assert all(not Path(v["configuredPath"]).exists() for v in moves)
    previous_environment=dict(env)
    try:
        env.clear();env.update(PATH="/patamaps-no-external-programs",HOME=str(app/"no-user-home"))
        replay=json.loads(command("workspace-offline",[cli,"verify-workspace",saved],cwd=work))
        assert replay["status"]=="verified-record-bindings" and replay["sourceRediscovery"]=="not-performed"
        staged=app/"staged-workspace"
        stage=json.loads(command("workspace-stage",[cli,"workspace-stage",saved,"--destination",staged],cwd=work))
        assert stage["status"]=="staged-workspace-outputs" and stage["baselineDigest"]==baseline["digest"]
        assert stage["sourceInputs"]=="not-copied" and stage["outputCount"]==2
        for path in baseline["outputs"]:
            assert (staged/path).read_bytes()==baseline["outputs"][path].encode()
        command("workspace-stage-existing",[cli,"workspace-stage",saved,"--destination",staged],cwd=work,expected_success=False)
        assert "PROJECT_STAGE_DESTINATION_UNAVAILABLE" in (work/"transport-workspace-stage-existing.stderr.log").read_text()
        assert all((staged/path).read_bytes()==body.encode() for path,body in baseline["outputs"].items())
    finally:env.clear();env.update(previous_environment)
    controls.append(dict(label="workspace-framework-offline",stage="workspace",result="verified",sourcePathsUnavailable=True,externalProgramsAbsentFromPath=True,retainedMoves=moves));save_controls()
    # The compiled consumer receives exact bytes materialized by the native stager.
    for path,name in [("generated/client.ts","client.ts"),("generated/witness.rs","witness.rs")]:
        shutil.copyfile(staged/path,app/name)
    controls.append(dict(label="workspace-output-stage",stage="workspace",result="staged",sourcePathsUnavailable=True,externalProgramsAbsentFromPath=True,outputs=2,consumer="native-staged-bytes-used-by-subsequent-real-build"));save_controls()
    controls.append(dict(label="workspace-output-stage-existing",stage="workspace",result="refused",code="PROJECT_STAGE_DESTINATION_UNAVAILABLE",outputBytesPreserved=True));save_controls()
    tampered=copy.deepcopy(baseline);tampered["outputs"]["generated/client.ts"]+="\n// altered generated output\n";tampered.pop("digest")
    tampered["digest"]=json.loads(command("workspace-tamper-digest",[cli,"json","digest"],input_bytes=json.dumps(tampered).encode()))
    (app/"workspace-tampered.json").write_text(json.dumps(tampered)+"\n")
    command("workspace-tamper",[cli,"verify-workspace",app/"workspace-tampered.json"],expected_success=False)
    assert "WORKSPACE_COMPOSITION_BINDING" in (work/"transport-workspace-tamper.stderr.log").read_text()
    controls.append(dict(label="workspace-framework-output-tamper",stage="workspace",result="refused",code="WORKSPACE_COMPOSITION_BINDING",baselineAddressRehashed=True));save_controls()
    refused_destination=app/"tampered-stage"
    command("workspace-stage-tamper",[cli,"workspace-stage",app/"workspace-tampered.json","--destination",refused_destination],expected_success=False)
    assert "WORKSPACE_COMPOSITION_BINDING" in (work/"transport-workspace-stage-tamper.stderr.log").read_text()
    assert not refused_destination.exists()
    controls.append(dict(label="workspace-output-stage-tamper",stage="workspace",result="refused",code="WORKSPACE_COMPOSITION_BINDING",destinationCreated=False));save_controls()
    assert api_digest==hashlib.sha256((app/"src/api.rs").read_bytes()).hexdigest()
    previous=env.get("PATAMAPS_AXUM_WITNESS")
    try:
        env["PATAMAPS_AXUM_WITNESS"]=str(app/"witness.rs")
        command("positive-rust",["cargo","build","--manifest-path",app/"Cargo.toml","--locked","--offline"])
        shutil.copy2(target/"debug/patamaps-http-transport-check",app/"service.native")
    finally:
        if previous is None:env.pop("PATAMAPS_AXUM_WITNESS",None)
        else:env["PATAMAPS_AXUM_WITNESS"]=previous
    command("positive-typescript",[node,compiler,"--target","ES2022","--module","commonjs","--lib","ES2022,DOM","--strict","--skipLibCheck","--outDir",app/"compiled",app/"client.ts"])
    (app/"typed.ts").write_text("import {callOperation} from './client';\nexport async function example(){const result=await callOperation('"+PREFIX+"evaluate',{message:'typed'});if(result.status===400)return result.body.issues[0]?.message;return result.body;}\nexport const get=()=>callOperation('"+PREFIX+"get-item',null,{path:{id:'a'},headers:{'x-proof':'allow'},query:{limit:1,verbose:false}});\n")
    command("typed-consumer",[node,compiler,"--target","ES2022","--module","commonjs","--lib","ES2022,DOM","--strict","--skipLibCheck","--noEmit",app/"typed.ts"])
    (app/"bad-types.ts").write_text("import {callOperation} from './client';\ncallOperation('"+PREFIX+"get-item',null);\n")
    diagnostics=command("missing-parameters",[node,compiler,"--target","ES2022","--module","commonjs","--lib","ES2022,DOM","--strict","--skipLibCheck","--noEmit",app/"bad-types.ts"],expected_success=False)
    assert b"TS2554" in diagnostics
    controls.append(dict(label="missing-typed-parameters",stage="typescript",result="refused",code="TS2554"))
    save_controls()
    (app/"runtime.cjs").write_bytes((root/"scripts/http_transport_runtime.cjs").read_bytes())
    out=app/"service.stdout.log"
    with out.open("xb") as stdout,(app/"service.stderr.log").open("xb") as stderr:
        process=subprocess.Popen([str(app/"service.native")],stdout=stdout,stderr=stderr,start_new_session=True,env=env)
        try:
            deadline=time.monotonic()+15
            while True:
                base=next(("http://"+v.removeprefix("LISTEN ") for v in out.read_text().splitlines() if v.startswith("LISTEN 127.0.0.1:")),None)
                if base:break
                if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError("Transport service failed to start")
                time.sleep(.05)
            controls.extend(json.loads(command("runtime",[node,app/"runtime.cjs",app/"compiled/client.js",base])))
            save_controls()
        finally:
            from cross_stack_bindings import stop
            stop(process)
    for label,mutate,code in [
        ("unsupported-pattern",lambda rows:rows[-1]["request"]["properties"]["quantity"].update(pattern="[0-9]+"),"HTTP_JSON_SCHEMA_UNSUPPORTED"),
        ("unsupported-format",lambda rows:rows[-1]["request"]["properties"]["uuid"].update(format="email"),"HTTP_JSON_SCHEMA_UNSUPPORTED"),
        ("missing-group",lambda rows:rows[1].pop("frontendGroup"),"HTTP_PROXY_GROUP"),
        ("mismatched-method",lambda rows:rows[0]["frontend"].update(method="PUT"),"HTTP_ENDPOINT_CONFLICT"),
        ("missing-path-required",lambda rows:rows[2]["pathParameters"].update(required=[]),"HTTP_PARAMETER_SCHEMA"),
        ("implicit-query-array",lambda rows:rows[2]["queryParameters"]["properties"].update(limit={"type":"array","items":{"type":"string"}}),"HTTP_PARAMETER_SCHEMA"),
        ("reserved-header",lambda rows:rows[2].update(headerParameters=obj({"host":{"type":"string"}})),"HTTP_HEADER_CONTRACT"),
    ]:prepare(label,mutate,code)
    for label,mutate,expected in [
        ("wrong-private-input",lambda rows:rows[0]["arguments"][-1].update(type="Replay"),b"E0631"),
        ("wrong-private-output",lambda rows:rows[0]["output"].update(successType="Problem"),b"E0271"),
    ]:
        bad=prepare(label,mutate)
        old=env.get("PATAMAPS_AXUM_WITNESS")
        try:
            env["PATAMAPS_AXUM_WITNESS"]=str(bad/"witness.rs")
            command(label+"-rust",["cargo","build","--manifest-path",bad/"Cargo.toml","--locked","--offline"],expected_success=False)
        finally:
            if old is None:env.pop("PATAMAPS_AXUM_WITNESS",None)
            else:env["PATAMAPS_AXUM_WITNESS"]=old
        error=(work/("transport-"+label+"-rust.stderr.log")).read_bytes()
        assert expected in error,(label,error[-3000:])
        controls.append(dict(label=label,stage="rust-signature",result="refused",code=expected.decode()))
        save_controls()
    receipt=dict(status="passed-transport-and-axum-controls",controls=controls,profile="patamaps-http-transport-1",
        lockDigest="sha256:"+hashlib.sha256(lock).hexdigest(),router="existing-router-preserved",fullWorkflowAccepted=False,
        existingProjectQualification="not-performed",nextjs="not-performed",activation="not-performed")
    (state/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt
