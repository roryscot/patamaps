"""Retained native workflow controls; controlled artifacts, not app acceptance."""
from pathlib import Path
import copy, json, os, shutil, signal, subprocess, tempfile, time

def verify(root,work,env,run):
    cli=root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    evidence=work/"project-builds";evidence.mkdir()
    source=evidence/"owner";source.mkdir()
    state=Path(tempfile.mkdtemp(prefix="patamaps-project-build-"))/"state"
    controls=[]
    def write(path,value):
        with path.open("x") as f:json.dump(value,f,indent=2);f.write("\n")
    identity="urn:qualification:project-build"
    graph=json.loads((root/"fixtures/routing/graph.json").read_text())
    policy=json.loads((root/"fixtures/routing/policy.json").read_text())
    policy["graph"]=dict(id=identity,revision="1")
    projection=dict(schemaVersion="0.1.0",documentType="projection-spec",id=identity+":projection",
                    select=dict(kinds=["routing:command"]),slots=[])
    for name,value in [("graph",graph),("policy",policy),("projection",projection)]:write(source/(name+".json"),value)
    (source/"pack.json").write_bytes((root/"relation-packs/routing.json").read_bytes())
    (source/"input.txt").write_text("original\n")
    profile=dict(profile="patamaps-project-inputs-1",id=identity+":source",nonsecretInputs=True,
                 inputs=["graph.json","policy.json","projection.json","pack.json","input.txt"],
                 components=[dict(id="files",kind="contracts",root=".",entrypoints=["graph.json"])],
                 nonsecretConfiguration=dict(mode="declared"),secretReferences={})
    workspace=dict(schemaVersion="0.1.0",documentType="workspace-config",id=identity,namespace="project-build-controls",revision="1",
                   sources=[dict(adapter="portable-shard",id=identity+":shard",path="graph.json")],packs=["pack.json"],
                   policy="policy.json",projections=[dict(path="projection.json",emissions=[dict(path="generated/routes.json",language="json")])],
                   context=dict(environment="production"),evaluatedAt="2026-10-10T12:00:00Z")
    def command(body):
        return dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences=dict(MODE="mode"),
                    invocation=dict(executable="/bin/sh",arguments=["-c",body],codeInputs=[],
                                    bounds=dict(maximumElapsedMs=60001,maximumStdoutBytes=65536,maximumStderrBytes=4096)))
    build_body="/bin/mkdir -p bundle; printf artifact > bundle/app"
    plan=dict(profile="patamaps-project-build-1",project=profile,workspace=workspace,
              buildSteps=[command(build_body)],verificationSteps=[command('test "$(/bin/cat bundle/app)" = artifact')],
              outputs=[dict(path="bundle",kind="tree")])
    def build(label,value,success=True,force=False):
        path=evidence/(label+".json");write(path,value)
        raw=run("build-"+label,[cli,"project-build",path,"--source",source,"--state",state,*(["--force"] if force else [])],
                expected_success=success)
        return json.loads(raw)
    observed_plan=evidence/"observe-plan.json";write(observed_plan,plan)
    observed=json.loads(run("build-input-observation",[cli,"project-build-input-key",observed_plan,"--source",source]))
    assert observed["status"]=="observed-project-build-inputs" and observed["commandsExecuted"] is False
    assert not state.exists() and not (source/"bundle").exists()
    first=build("first",plan);assert first["status"]=="selected-project-build"
    assert first["inputKey"]==observed["inputKey"]
    (source/"input.txt").write_text("changed observation\n")
    changed_key=json.loads(run("build-input-change",[cli,"project-build-input-key",observed_plan,"--source",source]))
    assert changed_key["inputKey"]!=observed["inputKey"]
    (source/"input.txt").write_text("original\n")
    controls.append(dict(control="build-input-observation",result="read-only",sameKeyAsBuild=True,selectedChangeDetected=True))
    pointer=(state/"selected.json").read_bytes()
    selected=state/json.loads(pointer)["attempt"]
    assert (selected/"candidate/bundle/app").read_text()=="artifact"
    controls.append(dict(control="build-selection",result="selected",workspaceAdmissionRequired=True,
                         separateVerificationCommands=True,artifactTree=True))
    noop=build("noop",plan);assert noop["status"]=="unchanged-project-build" and noop["verification"]=="not-repeated" and noop["cacheHits"]==0
    assert len(list((state/"attempts").iterdir()))==1 and (state/"selected.json").read_bytes()==pointer
    controls.append(dict(control="build-noop",result="unchanged",verification="not-repeated",cacheHits=0))
    failed=copy.deepcopy(plan);failed["buildSteps"][0]=command("printf failure >&2; exit 9")
    r=build("failure",failed,False);assert r["previousSelectionPreserved"] and (state/"selected.json").read_bytes()==pointer
    controls.append(dict(control="build-failure",result="refused",previousSelectionPreserved=True))
    changed=copy.deepcopy(plan);changed["verificationSteps"][0]=command("printf changed > bundle/app")
    r=build("artifact-change",changed,False);assert "PROJECT_BUILD_ARTIFACT_CHANGED" in r["reason"]
    assert (state/"selected.json").read_bytes()==pointer
    controls.append(dict(control="build-artifact-change",result="refused",previousSelectionPreserved=True))
    rejected=copy.deepcopy(plan);rejected["workspace"]["id"]=identity+":unmatched-policy"
    r=build("admission",rejected,False);assert r["status"]=="refused-project-build" and (state/"selected.json").read_bytes()==pointer
    assert not (state/r["attempt"]/"build-000.started.json").exists()
    controls.append(dict(control="build-admission-before-commands",result="refused",buildCommandStarted=False))
    # Every interruption targets only the CLI handle created by this test.
    for signal_name in ("SIGKILL","SIGTERM","SIGINT"):
        waiting=copy.deepcopy(plan);marker_name="tool-"+signal_name+".pid"
        waiting["buildSteps"][0]=command(build_body+'; printf "%s\\n" "$$" > '+marker_name+'; exec /bin/sleep 30')
        path=evidence/("waiting-"+signal_name+".json");write(path,waiting)
        argv=[str(v) for v in [cli,"project-build",path,"--source",source,"--state",state]]
        with (evidence/("waiting-"+signal_name+".stdout.log")).open("xb") as out,(evidence/("waiting-"+signal_name+".stderr.log")).open("xb") as err:
            parent=subprocess.Popen(argv,cwd=work,env=env,stdout=out,stderr=err)
            try:
                deadline=time.monotonic()+15;markers=[]
                while not markers:
                    assert parent.poll() is None,"Build exited before owned tool started"
                    markers=list((state/"attempts").glob("*/candidate/"+marker_name))
                    assert time.monotonic()<deadline,"Build tool never reached wait"
                    time.sleep(.02)
                pid=int(markers[0].read_text())
                if signal_name=="SIGKILL":
                    contender=evidence/"contender.json";write(contender,plan)
                    run("build-contender",[cli,"project-build",contender,"--source",source,"--state",state],expected_success=False)
                    assert "PROJECT_BUILD_LOCK_UNAVAILABLE" in (work/"build-contender.stderr.log").read_text()
                    assert parent.poll() is None
                    controls.append(dict(control="build-concurrent-writer",result="refused",ownerConfirmedLive=True))
                parent.send_signal(getattr(signal,signal_name));parent.wait(timeout=5)
                def running():
                    status=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True,timeout=2).stdout.strip()
                    return bool(status) and not status.startswith("Z")
                deadline=time.monotonic()+5
                while running() and time.monotonic()<deadline:time.sleep(.02)
                assert not running() and (state/"selected.json").read_bytes()==pointer
                controls.append(dict(control="build-interruption-"+signal_name.lower(),result="owned-child-stopped",previousSelectionPreserved=True,
                                     signal=signal_name,ordinaryProcessGroupOnly=True))
            finally:
                if parent.poll() is None:parent.kill();parent.wait(timeout=5)
    replay=json.loads(run("build-bindings",[cli,"project-build-verify",state]))
    assert replay["status"]=="verified-selected-build-bindings"
    # Selected permission changes matter even when bytes stay identical.
    artifact=selected/"candidate/bundle/app";mode=artifact.stat().st_mode & 0o7777
    artifact.chmod(mode ^ 0o100)
    run("build-permission-tamper",[cli,"project-build-verify",state],expected_success=False)
    artifact.chmod(mode)
    controls.append(dict(control="build-permission-tamper",result="refused"))
    original_source=source;source_retained=evidence/"owner.retained-offline";source.rename(source_retained)
    previous_env=dict(env)
    try:
        env.clear();env.update(PATH="/patamaps-no-external-programs",HOME=str(evidence))
        replay=json.loads(run("build-offline",[cli,"project-build-verify",state],cwd=work))
        assert replay["status"]=="verified-selected-build-bindings" and replay["toolExecution"]=="not-performed"
    finally:
        env.clear();env.update(previous_env)
    controls.append(dict(control="build-offline-bindings",result="verified",originalSourcePathUnavailable=True,
                         externalProgramsAbsentFromPath=True,verification="records-and-selected-bytes-only"))
    relocated=evidence/"state.retained-copy"
    shutil.copytree(state,relocated)
    replay=json.loads(run("build-state-relocation",[cli,"project-build-verify",relocated]))
    assert replay["status"]=="verified-selected-build-bindings"
    controls.append(dict(control="build-state-relocation",result="verified",originalStateRetained=True))
    receipt=dict(status="passed-native-project-build-controls",controls=controls,
                 retainedState=str(state),retainedStateCopy=str(relocated),retainedOriginalSource=str(source_retained),
                 partialAndFailedAttemptsRetained=True,filesDeleted=0,fullDevelopmentWorkflow=False,
                 actualApplicationQualification=False,foregroundWatch="not-performed",
                 runtimeReadinessMeaning="not-established-by-these-controls",activation="not-performed")
    write(evidence/"receipt.json",receipt)
    return receipt
