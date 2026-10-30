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


def verify_inspection_budget(controller, work):
    """Real subprocess deadline/protocol controls; no native build or lease."""
    import importlib.util
    from unittest.mock import patch
    work.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("patamaps_watch_budget_probe", controller)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    key = "sha256:" + "a" * 64
    compiler = work / "controlled-compiler"
    delay = work / "delay.json"
    selected = work / "selected-key.txt"
    delay.write_text("{}")
    selected.write_text(key)
    compiler.write_text("#!" + sys.executable + "\n" +
        "import json,sys,time\nfrom pathlib import Path\n" +
        "root=Path(__file__).parent\n" +
        "command=sys.argv[1]\n" +
        "time.sleep(json.loads((root/'delay.json').read_text()).get(command,0))\n" +
        "key='sha256:'+'a'*64\n" +
        "if command=='project-build-input-key':\n" +
        " print(json.dumps(dict(status='observed-project-build-inputs',commandsExecuted=False,inputKey=key)))\n" +
        "elif command=='project-build-verify':\n" +
        " print(json.dumps(dict(status='verified-selected-build-bindings',inputKey=(root/'selected-key.txt').read_text())))\n" +
        "else: raise SystemExit(2)\n")
    compiler.chmod(0o700)
    argv = [str(controller), str(work / "plan.json"), "--source", str(work),
            "--state", str(work / "state"), "--compiler", str(compiler)]
    def arguments(extra):
        with patch.object(sys, "argv", [*argv, *extra, "--runner", sys.executable]):
            return module.arguments()
    report = dict(control="bounded-watch-native-inspections", result="running", cases=[],
                  scope="controlled subprocess deadlines and protocol, not native/application acceptance")
    try:
        default = arguments([])
        assert default.inspection_timeout_ms == 30000
        report["cases"].append(dict(case="default-30000ms-preserved", result="passed"))
        for budget in ("999", "3600001", "invalid"):
            with (work / ("invalid-" + budget + ".stderr.log")).open("x") as err:
                with patch.object(sys, "stderr", err):
                    try:
                        arguments(["--inspection-timeout-ms", budget])
                    except SystemExit as error:
                        assert error.code == 2
                    else:
                        raise AssertionError("invalid inspection budget admitted")
            report["cases"].append(dict(case="invalid-budget-" + budget, result="refused"))
        assert arguments(["--inspection-timeout-ms", "3600000"]).inspection_timeout_ms == 3600000
        short = arguments(["--inspection-timeout-ms", "1000"])
        long = arguments(["--inspection-timeout-ms", "3000"])
        for command, inspect in (("project-build-input-key", module.observe),
                                 ("project-build-verify", module.verified_selection)):
            delay.write_text(json.dumps({command: 1.5}))
            try:
                inspect(short)
            except subprocess.TimeoutExpired:
                report["cases"].append(dict(case=command + "-short-budget", result="timed-out"))
            else:
                raise AssertionError("inspection exceeded its budget without refusal")
            value = inspect(long)
            assert (value if isinstance(value, str) else value["inputKey"]) == key
            report["cases"].append(dict(case=command + "-explicit-budget", result="passed"))
        delay.write_text("{}")
        selected.write_text("sha256:" + "b" * 64)
        try:
            module.verified_selection(long)
        except ValueError as error:
            assert str(error) == "WATCH_SELECTION_DOES_NOT_MATCH_CURRENT_INPUTS"
            report["cases"].append(dict(case="larger-budget-keeps-key-match", result="refused"))
        else:
            raise AssertionError("inspection budget bypassed selected/current key match")
        report["result"] = "passed"
        return report
    except BaseException as error:
        report.update(result="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
