"""Qualify native snapshot-backed Docker discovery with the frozen public Rust executable."""
import argparse, hashlib, io, json, os, platform, re, shutil, subprocess, sys, tarfile, time, uuid, zipfile
from pathlib import Path
from project_watch import stop
from deployment_miniserve_image import BASE, stop_owned
from qualify_installed_miniserve import ARTIFACT, RUN, PRODUCER, ZIP_SHA, STATE_SHA
ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    with path.open("rb") as source:
        return "sha256:" + hashlib.file_digest(source, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["cli", "work", "evidence"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--build-cli", action="store_true")
    args = parser.parse_args()
    assert platform.system() == "Linux" and platform.machine() == "x86_64" and os.environ.get("GITHUB_ACTIONS") == "true", "Use focused Linux CI; native Intel builds require their existing guard"
    work, out, cli = args.work.resolve(), args.evidence.resolve(), args.cli.resolve()
    work.mkdir(parents=True, exist_ok=False);out.mkdir(parents=True, exist_ok=False);(out/"logs").mkdir()
    assert not any((p/"Cargo.toml").exists() for p in work.parents)
    baseline = shutil.disk_usage(ROOT).used
    env = {k:v for k,v in os.environ.items() if k in ["PATH","HOME","CARGO_HOME","RUSTUP_HOME"]}
    env.update(PYTHONDONTWRITEBYTECODE="1",CARGO_INCREMENTAL="0",CARGO_BUILD_JOBS="2",CARGO_PROFILE_DEV_DEBUG="0",CARGO_PROFILE_TEST_DEBUG="0",RUST_TEST_THREADS="1",RUSTUP_TOOLCHAIN="1.99.0",CARGO_TERM_COLOR="never")
    record = dict(status="running",sourceRevision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),commands=[],controls=[],applicationRecompiled=False,productionActivation=False,registryPublication=False,filesDeleted=0)
    owned_path=out/"owned.json"

    def save():write(out/"receipt.json",record)
    def capacity():
        disk=shutil.disk_usage(ROOT)
        assert disk.free>=500000000 and disk.used-baseline<=4000000000,"CI storage boundary reached"
    def run(label,argv,expected=0,stdin=None,timeout=600,extra=None,binary=None,cwd=None):
        capacity();start=time.monotonic();stdout_path=binary or out/"logs"/(label+".stdout");stderr_path=out/"logs"/(label+".stderr")
        input_path=out/"logs"/(label+".input.json")
        if stdin is not None:input_path.write_bytes(stdin)
        with stdout_path.open("xb") as stdout,stderr_path.open("xb") as stderr:
            incoming=input_path.open("rb") if stdin is not None else subprocess.DEVNULL
            try:
                child=subprocess.Popen([sys.executable,str(ROOT/"scripts/project_watch.py"),"__guard",*map(str,argv)],cwd=cwd or ROOT,env={**env,**(extra or {})},stdin=incoming,stdout=stdout,stderr=stderr,start_new_session=True)
                try:
                    while child.poll() is None:
                        capacity();assert time.monotonic()-start<timeout,(label,"timeout")
                        assert stdout.tell()<67108864 and stderr.tell()<67108864,(label,"log limit");time.sleep(.25)
                    code=child.returncode
                finally:stop(child)
            finally:
                if stdin is not None:incoming.close()
        capacity();record["commands"].append(dict(label=label,exitCode=code,expectedExitCode=expected,elapsedMs=round((time.monotonic()-start)*1000)));save();print(json.dumps(record["commands"][-1]),flush=True)
        if code!=expected:
            print(stderr_path.read_text()[-5000:],flush=True)
            if not binary:print(stdout_path.read_text()[-3000:],flush=True)
            raise AssertionError((label,code,expected))
        return None if binary else stdout_path.read_text()
    def native(label,args,expected=0):return json.loads(run(label,[cli,*args],expected=expected))
    def discover(label,config,texts,diagnostic=None):
        request=dict(schemaVersion="0.1.0",documentType="adapter-request",profile="patamaps-workspace-draft-1",sourceId="urn:qualification:miniserve:docker",namespace="miniserve-binary-context",config=config,inputs=[dict(receipt=dict(path=p,digest="sha256:"+hashlib.sha256(text.encode()).hexdigest(),byteLength=len(text.encode())),content=text) for p,text in sorted(texts.items())],invocationDigest="sha256:"+"0"*64,requestDigest="")
        request["requestDigest"]=json.loads(run(label+"-digest",[cli,"json","digest"],stdin=json.dumps(request).encode()))
        result=run(label,[cli,"discover-native"],expected=2 if diagnostic else 0,stdin=json.dumps(request).encode(),cwd=work)
        if diagnostic:
            assert diagnostic in result+(out/"logs"/(label+".stderr")).read_text(),diagnostic
            record["controls"].append(dict(control=label,result="refused",diagnostic=diagnostic));save();return None
        result=json.loads(result);assert result["requestDigest"]==request["requestDigest"]
        record["controls"].append(dict(control=label,result="observed-captured-snapshot"));save();return result
    try:
        if args.build_cli:
            run("rustfmt",["cargo","+1.99.0","fmt","--all","--check"])
            tests=run("workspace-tests",["cargo","+1.99.0","test","--locked","-p","patamaps-workspace","--lib"])
            summary=re.search(r"test result: ok\. (\d+) passed; 0 failed; 0 ignored",tests);assert summary
            record["workspaceTestsPassed"]=int(summary[1])
            run("workspace-clippy",["cargo","+1.99.0","clippy","--locked","-p","patamaps-workspace","--all-targets","--","-D","warnings"])
            run("current-cli-build",["cargo","+1.99.0","build","--locked","-p","patamaps-cli","--bin","patamaps"])
        engine=native("current-engine",["engine"]);sys.path.insert(0,str(ROOT/"scripts/parity"));from identity import identities
        assert engine==dict(schemaVersion="0.1.0",documentType="executor-description",**identities(ROOT))
        record["compiler"]=dict(digest=sha(cli),engine=engine,buildProfile="development")
        token={"GH_TOKEN":os.environ["GH_TOKEN"]}
        meta=json.loads(run("frozen-artifact-metadata",["gh","api",f"repos/roryscot/patamaps/actions/artifacts/{ARTIFACT}"],extra=token))
        assert meta["workflow_run"]["id"]==RUN and meta["workflow_run"]["head_sha"]==PRODUCER and not meta["expired"] and meta["digest"]=="sha256:"+ZIP_SHA
        frozen=work/"frozen.zip";run("frozen-artifact",["gh","api",f"repos/roryscot/patamaps/actions/artifacts/{ARTIFACT}/zip"],extra=token,binary=frozen,timeout=180)
        assert sha(frozen)=="sha256:"+ZIP_SHA
        owner=work/"owner";owner.mkdir()
        with zipfile.ZipFile(frozen) as z:
            old=json.loads(z.read("receipt.json"));state=z.read("artifacts/selected-state.tar.gz")
            assert hashlib.sha256(state).hexdigest()==STATE_SHA
            with tarfile.open(fileobj=io.BytesIO(state),mode="r:gz") as tar:
                members=[m for m in tar.getmembers() if "/candidate/bundle/" in m.name and m.isfile()]
                assert len(members)==5
                for member in members:
                    relative="bundle/"+member.name.split("/candidate/bundle/",1)[1]
                    assert not Path(relative).is_absolute() and ".." not in Path(relative).parts and not member.mode & 0o7000 and member.size<10000000
                    path=owner/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tar.extractfile(member).read());path.chmod(member.mode)
            (owner/"MINISERVE-LICENSE").write_bytes(z.read("artifacts/MINISERVE-LICENSE"))
        assert sha(owner/"bundle/miniserve")=="sha256:"+old["applicationBinary"]["sha256"]
        (owner/"Dockerfile").write_text("# syntax=docker/dockerfile:1.10.0\nFROM "+BASE+" AS runtime\nWORKDIR /\nCOPY bundle/ /bundle/\nCOPY MINISERVE-LICENSE /licenses/MINISERVE-LICENSE\nUSER 65532:65532\nEXPOSE 9100/tcp\nENTRYPOINT [\"/bin/bash\", \"/bundle/launch.sh\"]\n")
        files=sorted(p.relative_to(owner).as_posix() for p in owner.rglob("*") if p.is_file());assert len(files)==7
        before={p:sha(owner/p) for p in files};texts={p:(owner/p).read_text() for p in files if p!="bundle/miniserve"}
        selection=work/"selection.json";write(selection,dict(profile="patamaps-project-context-selection-1",id="urn:qualification:miniserve:docker",nonsecretInputs=True,paths=files,symlinks="refuse"))
        snapshot=work/"snapshot";captured=native("binary-context-capture",["project-context-capture",selection,"--root",owner,"--destination",snapshot])
        config=dict(provider="dockerfile",nonsecretInputs=True,dockerfile="Dockerfile",context=".",contextFiles=files,completeContextSnapshot=True,target="runtime",platform="linux/amd64",frontend="docker/dockerfile:1.10.0",buildArgs={},contextSnapshot=dict(snapshot=str(snapshot),digest=captured["digest"]))
        positive=discover("snapshot-discovery",config,texts);observation=positive["shard"]["metadata"]["observation"]
        assert observation["contextSnapshot"]["digest"]==captured["digest"] and observation["contextSnapshot"]["fileCount"]==7 and observation["contextSnapshot"]["snapshotBytesVerified"] and observation["contextSnapshot"]["capturedModesBound"]
        assert all(observation[k] is False for k in ["instructionsExecuted","imageContentsEstablished","runtimeListenerEstablished","compilationEstablished","baseImageIdentitiesObserved"])
        copies=[e["attributes"] for e in positive["shard"]["entities"] if e["kind"]=="docker-instruction" and e["attributes"]["instruction"]=="copy_instruction"]
        runtime=[m for c in copies for m in c["observation"]["contextMembers"] if m["source"]=="bundle/miniserve"];assert len(runtime)==1 and runtime[0]["digest"]==before["bundle/miniserve"] and runtime[0]["contentSuppliedAsText"] is False
        assert all(c["supportedSyntaxAndResolution"] for c in copies),copies
        write(out/"discovery.json",positive)
        for label,change,diagnostic in [
            ("legacy-binary-refused",lambda c:c.pop("contextSnapshot"),"NATIVE_DOCKER_CONTEXT"),
            ("wrong-snapshot-digest",lambda c:c["contextSnapshot"].update(digest="sha256:"+"0"*64),"PROJECT_CONTEXT"),
            ("missing-member",lambda c:c["contextFiles"].pop(),"NATIVE_DOCKER_CONTEXT"),
            ("duplicate-member",lambda c:c["contextFiles"].append("Dockerfile"),"NATIVE_DOCKER_CONTEXT"),
            ("nonsecret-refused",lambda c:c.update(nonsecretInputs=False),"NATIVE_SECRET_INPUT"),
            ("unknown-snapshot-key",lambda c:c["contextSnapshot"].update(unreviewed=True),"NATIVE_DISCOVERY_CONFIG")]:
            changed=json.loads(json.dumps(config));change(changed);discover(label,changed,texts,diagnostic)
        changed=dict(texts);changed["Dockerfile"]+="# changed captured text\n";discover("changed-text-refused",config,changed,"NATIVE_DOCKER_CONTEXT_TEXT")
        blob=snapshot/"data/bundle/miniserve";backup=work/"opaque-runtime.retained";blob.rename(backup);blob.write_bytes(b"changed binary")
        discover("changed-binary-refused",config,texts,"PROJECT_CONTEXT");blob.rename(work/"changed-runtime.retained");backup.rename(blob)
        owner.rename(work/"owner.retained-offline")
        assert discover("owner-unavailable-discovery",config,texts)==positive
        staged=work/"staged";stage=native("binary-context-stage",["project-context-stage",snapshot,"--destination",staged]);assert stage["digest"]==captured["digest"]
        assert {p:sha(staged/p) for p in files}==before and (staged/"bundle/miniserve").stat().st_mode & 0o777==0o755
        native("staged-runtime-elf",["elf-target-check",staged/"bundle/miniserve","--target","linux/amd64","--digest",before["bundle/miniserve"]])
        iid=work/"image.iid";run("actual-snapshot-image",["docker","buildx","build","--load","--platform","linux/amd64","--target","runtime","--network","none","--progress","plain","--provenance=false","--iidfile",iid,"--metadata-file",out/"build-metadata.json",staged],timeout=300)
        image=iid.read_text().strip();assert re.fullmatch("sha256:[0-9a-f]{64}",image)
        info=json.loads(run("actual-image-inspect",["docker","image","inspect",image]))[0];assert (info["Os"],info["Architecture"])==("linux","amd64") and info["Config"]["User"]=="65532:65532"
        owned=dict(token=uuid.uuid4().hex,images=[image],containers=[],filesDeleted=0);write(owned_path,owned)
        shell="set -e; cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.swap.max /sys/fs/cgroup/pids.max; /bin/bash /bundle/probe.sh positive /tmp/probe; cat /tmp/probe/passed-controls.txt"
        cid=run("image-runtime-create",["docker","create","--label","org.patamaps.qualification-owner="+owned["token"],"--network","none","--read-only","--tmpfs","/tmp:rw,noexec,nosuid,size=1048576","--shm-size","1048576","--cpus","1","--memory","268435456","--memory-swap","268435456","--pids-limit","64","--cap-drop","ALL","--security-opt","no-new-privileges","--entrypoint","/bin/bash",image,"-c",shell]).strip()
        assert re.fullmatch("[0-9a-f]{64}",cid);owned["containers"].append(dict(id=cid,confirmedStopped=False));write(owned_path,owned)
        output=run("actual-image-runtime",["docker","start","--attach",cid],timeout=120)
        assert int(run("actual-image-wait",["docker","wait",cid]).strip())==0
        assert output.splitlines()[:4]==["100000 100000","268435456","0","64"]
        assert output.splitlines()[-8:]==old["runtimeControls"]
        final=json.loads(run("actual-image-final-inspect",["docker","inspect",cid]))[0];assert not final["State"]["Running"] and final["HostConfig"]["NetworkMode"]=="none" and final["HostConfig"]["ReadonlyRootfs"] and not final["HostConfig"].get("Binds")
        observed=work/"image-runtime";run("image-runtime-bytes",["docker","cp",cid+":/bundle/miniserve",observed]);assert sha(observed)==before["bundle/miniserve"]
        assert {p:sha(staged/p) for p in files}==before
        native("snapshot-post-runtime-verify",["project-context-verify",snapshot])
        record.update(status="passed-native-binary-docker-context",snapshotDigest=captured["digest"],contextFiles=before,discoveryRequestDigest=positive["requestDigest"],opaqueRuntime=runtime[0],imageId=image,imageRuntimeControls=old["runtimeControls"],actualImageRuntime=True,sourceUnavailableReplay=True,allContextBytesUnchanged=True,compilerOnRuntimeRequestPath=False,completeDependencyClosure=False,actualBrowser=False)
    except BaseException as error:
        record.update(status="failed",error=str(error));save();raise
    finally:
        stop_owned(owned_path)
    assert all(c["confirmedStopped"] for c in json.loads(owned_path.read_bytes())["containers"])
    record["ownedContainersStopped"]=True
    save();print(json.dumps(dict(status=record["status"],controls=len(record["controls"]))))


if __name__=="__main__":
    main()
