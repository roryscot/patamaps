"""Real compiler/HTTP controls for the M2 generated service boundary."""
from contextlib import contextmanager
from pathlib import Path
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def verify(root, work, env, run):
    fixture = root / "examples/cross-stack"
    expected = json.loads((fixture / "acceptance/m2-expected.json").read_bytes())
    frozen = json.loads((fixture / "acceptance/expected.json").read_bytes())
    run("m2-format", ["cargo", "fmt", "--all", "--", "--check"])
    run("m2-projection-tests", ["cargo", "test", "-p", "patamaps-projection", "--locked", "--offline"])
    run("m2-cli-build", ["cargo", "build", "-p", "patamaps-cli", "--locked", "--offline"])
    cli = root / "target/debug/patamaps"
    engine = json.loads(run("m2-engine", [cli, "engine"]))
    import sys
    sys.path.insert(0, str(root / "scripts/parity"))
    from identity import identities
    assert engine == {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(root)}
    spec = importlib.util.spec_from_file_location("cross_stack_consumer_build", fixture / "build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    cases = work / "cases"
    cases.mkdir()
    controls = []
    target = root / ".tools/cross-stack/target-service"

    def command(label, argv, cwd=root, expected_success=True, input_bytes=None):
        previous = dict(env)
        try:
            env.update(CARGO_TARGET_DIR=str(target), CARGO_PROFILE_DEV_DEBUG="0", CARGO_PROFILE_TEST_DEBUG="0")
            return run(label, argv, cwd=cwd, timeout=300, expected_success=expected_success, input_bytes=input_bytes)
        finally:
            env.clear()
            env.update(previous)

    def prepare(label, mutate=None, refusal=None):
        owner = cases / label
        inventory = builder.snapshot(fixture, owner)
        if mutate:
            mutate(owner)

        def emit(name, argv, cwd, input_bytes=None):
            result = command(label + "-" + name, argv, cwd, expected_success=not (refusal and name == "http-rust"), input_bytes=input_bytes)
            if refusal and name == "http-rust":
                diagnostics = (work / (label + "-" + name + ".stderr.log")).read_text() + result.decode("utf-8")
                assert refusal in diagnostics, diagnostics
                raise builder.BuildError(refusal)
            return result

        try:
            generated = builder.generate(owner, cli, emit)
        except builder.BuildError as error:
            if not refusal or refusal not in str(error):
                raise
            controls.append({"control": label, "stage": "generation", "result": "refused", "code": refusal})
            return owner, None
        assert refusal is None, label + " unexpectedly generated"
        for name, expected_digest in generated["sourceBytes"].items():
            assert builder.digest(builder.owned(owner, name).read_bytes()) == expected_digest, name
        assert generated["operationIds"] == [frozen["operationId"]]
        return owner, {"generated": generated, "snapshot": inventory}

    def build(label, owner, failure=None, features=()):
        args = ["cargo", "build", "--manifest-path", owner / "service/Cargo.toml", "--bin", "catalog-service", "--locked", "--offline"]
        if features:
            args += ["--features", ",".join(features)]
        command(label + "-cargo-build", args, expected_success=failure is None)
        if failure:
            text = (work / (label + "-cargo-build.stderr.log")).read_text()
            assert failure in text, text[-3000:]
            controls.append({"control": label, "stage": "Cargo", "result": "refused", "code": failure})
            return None
        executable = owner / "catalog-service.accepted-test-binary"
        shutil.copy2(target / "debug/catalog-service", executable)
        return executable

    @contextmanager
    def service(label, owner, executable):
        out_path, err_path = work / (label + ".service.stdout.log"), work / (label + ".service.stderr.log")
        with out_path.open("xb") as out, err_path.open("xb") as err:
            process = subprocess.Popen([str(executable), str(owner / "config/service.toml"), "127.0.0.1:0"], cwd=owner, env=env, stdout=out, stderr=err, start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                address = None
                while time.monotonic() < deadline:
                    address = next((s.removeprefix("LISTEN ") for s in out_path.read_text().splitlines() if s.startswith("LISTEN ")), None)
                    if address:
                        break
                    assert process.poll() is None, err_path.read_text()
                    time.sleep(.05)
                assert address and address.startswith("127.0.0.1:")
                yield "http://" + address
            finally:
                stop(process)

    def http(base, method, path, body):
        request = Request(base + path, data=None if body is None else json.dumps(body, ensure_ascii=False).encode(), headers={"content-type": "application/json"}, method=method)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return {"status": response.status, "body": json.loads(response.read())}

    happy = {"status": frozen["status"], "body": frozen["response"]}
    clean, baseline = prepare("supported")
    executable = build("supported", clean)
    command("supported-cargo-tests", ["cargo", "test", "--manifest-path", clean / "service/Cargo.toml", "--locked", "--offline"])
    web = clean / "web"
    (web / "node_modules").symlink_to(fixture / "web/node_modules", target_is_directory=True)
    command("supported-next-build", ["npm", "run", "build"], cwd=web)
    command("supported-next-typecheck", ["npm", "run", "typecheck"], cwd=web)
    client = work / "client-js"
    command("supported-client-compile", [fixture / "web/node_modules/.bin/tsc", "--target", "ES2022", "--module", "commonjs", "--lib", "ES2022,DOM", "--strict", "--skipLibCheck", "--outDir", client, web / "generated/operations.ts"])
    module = client / "operations.js"
    observed = []
    with service("supported", clean, executable) as base:
        for case in expected["http"]:
            got = http(base, case["method"], case["path"], case["body"])
            assert got == case["expected"], (case["name"], got)
            observed.append({"case": case["name"], **got})
        assert http(base, "POST", "/items", frozen["request"]) == happy
        with next_service(web, base, env, work) as frontend:
            script = work / "independent-client-check.cjs"
            script.write_text("const assert = require('node:assert/strict');\nconst {callOperation,validRequest,validResponse,OPERATIONS} = require(" + json.dumps(str(module)) + ");\n" + "const frontend=" + json.dumps(frontend) + "; const backend=" + json.dumps(base) + ";\n" + r'''
(async () => {
 const id='urn:example:operation:create-item';
 assert.deepEqual(OPERATIONS.map(v=>v.id),[id]);
 assert.deepEqual(await callOperation(id,{name:'Widget'},{base:frontend}),{status:201,body:{id:'item:widget',name:'Widget'}});
 assert.deepEqual(await callOperation(id,{name:'fail'},{base:frontend}),{status:500,body:{error:'backend-failure'}});
 const unicode='😀'.repeat(80);
 assert.deepEqual(await callOperation(id,{name:unicode},{base:backend,endpoint:'backend'}),{status:201,body:{id:'item:'+unicode,name:unicode}});
 assert.equal(validRequest(id,{name:'😀'.repeat(81)}),false);
 assert.equal(validRequest(id,{name:'\ud800'}),false);
 assert.equal(validRequest(id,{name:'ok',extra:true}),false);
 assert.equal(validResponse(id,{id:'item:ok'}),false);
 await assert.rejects(callOperation(id,{name:'ok'},{transport:async()=>new Response(JSON.stringify({id:'item:ok'}),{status:201})}),/HTTP_RESPONSE_CONTRACT/);
 await assert.rejects(callOperation(id,{name:'ok'},{transport:async()=>new Response(JSON.stringify({error:'unowned-error'}),{status:500})}),/HTTP_ERROR_CONTRACT/);
 console.log(JSON.stringify({status:'passed',realNextRustRoundTrip:true,unicodeCodePointBoundary:true,unpairedSurrogateRefused:true,invalidResponseRefused:true}));
})().catch(e=>{console.error(e);process.exitCode=1});
''')
            output = command("supported-http-client", ["node", script])
            client_result = json.loads(output)
    controls.append({"control": "supported-generated-consumer", "stage": "Next/Cargo/HTTP", "result": "passed", "http": observed, "client": client_result})

    def manifest(owner, edit):
        p = owner / "contracts/operations.json"
        value = json.loads(p.read_bytes())
        edit(value)
        p.write_text(json.dumps(value, indent=2) + "\n")

    def edit_source(owner, transform):
        p = owner / "service/src/handlers/create_item.rs"
        p.write_text(transform(p.read_text()))

    def moved(owner):
        shutil.copy2(owner / "service/src/handlers/create_item.rs", owner / "service/src/handlers/moved.rs")
        manifest(owner, lambda v: (v["moduleMap"].update(catalog="service/src/handlers/moved.rs"), v["operations"][0]["implementation"].update(file="service/src/handlers/moved.rs")))

    moved_owner, moved_record = prepare("moved-handler", moved)
    moved_binary = build("moved-handler", moved_owner)
    with service("moved-handler", moved_owner, moved_binary) as base:
        assert http(base, "POST", "/items", frozen["request"]) == happy
    assert moved_record["generated"]["operationIds"] == baseline["generated"]["operationIds"]
    assert moved_record["generated"]["projection"]["digest"] != baseline["generated"]["projection"]["digest"]
    controls.append({"control": "moved-handler", "stage": "Cargo/HTTP", "result": "passed", "stableOperationId": frozen["operationId"], "freshPhysicalBinding": True})

    failures = [
        ("missing-export", lambda s: s.replace("pub fn create_item(", "pub fn removed_item("), "E0425"),
        ("wrong-signature", lambda s: s.replace("create_item(input: CreateItemRequest)", "create_item(input: &CreateItemRequest)").replace("name: input.name,", "name: input.name.clone(),"), "E0308"),
        ("disabled-handler", lambda s: s.replace("pub fn create_item(", '#[cfg(feature="handler-enabled")]\npub fn create_item('), "E0425"),
    ]
    for label, transform, code in failures:
        def mutate(owner, transform=transform, label=label):
            edit_source(owner, transform)
            if label == "disabled-handler":
                with (owner / "service/Cargo.toml").open("a") as out:
                    out.write('\n[features]\nhandler-enabled=[]\n')
        owner, _ = prepare(label, mutate)
        build(label, owner, failure=code)

    enabled_owner = cases / "disabled-handler"
    enabled_binary = build("enabled-handler", enabled_owner, features=("handler-enabled",))
    with service("enabled-handler", enabled_owner, enabled_binary) as base:
        assert http(base,"POST","/items",frozen["request"]) == happy
    controls.append({"control":"enabled-handler","stage":"Cargo/HTTP","result":"passed","explicitFeatures":["handler-enabled"]})

    def duplicate(owner):
        manifest(owner, lambda v: v["operations"].append(v["operations"][0].copy()))
    prepare("duplicate-binding", duplicate, refusal="HTTP_DUPLICATE_OPERATION")
    def colliding_endpoint(owner):
        def change(value):
            clone=json.loads(json.dumps(value["operations"][0]));clone["id"]="urn:example:operation:collision";value["operations"].append(clone)
        manifest(owner,change)
    prepare("colliding-endpoint",colliding_endpoint,refusal="HTTP_ENDPOINT_CONFLICT")
    prepare("escaped-module-map",lambda o:manifest(o,lambda v:(v["moduleMap"].update(catalog="service/src/../../../outside.rs"),v["operations"][0]["implementation"].update(file="service/src/../../../outside.rs"))),refusal="HTTP_MODULE_OUTSIDE_OWNER")

    def schema_change(owner, which, transform):
        p = owner / ("contracts/create-item." + which + ".schema.json")
        value = json.loads(p.read_bytes())
        transform(value)
        p.write_text(json.dumps(value, indent=2) + "\n")

    prepare("unsupported-schema-pattern", lambda o: schema_change(o,"request",lambda v:v["properties"]["name"].update(pattern="^[a-z]+$")), refusal="HTTP_SCHEMA_UNSUPPORTED")
    prepare("unsupported-method", lambda o: manifest(o,lambda v:v["operations"][0]["endpoint"].update(method="GET")), refusal="HTTP_ENDPOINT_CONFLICT")

    def extra_required(value):
        value["properties"]["code"] = {"type":"string"}
        value["required"].append("code")

    runtime_mutations = [
        ("wrong-http-path", lambda o: manifest(o, lambda v:v["operations"][0]["endpoint"].update(path="/wrong"))),
        ("changed-request-shape", lambda o: schema_change(o,"request",extra_required)),
        ("changed-response-shape", lambda o: schema_change(o,"response",extra_required)),
        ("removed-serde-field", lambda o: edit_source(o,lambda s:s.replace("pub struct CreateItemResponse {\n    pub id: String,\n    pub name: String,", "pub struct CreateItemResponse {\n    pub id: String,\n    #[serde(skip_serializing)]\n    pub name: String,"))),
        ("renamed-request-wire-field", lambda o: edit_source(o,lambda s:s.replace("pub struct CreateItemRequest {\n    pub name: String,", 'pub struct CreateItemRequest {\n    #[serde(rename="title")]\n    pub name: String,'))),
        ("missing-router-registration", lambda o:(o/"service/src/main.rs").write_text((o/"service/src/main.rs").read_text().replace("generated::dispatch(request.method().as_str(), request.url(), &raw)", "{ let _ = generated::OPERATIONS; None::<(u16, serde_json::Value)> }"))),
    ]
    for label, mutate in runtime_mutations:
        owner, _ = prepare(label, mutate)
        binary = build(label, owner)
        with service(label, owner, binary) as base:
            got = http(base,"POST","/items",frozen["request"])
        assert got == expected["runtimeRefusals"][label] and got != happy, (label,got)
        controls.append({"control":label,"stage":"independent-HTTP","result":"candidate-rejected","observation":got})

    def unrelated(owner):
        (owner/"service/src/unrelated.rs").write_text("pub fn unrelated() -> usize { 42 }\n")
    owner, other = prepare("unrelated-rust-edit", unrelated)
    assert other["generated"]["projection"] == baseline["generated"]["projection"]
    binary = build("unrelated-rust-edit", owner)
    with service("unrelated-rust-edit",owner,binary) as base:
        assert http(base,"POST","/items",frozen["request"]) == happy
    controls.append({"control":"unrelated-rust-edit","stage":"projection/Cargo/HTTP","result":"passed","semanticProjectionUnchanged":True,"sourceInventoryChanged":True})
    negative = work/"negative-consumer.ts"
    negative.write_text("import {callOperation} from "+json.dumps(str(web/"generated/operations"))+";\ncallOperation('urn:example:operation:create-item',{name:4});\n")
    command("wrong-typescript-consumer",[fixture/"web/node_modules/.bin/tsc","--noEmit","--target","ES2022","--module","commonjs","--lib","ES2022,DOM","--strict","--skipLibCheck",negative],expected_success=False)
    assert "TS2322" in (work/"wrong-typescript-consumer.stdout.log").read_text()
    controls.append({"control":"wrong-typescript-consumer","stage":"TypeScript","result":"refused","code":"TS2322"})
    with service("retained-prior-candidate",clean,executable) as base:
        assert http(base,"POST","/items",frozen["request"]) == happy
    controls.append({"control":"prior-candidate-after-refusals","stage":"HTTP","result":"passed","selectionPublication":"not-tested-until-M5"})
    return {"status":"passed","controls":controls,"engines":engine,"baseline":baseline,"acceptedCandidate":str(clean.relative_to(root)),"browser":"not-run","LinuxImage":"not-run","atomicSelection":"not-tested-until-M5","filesDeleted":[]}


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=5)


@contextmanager
def next_service(web,backend,env,work):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port = sock.getsockname()[1]
    base = "http://127.0.0.1:"+str(port)
    out_path,err_path=work/"next.stdout.log",work/"next.stderr.log"
    with out_path.open("xb") as out,err_path.open("xb") as err:
        process=subprocess.Popen(["node",str(web/"node_modules/next/dist/bin/next"),"start","--hostname","127.0.0.1","--port",str(port)],cwd=web,env={**env,"CATALOG_SERVICE_URL":backend},stdout=out,stderr=err,start_new_session=True)
        try:
            deadline=time.monotonic()+30
            while True:
                assert process.poll() is None,err_path.read_text()
                try:
                    with urlopen(base,timeout=1) as response:
                        if response.status==200:break
                except OSError:
                    pass
                assert time.monotonic()<deadline,"Next startup deadline"
                time.sleep(.1)
            yield base
        finally:
            stop(process)
