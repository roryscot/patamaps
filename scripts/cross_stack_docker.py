"""Native parser/context controls. BuildKit and Linux image acceptance are separate."""
from pathlib import Path
import hashlib
import json
import sys


def verify(root,work,env,run):
    run("m3-format",["cargo","fmt","--all","--","--check"])
    run("m3-native-tests",["cargo","test","-p","patamaps-workspace","--locked","--offline"])
    run("m3-cli-build",["cargo","build","-p","patamaps-cli","--locked","--offline"])
    cli=root/"target/debug/patamaps"
    engine=json.loads(run("m3-engine",[cli,"engine"]))
    sys.path.insert(0,str(root/"scripts/parity"))
    from identity import identities
    assert engine=={"schemaVersion":"0.1.0","documentType":"executor-description",**identities(root)}
    fixture=root/"examples/cross-stack"
    raw=(fixture/"deploy/Dockerfile").read_text()
    expected=json.loads((fixture/"acceptance/m3-expected.json").read_bytes())
    cases=work/"cases";cases.mkdir()
    source={"deploy/Dockerfile":raw,".dockerignore":(fixture/".dockerignore").read_text(),"config/service.toml":(fixture/"config/service.toml").read_text(),"service/target/not-a-build-artifact":"nonsecret ignored marker\n"}
    for p in (fixture/"service").rglob("*"):
        if p.is_file() and "target" not in p.relative_to(fixture).parts:source[p.relative_to(fixture).as_posix()]=p.read_text()
    controls=[]
    sha=lambda raw:"sha256:"+hashlib.sha256(raw).hexdigest()

    def provider(label,changes=None,config_changes=None,omit=(),refuse=None):
        files={k:v for k,v in source.items() if k not in omit}
        if changes:files.update(changes)
        owner=cases/label;owner.mkdir()
        for path,content in files.items():
            p=owner/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        config={"provider":"dockerfile","nonsecretInputs":True,"dockerfile":"deploy/Dockerfile","context":".","contextFiles":sorted(files),"completeContextSnapshot":True,"target":"runtime","platform":"linux/amd64","frontend":"docker/dockerfile:1.10.0","buildArgs":{}}
        if config_changes:config.update(config_changes)
        request={"schemaVersion":"0.1.0","documentType":"adapter-request","profile":"patamaps-workspace-draft-1","sourceId":"urn:test:docker","namespace":"cross-stack-m3","config":config,
                 "inputs":[{"receipt":{"path":p,"digest":sha(v.encode()),"byteLength":len(v.encode())},"content":v} for p,v in sorted(files.items())],"invocationDigest":"sha256:"+"0"*64,"requestDigest":""}
        request["requestDigest"]=json.loads(run(label+"-request",[cli,"json","digest"],input_bytes=json.dumps(request).encode()))
        output=run(label,[cli,"discover-native"],cwd=owner,input_bytes=json.dumps(request).encode(),expected_success=refuse is None)
        assert all((owner/p).read_text()==content for p,content in files.items()),label+" changed captured input"
        assert not list(owner.rglob("RUN_WAS_EXECUTED")),"Discovery executed Docker instructions"
        if refuse:
            diagnostic=output.decode()+(work/(label+".stderr.log")).read_text();assert refuse in diagnostic,diagnostic
            controls.append({"control":label,"result":"refused","code":refuse,"sourcesUnchanged":True});return None
        value=json.loads(output);observation=value["shard"]["metadata"]["observation"]
        assert value["requestDigest"]==request["requestDigest"] and value["inputs"]==[v["receipt"] for v in request["inputs"]]
        assert observation["parser"]["grammar"]=="tree-sitter-containerfile=0.9.2" and observation["parser"]["engine"]=="tree-sitter=0.26.5"
        for key in ["compilationEstablished","instructionsExecuted","imageContentsEstablished","runtimeListenerEstablished","baseImageIdentitiesObserved"]:assert observation[key] is False
        for entity in value["shard"]["entities"]:
            if entity["kind"]=="docker-instruction":
                a=entity["attributes"];start,end=a["span"]
                assert all(isinstance(v,(int,float)) and not isinstance(v,bool) and v==int(v) for v in (start,end)), a["span"]
                start,end=int(start),int(end);raw_bytes=files[a["file"]].encode();assert 0<=start<=end<=len(raw_bytes)
                assert raw_bytes[start:end].decode()==a["lexeme"]
        controls.append({"control":label,"result":"syntax-observed","requestDigest":request["requestDigest"],"sourcesUnchanged":True,"instructionsExecuted":False})
        return value

    def instructions(value,kind):return sorted([v["attributes"] for v in value["shard"]["entities"] if v["kind"]=="docker-instruction" and v["attributes"]["instruction"]==kind],key=lambda v:v["span"][0])
    def reasons(value):return [reason for v in value["shard"]["metadata"]["observation"]["unsupported"] for reason in v["reasons"]]
    def members(value):return [m for c in instructions(value,"copy_instruction") for m in c["observation"]["contextMembers"]]

    baseline=provider("m3-real-dockerfile")
    observation=baseline["shard"]["metadata"]["observation"]
    stage=observation["selectedStage"]
    for key,value in expected["selectedStage"].items():assert stage[key]==value,(key,stage)
    copies=instructions(baseline,"copy_instruction")
    assert len(copies)==4 and copies[1]["observation"]["fromStageIndex"]==0
    assert copies[3]["observation"]["fromStageIndex"]==0 and copies[3]["observation"]["sources"]==["/build/licenses"]
    assert any(v["source"]=="config/service.toml" and v["destination"]=="/app/service.toml" for v in members(baseline))
    assert not any(v["source"].startswith("service/target/") for v in members(baseline))
    assert any("RUN effects" in v for v in reasons(baseline))

    alias=provider("m3-stage-alias-move",{"deploy/Dockerfile":raw.replace("AS builder","AS buildx").replace("--from=builder","--from=buildx")})
    assert instructions(alias,"copy_instruction")[1]["observation"]["fromStageIndex"]==0
    index=provider("m3-stage-index",{"deploy/Dockerfile":raw.replace("--from=builder","--from=0")})
    assert instructions(index,"copy_instruction")[1]["observation"]["fromStageIndex"]==0
    broken=provider("m3-missing-copy-stage",{"deploy/Dockerfile":raw.replace("--from=builder","--from=missing")})
    assert any("stage is unavailable or external" in v for v in reasons(broken))
    binary=provider("m3-unproved-builder-artifact",{"deploy/Dockerfile":raw.replace("/release/catalog-service","/release/missing-service")})
    assert instructions(binary,"copy_instruction")[1]["observation"]["sources"]==["/build/service/target/x86_64-unknown-linux-gnu/release/missing-service"]
    assert instructions(binary,"copy_instruction")[1]["observation"]["contentEstablished"] is False
    missing=provider("m3-missing-config",omit=("config/service.toml",))
    assert "missing context source config/service.toml" in reasons(missing)
    excluded=provider("m3-ignored-config",{".dockerignore":source[".dockerignore"]+"\nconfig/service.toml\n"})
    assert "context source excluded by ignore rules config/service.toml" in reasons(excluded)
    specific=provider("m3-specific-ignore-precedence",{".dockerignore":"config/service.toml\n","deploy/Dockerfile.dockerignore":"**/target\n"})
    assert specific["shard"]["metadata"]["observation"]["ignoreFile"]=="deploy/Dockerfile.dockerignore"
    assert any(m["source"]=="config/service.toml" for m in members(specific))
    arg=raw.replace("FROM rust:1.99.0-bookworm AS builder","ARG BASE\nFROM ${BASE} AS builder")
    unresolved=provider("m3-unresolved-build-arg",{"deploy/Dockerfile":arg})
    assert any("unresolved variable BASE" in v for v in reasons(unresolved))
    resolved=provider("m3-explicit-build-arg",{"deploy/Dockerfile":arg},config_changes={"buildArgs":{"BASE":"rust:1.99.0-bookworm"}})
    assert any(v["kind"]=="docker-stage" and v["attributes"]["base"]=="rust:1.99.0-bookworm" for v in resolved["shard"]["entities"])
    shell=provider("m3-shell-launch",{"deploy/Dockerfile":raw.replace('ENTRYPOINT ["/usr/local/bin/catalog-service"]','ENTRYPOINT /usr/local/bin/catalog-service')})
    assert shell["shard"]["metadata"]["observation"]["selectedStage"]["entrypoint"] is None
    assert any("shell-form launch" in v for v in reasons(shell))
    opaque=provider("m3-opaque-run",{"deploy/Dockerfile":raw+"RUN touch RUN_WAS_EXECUTED\n"})
    assert any("RUN effects" in v for v in reasons(opaque))
    json_copy=provider("m3-json-copy",{"deploy/Dockerfile":raw.replace("COPY config/service.toml /app/service.toml",'COPY ["config/service.toml", "/app/service.toml"]')})
    assert any(v["source"]=="config/service.toml" and v["destination"]=="/app/service.toml" for v in members(json_copy))
    provider("m3-wrong-context",config_changes={"context":"service"},refuse="NATIVE_DOCKER_CONTEXT")
    provider("m3-incomplete-context",config_changes={"completeContextSnapshot":False},refuse="NATIVE_DOCKER_CONTEXT")
    provider("m3-missing-target",config_changes={"target":"missing"},refuse="NATIVE_DOCKER_TARGET")
    provider("m3-unsupported-platform",config_changes={"platform":"windows/amd64"},refuse="NATIVE_DOCKER_CONTEXT")
    provider("m3-unsupported-ignore",{".dockerignore":"[ab]\n"},refuse="NATIVE_DOCKER_IGNORE_UNSUPPORTED")
    invalid_exec=provider("m3-invalid-json-launch-unresolved",{"deploy/Dockerfile":raw+'ENTRYPOINT ["broken"\n'})
    assert invalid_exec["shard"]["metadata"]["observation"]["selectedStage"]["entrypoint"] is None
    assert any("shell-form launch" in v for v in reasons(invalid_exec))
    provider("m3-malformed",{"deploy/Dockerfile":raw+'FROM\n'},refuse="NATIVE_DOCKER_SYNTAX")
    provider("m3-duplicate-stage-alias",{"deploy/Dockerfile":raw.replace("AS runtime","AS builder")},refuse="NATIVE_DOCKER_STAGE_ALIAS")
    provider("m3-over-byte-bound",{"deploy/Dockerfile":raw+"#"*(1024*1024)},refuse="NATIVE_DOCKER_LIMIT")
    moved=provider("m3-relocated")
    assert moved["shard"]==baseline["shard"],"Relocation changed captured syntax identities"
    return {"status":"passed","controls":controls,"nativeUnitControls":6,"engines":engine,"nativeBinaryDigest":sha(cli.read_bytes()),"parser":observation["parser"],"scope":"captured syntax/context membership only","BuildKitOracle":"unavailable-on-Intel; required Linux CI lane not run","LinuxArtifact":"not-observed","imageContents":"not-observed","runtime":"not-observed","graphConnection":"not-yet-enforced-M4","filesDeleted":[]}
