"""Owned no-detach runner lifetime regression; no build/source execution."""
from pathlib import Path
import json,os,signal,subprocess,sys,time

def verify(controller,work,expect_cleanup=True):
    work.mkdir(exist_ok=False)
    marker=work/"tool.json";runner_record=work/"runner.json"
    tool=work/"tool.py"
    tool.write_text("import json,os,subprocess,time\nfrom pathlib import Path\np=subprocess.Popen(['/bin/sleep','300'])\nPath("+repr(str(marker))+").write_text(json.dumps(dict(tool=os.getpid(),sleep=p.pid,guard=os.getppid())))\ntime.sleep(300)\n")
    runner=work/"runner.py"
    runner.write_text("import json,os,subprocess,sys\nfrom pathlib import Path\np=subprocess.Popen(sys.argv[1:])\nPath("+repr(str(runner_record))+").write_text(json.dumps(dict(runner=os.getpid(),guard=p.pid)))\np.wait()\n")
    def running(pid):
        value=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
        return value.returncode==0 and bool(value.stdout.strip()) and not value.stdout.strip().startswith("Z")
    process=None;pids={};report={"control":"no-detach-policy-guardian-group","result":"running"}
    try:
        with (work/"stdout.log").open("xb") as out,(work/"stderr.log").open("xb") as err:
            process=subprocess.Popen([sys.executable,str(controller),"__guard",sys.executable,str(runner),
                sys.executable,str(controller),"__guard",sys.executable,str(tool)],
                stdout=out,stderr=err,start_new_session=True)
            deadline=time.monotonic()+15
            while not marker.exists() and time.monotonic()<deadline:
                assert process.poll() is None,"guard exited before tool started"
                time.sleep(.05)
            assert marker.exists()
            pids=json.loads(marker.read_text());owner=json.loads(runner_record.read_text())
            assert pids["guard"]==owner["guard"]
            report.update(runner=owner["runner"],innerGuard=pids["guard"],tool=pids["tool"],sleep=pids["sleep"],
                          runnerGroup=os.getpgid(owner["runner"]),innerGuardGroup=os.getpgid(pids["guard"]))
            # Hold only our guardian to make outer group cleanup order deterministic.
            os.kill(pids["guard"],signal.SIGSTOP)
            os.kill(owner["runner"],signal.SIGKILL)
            process.wait(timeout=15)
            if running(pids["guard"]):os.kill(pids["guard"],signal.SIGCONT)
            deadline=time.monotonic()+15
            while any(running(pids[k]) for k in ["tool","sleep"]) and time.monotonic()<deadline:
                time.sleep(.05)
            survivors=[pids[k] for k in ["tool","sleep"] if running(pids[k])]
            report.update(ordinarySurvivors=survivors,guardianHasIndependentGroup=report["runnerGroup"]!=report["innerGuardGroup"])
            assert (not survivors)==expect_cleanup,report
            if expect_cleanup:assert report["guardianHasIndependentGroup"]
            report["result"]="passed" if expect_cleanup else "confirmed-old-group-defect"
            return report
    except BaseException as error:
        report.update(result="failed",error=type(error).__name__+": "+str(error))
        raise
    finally:
        if pids:
            try:os.kill(pids["guard"],signal.SIGCONT)
            except ProcessLookupError:pass
        if process is not None and process.poll() is None:
            process.terminate();process.wait(timeout=15)
        if pids and any(running(pids[k]) for k in ["tool","sleep"]):
            # Our tool is its group leader; stop only the owned live probe group.
            try:os.killpg(pids["tool"],signal.SIGKILL)
            except ProcessLookupError:pass
        (work/"receipt.json").write_text(json.dumps(report,indent=2)+"\n")


def verify_exits(controller, work):
    """Preserve normal exits and refuse permission errors for live owned groups."""
    import importlib.util
    from types import SimpleNamespace
    from unittest.mock import patch
    work.mkdir(exist_ok=False)
    spec=importlib.util.spec_from_file_location("patamaps_owned_exit_probe",controller)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    receipt={"control":"ordinary-exit-and-empty-group-permission","result":"running","cases":[]}
    def running(pid):
        value=subprocess.run(["/bin/ps","-p",str(pid),"-o","stat="],capture_output=True,text=True,check=False)
        return value.returncode==0 and bool(value.stdout.strip()) and not value.stdout.strip().startswith("Z")
    try:
        for label,argv,expected in [
            ("ordinary-success",[sys.executable,"-c","pass"],0),
            ("ordinary-failure",[sys.executable,"-c","raise SystemExit(7)"],7),
            ("timed-success",["/usr/bin/time","-p",sys.executable,"-c","pass"],0)]:
            with (work/(label+".stdout.log")).open("xb") as out,(work/(label+".stderr.log")).open("xb") as err:
                result=subprocess.run([sys.executable,str(controller),"__guard",*argv],stdout=out,stderr=err,timeout=20)
            assert result.returncode==expected,(label,result.returncode,expected)
            receipt["cases"].append(dict(case=label,result="passed",exitCode=result.returncode))
        empty=subprocess.Popen([sys.executable,"-c","pass"],start_new_session=True);empty.wait(timeout=5)
        with patch.object(module,"sys",SimpleNamespace(platform="darwin")),patch.object(module.os,"killpg",side_effect=PermissionError(1,"injected empty owned group race")):
            module.stop(empty,grace=.1)
        receipt["cases"].append(dict(case="empty-group-EPERM",result="passed"))
        live=subprocess.Popen(["/bin/sleep","300"],start_new_session=True)
        try:
            refused=False
            with patch.object(module,"sys",SimpleNamespace(platform="darwin")),patch.object(module.os,"killpg",side_effect=PermissionError(1,"injected live owned group refusal")):
                try:module.stop(live,grace=.1)
                except PermissionError:refused=True
            assert refused and running(live.pid)
            receipt["cases"].append(dict(case="live-group-EPERM",result="refused"))
        finally:
            if live.poll() is None:os.killpg(live.pid,signal.SIGKILL)
            live.wait(timeout=5)
        receipt["result"]="passed"
        return receipt
    except BaseException as error:
        receipt.update(result="failed",error=type(error).__name__+": "+str(error));raise
    finally:
        (work/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
