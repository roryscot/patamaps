"""Selected-output execution controls. Keeps all successful and refused cases."""
import argparse,json,os,shlex,signal,subprocess,time
from pathlib import Path

def verify(cli,root):
    cli=cli.resolve(); repo=Path(__file__).resolve().parent.parent
    root.mkdir(parents=True,exist_ok=False)
    checks=[]
    def write(p,v): p.write_text(json.dumps(v,indent=2)+"\n")
    def run(label,args,expected=0):
        p=subprocess.run([str(cli),*map(str,args)],capture_output=True,text=True,
                         env={**os.environ,"AMBIENT_SELECTED_EXEC_TEST":"must-not-leak"},timeout=90)
        (root/(label+".stdout")).write_text(p.stdout)
        (root/(label+".stderr")).write_text(p.stderr)
        assert p.returncode==expected,(label,p.returncode,p.stderr[-2000:],p.stdout[-2000:])
        return json.loads(p.stdout) if p.stdout else p.stderr
    def command(body,refs=None):
        return dict(profile="patamaps-project-command-1",workingDirectory=".",
            environmentReferences={"MODE":"mode"} if refs is None else refs,
            invocation=dict(executable="/bin/sh",arguments=["-c",body],codeInputs=[],
                bounds=dict(maximumElapsedMs=60001,maximumStdoutBytes=65536,maximumStderrBytes=65536)))
    def setup(name):
        case=root/name;case.mkdir();owner=case/"owner";owner.mkdir();state=case/"state"
        identity="urn:qualification:selected-exec:"+name
        graph=json.loads((repo/"fixtures/routing/graph.json").read_text())
        policy=json.loads((repo/"fixtures/routing/policy.json").read_text())
        policy["graph"]=dict(id=identity,revision="1")
        projection=dict(schemaVersion="0.1.0",documentType="projection-spec",id=identity+":projection",
                        select=dict(kinds=["routing:command"]),slots=[])
        for n,v in [("graph",graph),("policy",policy),("projection",projection)]:write(owner/(n+".json"),v)
        (owner/"pack.json").write_bytes((repo/"relation-packs/routing.json").read_bytes())
        (owner/"input.txt").write_text("original")
        profile=dict(profile="patamaps-project-inputs-1",id=identity+":source",nonsecretInputs=True,
          inputs=["graph.json","policy.json","projection.json","pack.json","input.txt"],
          components=[dict(id="files",kind="contracts",root=".",entrypoints=["graph.json"])],
          nonsecretConfiguration=dict(mode="declared"),secretReferences={})
        workspace=dict(schemaVersion="0.1.0",documentType="workspace-config",id=identity,
          namespace="selected-exec-controls",revision="1",sources=[dict(adapter="portable-shard",id=identity+":shard",path="graph.json")],
          packs=["pack.json"],policy="policy.json",
          projections=[dict(path="projection.json",emissions=[dict(path="generated/routes.json",language="json")])],
          context=dict(environment="production"),evaluatedAt="2026-10-10T12:00:00Z")
        plan=case/"plan.json"
        write(plan,dict(profile="patamaps-project-build-1",project=profile,workspace=workspace,
          buildSteps=[command("/bin/mkdir -p bundle; printf artifact > bundle/app")],
          verificationSteps=[command('test "$(/bin/cat bundle/app)" = artifact')],
          outputs=[dict(path="bundle/app",kind="file")]))
        result=run(name+"-build",["project-build",plan,"--source",owner,"--state",state])
        assert result["status"]=="selected-project-build",result
        pointer=(state/"selected.json").read_bytes()
        candidate=state/json.loads(pointer)["attempt"]/"candidate"
        return case,owner,state,candidate,pointer,plan
    def execute(name,state,body,expected=0,refs=None):
        p=root/(name+".command.json");write(p,command(body,refs))
        return run(name,["project-exec-selected",state,p],expected)
    case,owner,state,candidate,pointer,plan=setup("positive")
    owner.rename(case/"owner.offline-retained")
    r=execute("captured-env",state,'printf "%s:%s:%s" "$(/bin/cat bundle/app)" "$MODE" "${AMBIENT_SELECTED_EXEC_TEST-unset}"')
    assert r["command"]["stdout"]["text"]=="artifact:declared:unset",r
    assert r["postExecutionSelectionVerified"] and r["selectionPointerUnchanged"]
    checks.append(dict(control="verified-artifact-offline-captured-environment",passed=True))
    case,owner,state,candidate,pointer,plan=setup("stale")
    (candidate/"bundle/app").rename(case/"qualified-artifact.retained")
    (candidate/"bundle/app").write_text("stale artifact")
    r=execute("stale-before-effects",state,"printf invoked > invoked.marker",2)
    assert "PROJECT_BUILD_SELECTED_OUTPUT_CHANGED" in r and not (candidate/"invoked.marker").exists()
    assert (state/"selected.json").read_bytes()==pointer
    checks.append(dict(control="stale-output-refused-before-command",passed=True))
    case,owner,state,candidate,pointer,plan=setup("artifact-mutation")
    (case/"qualified-artifact.retained").write_bytes((candidate/"bundle/app").read_bytes())
    r=execute("artifact-mutating-command",state,"printf changed > bundle/app",1)
    assert r["command"]["programSucceeded"] and not r["postExecutionSelectionVerified"]
    assert r["selectionPointerUnchanged"] and "PROJECT_BUILD_SELECTED_OUTPUT_CHANGED" in r["postExecutionVerification"]["error"]
    checks.append(dict(control="successful-command-output-mutation-refused",passed=True))
    case,owner,state,candidate,pointer,plan=setup("pointer-mutation")
    (case/"selected.retained.json").write_bytes(pointer)
    r=execute("pointer-mutating-command",state,"printf invalid > "+shlex.quote(str(state/"selected.json")),1)
    assert r["command"]["programSucceeded"] and not r["selectionPointerUnchanged"] and not r["postExecutionSelectionVerified"]
    checks.append(dict(control="successful-command-pointer-mutation-refused",passed=True))
    case,owner,state,candidate,pointer,plan=setup("missing-reference")
    r=execute("unresolved-reference",state,"printf invoked > invoked.marker",1,{"MODE":"missing"})
    assert "PROJECT_COMMAND_ENVIRONMENT" in r["command"]["error"] and not (candidate/"invoked.marker").exists()
    assert r["postExecutionSelectionVerified"]
    checks.append(dict(control="unresolved-configuration-refused-before-command",passed=True))
    case,owner,state,candidate,pointer,plan=setup("symlink-lock")
    (state/"driver.lock").rename(case/"driver.lock.retained")
    (state/"driver.lock").symlink_to(owner/"input.txt")
    execute("symlink-lock-refusal",state,"printf invoked > invoked.marker",2)
    assert not (candidate/"invoked.marker").exists() and (owner/"input.txt").read_text()=="original"
    checks.append(dict(control="symlink-lock-refused-before-command",passed=True))
    for sig in (signal.SIGKILL,signal.SIGTERM,signal.SIGINT):
        name="interruption-"+sig.name.lower()
        case,owner,state,candidate,pointer,plan=setup(name)
        p=case/"waiting.command.json";write(p,command('printf "%s" "$$" > owned.pid; exec /bin/sleep 30'))
        with (case/"parent.stdout").open("xb") as out,(case/"parent.stderr").open("xb") as err:
            parent=subprocess.Popen([str(cli),"project-exec-selected",str(state),str(p)],stdout=out,stderr=err)
            try:
                deadline=time.monotonic()+15
                while not (candidate/"owned.pid").exists():
                    assert parent.poll() is None,"owner exited before starting child"
                    assert time.monotonic()<deadline,"owned child did not start"
                    time.sleep(.02)
                pid=int((candidate/"owned.pid").read_text())
                if sig==signal.SIGKILL:
                    r=execute("simultaneous-executor",state,"printf invoked > contender.marker",2)
                    assert "PROJECT_BUILD_LOCK_UNAVAILABLE" in r
                    r=run("simultaneous-builder",["project-build",plan,"--source",owner,"--state",state,"--force"],2)
                    assert "PROJECT_BUILD_LOCK_UNAVAILABLE" in r and parent.poll() is None
                    assert not (candidate/"contender.marker").exists()
                    checks.append(dict(control="executor-and-builder-share-live-lock",passed=True))
                parent.send_signal(sig);parent.wait(timeout=5)
                def running():
                    s=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True,timeout=2).stdout.strip()
                    return bool(s) and not s.startswith("Z")
                deadline=time.monotonic()+5
                while running() and time.monotonic()<deadline:time.sleep(.02)
                assert not running(),"owned child survived"
                r=execute(name+"-recovery",state,"/bin/cat bundle/app")
                assert r["postExecutionSelectionVerified"] and (state/"selected.json").read_bytes()==pointer
                checks.append(dict(control=name+"-owned-child-stopped-and-lock-recovered",passed=True))
            finally:
                if parent.poll() is None:parent.kill();parent.wait(timeout=5)
    receipt=dict(status="passed-selected-project-exec-controls",checks=checks,filesDeleted=0,
                 applicationAcceptance=False,productionActivation=False)
    write(root/"receipt.json",receipt)
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--compiler",type=Path,required=True);p.add_argument("--work-root",type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.compiler,a.work_root)))
