"""Foreground watch controls. Launch outside an allocating storage lease."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import shutil
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/debug/patamaps")
    parser.add_argument("--runner", nargs=argparse.REMAINDER)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--prepare-contract", action="store_true")
    parser.add_argument("--isolated-ci", action="store_true")
    argv = sys.argv[1:]
    runner = None
    if "--runner" in argv:
        split = argv.index("--runner")
        runner, argv = argv[split + 1:], argv[:split]
        if not runner:
            parser.error("--runner requires an executable")
    args = parser.parse_args(argv)
    args.runner = runner
    if args.prepare_contract and args.context is None:
        parser.error("--prepare-contract requires --context")
    if args.context is not None:
        args.context = args.context.absolute()
    if os.environ.get("WARGAME_STORAGE_RUN_TOKEN"):
        parser.error("run outside the allocating lease; each watch update is supervised")
    if args.isolated_ci and (platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true"):
        parser.error("isolated-ci requires the actual isolated GitHub Linux job")
    runner = args.runner
    if not runner and not args.isolated_ci:
        runner = [os.environ["PATAMAPS_DEV_NODE"], os.environ["PATAMAPS_DEV_SUPERVISOR"], "patamaps", "--"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = args.work or ROOT / ".tools/project-adoption" / ("watch-" + stamp)
    work.mkdir(parents=True, exist_ok=False)
    if args.isolated_ci:
        runner = [sys.executable, str(Path(__file__).resolve()), "__ci-runner",
                  str(work / "controlled-policy.lock"), "--"]
    owner = work / "owner"
    owner.mkdir()
    state = Path(tempfile.mkdtemp(prefix="patamaps-project-watch-")) / "state"
    identity = "urn:qualification:project-watch"
    graph = json.loads((ROOT / "fixtures/routing/graph.json").read_text())
    policy = json.loads((ROOT / "fixtures/routing/policy.json").read_text())
    policy["graph"] = dict(id=identity, revision="1")
    projection = dict(schemaVersion="0.1.0", documentType="projection-spec",
                      id=identity + ":projection", select=dict(kinds=["routing:command"]), slots=[])
    for name, value in (("graph", graph), ("policy", policy), ("projection", projection)):
        (owner / (name + ".json")).write_text(json.dumps(value))
    (owner / "pack.json").write_bytes((ROOT / "relation-packs/routing.json").read_bytes())
    (owner / "input.txt").write_text("original")
    project = dict(profile="patamaps-project-inputs-1", id=identity + ":inputs", nonsecretInputs=True,
                   inputs=["graph.json", "policy.json", "projection.json", "pack.json", "input.txt"],
                   components=[dict(id="files", kind="contracts", root=".", entrypoints=["graph.json"])],
                   nonsecretConfiguration={}, secretReferences={})
    workspace = dict(schemaVersion="0.1.0", documentType="workspace-config", id=identity,
                     namespace="project-watch-controls", revision="1",
                     sources=[dict(adapter="portable-shard", id=identity + ":shard", path="graph.json")],
                     packs=["pack.json"], policy="policy.json",
                     projections=[dict(path="projection.json", emissions=[dict(path="generated.json", language="json")])],
                     context=dict(environment="production"), evaluatedAt="2026-10-10T12:00:00Z")

    def command(body):
        return dict(profile="patamaps-project-command-1", workingDirectory=".", environmentReferences={},
                    invocation=dict(executable="/bin/sh", arguments=["-c", body], codeInputs=[],
                                    bounds=dict(maximumElapsedMs=600000, maximumStdoutBytes=65536,
                                                maximumStderrBytes=4096)))

    good = "/bin/mkdir -p bundle; printf artifact > bundle/app"
    preparation_path = None
    original_preparation = None
    if args.prepare_contract:
        preparation_path = work / "preparation.json"
        preparation = dict(profile="patamaps-project-preparation-1",
            commands=[command("umask 077; /bin/cp input.txt generated-owner.txt")],
            outputs={"generated-owner.txt": None})
        original_preparation = json.dumps(preparation)
        preparation_path.write_text(original_preparation)
        good += "; /usr/bin/cmp input.txt generated-owner.txt; /bin/cp generated-owner.txt bundle/owner-contract"
    plan = dict(profile="patamaps-project-build-1", maximumRetainedAttempts=64, project=project, workspace=workspace,
                buildSteps=[command(good)], verificationSteps=[command('test "$(/bin/cat bundle/app)" = artifact')],
                outputs=[dict(path="bundle", kind="tree")])
    plan_path = work / "plan.json"

    def save_plan(body):
        plan["buildSteps"] = [command(body)]
        # Native strict reader may observe transient unavailable bytes; it must refuse.
        plan_path.write_text(json.dumps(plan))

    save_plan(good)
    receipt = dict(status="running", compiler=str(args.compiler),
                   compilerDigest=hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
                   controlsDigest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   runnerScope="isolated-CI controlled lock fixture" if args.isolated_ci else "explicit configured policy runner",
                   controllerDigest=hashlib.sha256((ROOT / "scripts/project_watch.py").read_bytes()).hexdigest(),
                   runner=runner, state=str(state), controls=[], sourceScope="controlled native build, not application acceptance")
    receipt_path = work / "receipt.json"
    current = None
    handles = []

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    def events(label):
        path = work / (label + ".stdout.log")
        result = []
        if path.exists():
            for line in path.read_text(errors="replace").splitlines():
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        result.append(value)
                except ValueError:
                    pass
        return result

    def wait_until(test, label, timeout=240):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if test():
                return
            if current is not None and current.poll() is not None:
                raise AssertionError("watch exited before " + label + ": " + str(current.returncode))
            time.sleep(.1)
        raise AssertionError("timed out: " + label)

    def start(label, parent_wrapper=False, runner_override=None):
        nonlocal current
        out = (work / (label + ".stdout.log")).open("xb")
        err = (work / (label + ".stderr.log")).open("xb")
        handles.extend([out, err])
        argv = [sys.executable, str(ROOT / "scripts/project_watch.py"), str(plan_path),
                "--source", str(owner), "--state", str(state), "--compiler", str(args.compiler),
                "--poll-ms", "100", "--debounce-ms", "500", "--runner", *(runner_override or runner)]
        if args.context is not None:
            # Context must precede the runner's remainder arguments.
            split=argv.index("--runner")
            argv[split:split]=["--context",str(args.context)]
        if preparation_path is not None:
            split = argv.index("--runner")
            argv[split:split] = ["--preparation", str(preparation_path)]
        if parent_wrapper:
            # Real parent process; exec would erase the parent-death condition.
            argv = [sys.executable, "-c",
                    "import subprocess,sys; p=subprocess.Popen(sys.argv[1:]); print(p.pid,flush=True); p.wait()",
                    *argv]
        current = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
        return current

    def completed(label, count):
        return sum(e.get("status") == "completed-project-build-update" for e in events(label)) >= count

    def refused(label):
        return any(e.get("status") == "refused-project-build-update" for e in events(label))

    def pointer():
        return (state / "selected.json").read_bytes()

    def running(pid):
        result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
        return result.returncode == 0 and bool(result.stdout.strip()) and not result.stdout.strip().startswith("Z")

    def finish(sig=signal.SIGTERM):
        nonlocal current
        if current is not None and current.poll() is None:
            current.send_signal(sig)
            current.wait(timeout=35)
        current = None

    fixed = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
             [Path(__file__), ROOT / "scripts/project_watch.py", ROOT / "scripts/project_watch_guard_controls.py", args.compiler]}
    if args.context is not None:
        fixed[str(args.context)]=hashlib.sha256(args.context.read_bytes()).hexdigest()
        receipt["contextBindingDigest"]=fixed[str(args.context)]
    if preparation_path is not None:
        fixed[str(preparation_path)] = hashlib.sha256(preparation_path.read_bytes()).hexdigest()
    receipt["fixedSourceDigests"] = fixed
    save()
    try:
        from project_watch_guard_controls import verify as verify_guard_groups
        receipt["controls"].append(verify_guard_groups(ROOT / "scripts/project_watch.py", work / "guard-group-probe"))
        from project_watch_guard_controls import verify_exits
        receipt["controls"].append(verify_exits(ROOT / "scripts/project_watch.py", work / "guard-exit-probe"))
        from project_watch_guard_controls import verify_inspection_budget
        receipt["controls"].append(verify_inspection_budget(ROOT / "scripts/project_watch.py", work / "inspection-budget-probe"))
        save()
        start("edits")
        wait_until(lambda: completed("edits", 1), "initial selected build")
        if args.context is not None:
            expected_context=json.loads(args.context.read_text())
            selected=json.loads(pointer())
            attempt=state/selected["attempt"]
            assert json.loads((attempt/"context-binding.json").read_text())==expected_context
            assert json.loads((attempt/"context/manifest.json").read_text())["digest"]==expected_context["digest"]
            receipt["controls"].append(dict(control="native-context-binding-materialized",result="passed",
                snapshotDigest=expected_context["digest"],nativeSelectedContextRequired=True))
            save()

        if preparation_path is not None:
            selected = json.loads(pointer())
            attempt = state / selected["attempt"]
            assert json.loads((attempt / "preparation.json").read_text()) == preparation
            assert (attempt / "candidate/bundle/owner-contract").read_bytes() == (owner / "input.txt").read_bytes()
            receipt["controls"].append(dict(control="native-preparation-consumed-through-watch", result="passed"))
            save()
        previous = pointer()
        attempts = len(list((state / "attempts").iterdir()))
        time.sleep(1)
        assert len(list((state / "attempts").iterdir())) == attempts
        # Multiple writes finish before debounce expires.
        for value in ("rapid-one", "rapid-two", "rapid-final"):
            (owner / "input.txt").write_text(value)
            time.sleep(.05)
        wait_until(lambda: completed("edits", 2), "debounced edit")
        assert len(list((state / "attempts").iterdir())) == attempts + 1
        assert pointer() != previous
        if preparation_path is not None:
            selected = json.loads(pointer())
            assert (state / selected["attempt"] / "candidate/bundle/owner-contract").read_text() == "rapid-final"
        receipt["controls"].append(dict(control="initial-edit-debounce-idle", result="passed",
                                        idleCreatedNoAttempt=True, rapidEditsOneAttempt=True))
        previous = pointer()
        save_plan("printf failure >&2; exit 9")
        wait_until(lambda: refused("edits"), "failed build")
        assert pointer() == previous
        attempts = len(list((state / "attempts").iterdir()))
        time.sleep(1)
        assert len(list((state / "attempts").iterdir())) == attempts
        assert sum(e.get("status") == "refused-project-build-update" for e in events("edits")) == 1
        receipt["controls"].append(dict(control="failed-key-suppression", result="passed", previousSelectionPreserved=True))
        save_plan(good)
        wait_until(lambda: completed("edits", 3), "recovery")
        assert pointer() == previous  # Native no-op: commands deliberately not repeated.
        receipt["controls"].append(dict(control="recovery-native-noop", result="passed", verification="not-repeated"))
        if preparation_path is not None:
            bad_preparation = json.loads(original_preparation)
            bad_preparation["commands"] = [command("printf preparation-failed >&2; exit 9")]
            preparation_path.write_text(json.dumps(bad_preparation))
            wait_until(lambda: sum(e.get("status") == "refused-project-build-update" for e in events("edits")) >= 2,
                       "failed preparation update")
            assert pointer() == previous
            attempts = len(list((state / "attempts").iterdir()))
            time.sleep(1)
            assert len(list((state / "attempts").iterdir())) == attempts
            preparation_path.write_text(original_preparation)
            wait_until(lambda: completed("edits", 4), "restored preparation native no-op")
            assert pointer() == previous
            receipt["controls"].append(dict(control="preparation-key-edit-failure-suppression-recovery",
                result="passed", previousSelectionPreserved=True, verification="not-repeated"))
            save()
        finish()
        for case in ("SIGINT", "SIGTERM", "SIGKILL", "parent-death", "runner-death"):
            sig = getattr(signal, case) if case.startswith("SIG") else signal.SIGKILL
            label = case
            pid_file = work / (label + ".pids")
            body = "/bin/sleep 300 & child=$!; printf '%s %s\\n' \"$$\" \"$child\" > " + shlex.quote(str(pid_file)) + '; wait "$child"'
            save_plan(body)
            previous = pointer()
            proc = start(label, parent_wrapper=case == "parent-death")
            wait_until(pid_file.exists, label + " ordinary descendants")
            pids = [int(v) for v in pid_file.read_text().split()]
            assert all(running(pid) for pid in pids)
            if case == "SIGINT":
                # A second controller must respect the live shared storage lease.
                out = (work / "contender.stdout.log").open("xb")
                err = (work / "contender.stderr.log").open("xb")
                handles.extend([out, err])
                contender = subprocess.Popen(proc.args, stdout=out, stderr=err, start_new_session=True)
                try:
                    wait_until(lambda: refused("contender"), "busy contender", timeout=30)
                    refused_event = next(e for e in events("contender") if e.get("status") == "refused-project-build-update")
                    assert refused_event["exitCode"] == 75
                    time.sleep(1)
                    assert sum(e.get("status") == "refused-project-build-update" for e in events("contender")) == 1
                    receipt["controls"].append(dict(control="live-policy-contender", result="passed",
                                                    policyExitCode=75, noAutomaticRetry=True))
                finally:
                    contender.terminate()
                    contender.wait(timeout=35)
            watcher_pid = None
            if case == "runner-death":
                table = {int(pid): int(parent) for pid, parent in
                         (line.split() for line in subprocess.check_output(
                             ["/bin/ps", "-axo", "pid=,ppid="], text=True).splitlines())}
                # shell <- private native guard <- CLI <- inner wrapper <- policy runner.
                victim = pids[0]
                for _ in range(4):
                    victim = table[victim]
                assert victim != proc.pid and running(victim)
                os.kill(victim, signal.SIGKILL)
                wait_until(lambda: refused(label), "runner death refusal", timeout=40)
                finish()
            else:
                if case == "parent-death":
                    watcher_pid = next(int(line) for line in (work / (label + ".stdout.log")).read_text().splitlines() if line.isdecimal())
                    assert running(watcher_pid)
                proc.send_signal(sig)
                proc.wait(timeout=35)
                current = None
            until = time.monotonic() + 35
            while (any(running(pid) for pid in pids) or watcher_pid is not None and running(watcher_pid)) and time.monotonic() < until:
                time.sleep(.1)
            assert not any(running(pid) for pid in pids), "ordinary descendants survived " + label
            if watcher_pid is not None:
                assert not running(watcher_pid), "watcher survived actual parent death"
            assert pointer() == previous
            receipt["controls"].append(dict(control="watch-" + label, result="passed", pids=pids,
                                            previousSelectionPreserved=True, ordinaryDescendantsStopped=True))
            save()
        previous = pointer()
        save_plan(good)
        # New selected bytes, with an explicit no-op runner: no allocating command occurs.
        (owner / "input.txt").write_text("ignored runner must not claim a build")
        attempts = len(list((state / "attempts").iterdir()))
        start("ignored-runner", runner_override=["/usr/bin/true"])
        wait_until(lambda: refused("ignored-runner"), "ignored runner refusal", timeout=30)
        assert pointer() == previous and len(list((state / "attempts").iterdir())) == attempts
        assert any(e.get("reason") == "WATCH_VERIFICATION_RECORD_REFUSED" for e in events("ignored-runner"))
        receipt["controls"].append(dict(control="ignored-runner-refuses-success", result="passed",
                                        guardedVerificationRecordRequired=True, currentInputKeyRequired=True))
        finish()
        assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected for path, expected in fixed.items())
        receipt["sourceUnchanged"] = True
        receipt["status"] = "passed"
    except BaseException as error:
        receipt.update(status="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        finish()
        for handle in handles:
            handle.close()
        if state.exists():
            shutil.copytree(state, work / "state.retained-copy")
            receipt["retainedStateCopy"] = str(work / "state.retained-copy")
        save()
        print(json.dumps(dict(status=receipt["status"], receipt=str(receipt_path))), flush=True)


def controlled_ci_runner():
    # Test fixture only: real Intel uses its installed storage supervisor.
    import fcntl
    if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("CI runner fixture is restricted to the actual isolated Linux job")
    lock = Path(sys.argv[2]).open("a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(75)
    assert sys.argv[3] == "--"
    raise SystemExit(subprocess.call(sys.argv[4:]))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "__ci-runner":
        controlled_ci_runner()
    else:
        main()
