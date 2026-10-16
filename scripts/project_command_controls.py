"""Controlled native project-command execution; not application acceptance."""
from pathlib import Path
import copy, json, os, shutil, subprocess, sys, time

def verify(root, work, env, run):
    cli = root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    state=work/"project-commands";state.mkdir()
    controls=[]
    def write(path,value):
        with path.open("x") as f:json.dump(value,f,indent=2);f.write("\n")
    def setup(label,configuration=None):
        case=state/label;case.mkdir();source=case/"owner";source.mkdir()
        (source/"input.txt").write_text("captured\n")
        profile=dict(profile="patamaps-project-inputs-1",id="urn:command:"+label,nonsecretInputs=True,inputs=["input.txt"],
                     components=[dict(id="inputs",kind="configuration",root=".",entrypoints=["input.txt"])],
                     nonsecretConfiguration=dict(mode="declared"),secretReferences=dict(unused="PATAMAPS_SECRET_UNUSED"))
        profile["nonsecretConfiguration"].update(configuration or {})
        write(case/"profile.json",profile)
        run(label+"-capture",[cli,"project-capture",case/"profile.json","--root",source,"--output",case/"capture.json"])
        command=dict(profile="patamaps-project-command-1",workingDirectory=".",environmentReferences=dict(MODE="mode"),
                     invocation=dict(executable="/usr/bin/env",arguments=[],codeInputs=[],bounds=dict(maximumElapsedMs=60001,maximumStdoutBytes=65536,maximumStderrBytes=4096)))
        return case,source,command
    def execute(label,argv=None,mutate=None,success=True,refusal=None,configuration=None):
        case,source,command=setup(label,configuration)
        if argv is not None:command["invocation"].update(executable=argv[0],arguments=argv[1:])
        if mutate:mutate(command)
        write(case/"command.json",command)
        raw=run(label+"-exec",[cli,"project-exec",case/"capture.json",case/"command.json","--root",source],expected_success=success)
        if refusal:
            assert refusal in (work/(label+"-exec.stderr.log")).read_text()
            controls.append(dict(control=label,result="refused",code=refusal))
            return None
        report=json.loads(raw);assert report["parentDeathCleanup"]=="private-supervisor-configured"
        assert report["ambientEnvironment"]=="not-inherited" and report["selectionPublication"]=="not-performed"
        controls.append(dict(control=label,result=report["status"],exitCode=report["exitCode"],
                             selectedInputsUnchanged=report["selectedInputsUnchanged"],executableUnchanged=report["executableUnchanged"]))
        return report
    report=execute("command-environment")
    assert report["stdout"]["text"]=="MODE=declared\n" and report["status"]=="completed-project-command"
    report=execute("command-nonzero",["/bin/sh","-c","printf out; printf diagnostic >&2; exit 9"],success=False)
    assert report["exitCode"]==9 and report["stdout"]["text"]=="out" and report["stderr"]["text"]=="diagnostic"
    report=execute("command-source-change",["/bin/sh","-c","printf changed > input.txt"],success=False)
    assert report["programSucceeded"] and not report["selectedInputsUnchanged"]
    execute("command-directory",mutate=lambda c:c.update(workingDirectory="../"),success=False,refusal="PROJECT_COMMAND_DIRECTORY")
    execute("command-environment-reference",mutate=lambda c:c.update(environmentReferences=dict(MODE="missing")),success=False,refusal="PROJECT_COMMAND_ENVIRONMENT")
    execute("command-helper-binding",mutate=lambda c:c["invocation"].update(codeInputs=["uncaptured.sh"]),success=False,refusal="PROJECT_COMMAND_CODE_INPUTS")
    execute("command-deadline",["/bin/sleep","5"],mutate=lambda c:c["invocation"]["bounds"].update(maximumElapsedMs=100),success=False,refusal="ADAPTER_TIMEOUT")
    execute("command-pipe-limit",["/bin/sh","-c","printf too-long"],mutate=lambda c:c["invocation"]["bounds"].update(maximumStdoutBytes=3),success=False,refusal="ADAPTER_OUTPUT_LIMIT")
    report=execute("command-binary-output",["/bin/sh","-c",r"printf '\377'"])
    assert report["stdout"]["text"] is None and report["stdout"]["hex"]=="ff"
    alias=state/"named-python"
    alias.symlink_to(Path(sys.executable).resolve())
    report=execute("command-executable-alias",[str(alias),"-c","import sys; print(sys.orig_argv[0])"])
    assert report["stdout"]["text"]==str(alias)+"\n"
    cargo=shutil.which("cargo",path=env.get("PATH"))
    assert cargo is not None
    configuration=dict(home=env.get("HOME",str(Path.home())),
                       cargoHome=env.get("CARGO_HOME",str(Path.home()/".cargo")),
                       rustupHome=env.get("RUSTUP_HOME",str(Path.home()/".rustup")))
    references=dict(MODE="mode",HOME="home",CARGO_HOME="cargoHome",RUSTUP_HOME="rustupHome")
    if env.get("RUSTUP_TOOLCHAIN"):
        configuration["toolchain"]=env["RUSTUP_TOOLCHAIN"];references["RUSTUP_TOOLCHAIN"]="toolchain"
    report=execute("command-cargo-version",[cargo,"--version"],configuration=configuration,
                   mutate=lambda c:c.update(environmentReferences=references))
    assert report["stdout"]["text"].startswith("cargo ")
    tool=state/"mutable-tool.sh"
    tool.write_text("#!/bin/sh\nprintf '# changed\\n' >> \"$0\"\n");tool.chmod(0o700)
    report=execute("command-tool-change",[str(tool)],success=False)
    assert report["programSucceeded"] and report["selectedInputsUnchanged"] and not report["executableUnchanged"]
    # SIGKILL only our own CLI handle. Its existing private guardian must stop
    # ordinary tool descendants independently of the invoking CLI.
    case,source,command=setup("command-parent-death")
    command["invocation"].update(executable="/bin/sh",arguments=["-c",'printf "%s\\n" "$$" > command.pid; exec /bin/sleep 30'])
    write(case/"command.json",command)
    argv=[str(v) for v in [cli,"project-exec",case/"capture.json",case/"command.json","--root",source]]
    with (case/"parent.stdout.log").open("xb") as out,(case/"parent.stderr.log").open("xb") as err:
        parent=subprocess.Popen(argv,env=env,cwd=work,stdout=out,stderr=err)
        try:
            deadline=time.monotonic()+10
            pidfile=source/"command.pid"
            while not pidfile.exists():
                assert parent.poll() is None,"CLI exited before owned tool started"
                assert time.monotonic()<deadline,"Owned tool did not start"
                time.sleep(.02)
            pid=int(pidfile.read_text())
            parent.kill();parent.wait(timeout=5)
            def running():
                r=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True,timeout=2)
                state=r.stdout.strip()
                return bool(state) and not state.startswith("Z")
            deadline=time.monotonic()+5
            while running() and time.monotonic()<deadline:time.sleep(.02)
            assert not running(),"Owned ordinary descendant survived parent death"
            controls.append(dict(control="command-parent-death",result="owned-descendant-stopped",parentSignal="SIGKILL",ordinaryProcessGroupOnly=True))
        finally:
            if parent.poll() is None:parent.kill();parent.wait(timeout=5)
    receipt=dict(status="passed-native-project-command-controls",controls=controls,selectionPublication="not-performed",
                 fullDevelopmentWorkflow=False,applicationBuild="not-performed",activation="not-performed",
                 abortedProgramPipeRetention="not-established")
    write(state/"receipt.json",receipt)
    return receipt
