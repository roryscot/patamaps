"""Real-kernel proposed guardian controls; not installed release acceptance."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import native_inspection_guard as adapter
import project_watch as watch

KEY = "sha256:" + "a" * 64


class InspectionGuardian(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="inspection-guardian-",
                         dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"])).resolve()
        cls.root.chmod(0o700)

    def fixture(self):
        case = self.root / self._testMethodName
        case.mkdir(mode=0o700)
        self.case = case
        jobs = case / "jobs"
        jobs.mkdir(mode=0o700)
        return case, adapter.InspectionRunner(jobs, case, stop_grace=.2)

    def argv(self, source):
        return [str(Path(sys.executable).resolve()), "-I", "-S", "-B", "-c", source]

    def call(self, runner, argv, timeout=5):
        return runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      timeout=timeout, check=False)

    def live(self, pid):
        p = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="],
                           capture_output=True, text=True)
        return p.returncode == 0 and bool(p.stdout.strip()) and not p.stdout.strip().startswith("Z")

    def wait_file(self, path, child, timeout=8):
        until = time.monotonic() + timeout
        while not path.exists():
            self.assertIsNone(child.poll())
            self.assertLess(time.monotonic(), until)
            time.sleep(.02)

    def collect(self, fd, records, count=None, timeout=10):
        until = time.monotonic() + timeout
        raw = bytearray()
        with selectors.DefaultSelector() as poll:
            poll.register(fd, selectors.EVENT_READ)
            while count is None or len(records) < count:
                self.assertLess(time.monotonic(), until, "control channel deadline")
                if not poll.select(.1):
                    continue
                chunk = os.read(fd, 4096)
                if not chunk:
                    self.assertFalse(raw)
                    return True
                raw.extend(chunk)
                while b"\n" in raw:
                    row, _, rest = raw.partition(b"\n")
                    raw = bytearray(rest)
                    records.append(json.loads(row))
                    (self.case/"control-records.json").write_text(json.dumps(records,indent=2)+"\n")
            self.assertFalse(raw)
        return False

    def test_success_and_failure_exit_preserved(self):
        _, run = self.fixture()
        for code in [0, 7]:
            result = self.call(run, self.argv("print('native-data');raise SystemExit(" + str(code) + ")"))
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(result.stdout, b"native-data\n")
            self.assertEqual(len(run.calls[-1]["records"]), 3)
            self.assertFalse(self.live(run.calls[-1]["records"][1]["pid"]))

    def test_existing_watch_observation_and_binding_logic_uses_adapter(self):
        case, run = self.fixture()
        compiler = case / "compiler"
        current = case / "key"
        current.write_text(KEY)
        compiler.write_text("#!" + str(Path(sys.executable).resolve()) + "\n" +
            "import json,sys\nfrom pathlib import Path\n" +
            "key=Path(" + repr(str(current)) + ").read_text()\n" +
            "if sys.argv[1]=='project-build-verify':print(json.dumps(dict(status='verified-selected-build-bindings',inputKey=" + repr(KEY) + ")))\n" +
            "elif sys.argv[1]=='project-build-input-key':print(json.dumps(dict(status='observed-project-build-inputs',commandsExecuted=False,inputKey=key)))\n" +
            "else:raise SystemExit(9)\n")
        compiler.chmod(0o700)
        state = case / "state"
        state.mkdir()
        (state / "selected.json").write_text("{}")
        args = argparse.Namespace(compiler=compiler, plan=case/"plan", source=case/"owner",
                                  state=state, context=None, preparation=None,
                                  inspection_timeout_ms=5000)
        self.assertEqual(watch.observe(args, native_run=run), KEY)
        self.assertEqual(watch.verified_selection(args, native_run=run)["inputKey"], KEY)
        payload = {k: str(getattr(args, k)) if getattr(args, k) is not None else None
                   for k in ["compiler", "plan", "source", "state", "context", "preparation"]}
        payload.update(inspectionTimeoutMs=5000, nonce="a"*32,
                       driverDigest=adapter.digest(watch.__file__))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            watch.verify_selected_step(json.dumps(payload), native_run=run)
        self.assertEqual(json.loads(out.getvalue())["inputKey"], KEY)
        self.assertEqual(len(run.calls), 5)
        current.write_text("sha256:" + "b"*64)
        with self.assertRaisesRegex(ValueError, "WATCH_SELECTION_DOES_NOT_MATCH_CURRENT_INPUTS"):
            watch.verified_selection(args, native_run=run)

    def test_payload_cannot_write_control_and_stdout_is_data(self):
        _, run = self.fixture()
        code = ("import json,os\nclosed=True\n"
                "for fd in range(3,64):\n"
                " try:os.write(fd,b'forged-control');closed=False\n"
                " except OSError:pass\n"
                "print(json.dumps(dict(event='payload-stopped',sequence=2,closed=closed)))\n")
        result = self.call(run, self.argv(code))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)["closed"], True)
        records = run.calls[-1]["records"]
        self.assertEqual([r["event"] for r in records],
                         ["launch-pending", "payload-started", "payload-stopped"])
        self.assertNotIn("closed", records[-1])

    def test_early_stdout_close_does_not_finish_guardian(self):
        _, run = self.fixture()
        path, value = run.prepare(self.argv("import os,time;os.close(1);os.close(2);time.sleep(1)"), 5)
        r, w = os.pipe()
        child = None
        rows = []
        try:
            child = run.spawn(path, value, w)
            os.close(w); w = None
            self.collect(r, rows, count=2)
            time.sleep(.15)
            self.assertIsNone(child.poll())
            self.assertTrue(self.live(rows[1]["pid"]))
            out, err = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 0, err)
            self.assertTrue(self.collect(r, rows))
            adapter.validate_records(rows, value["runId"], child.pid)
        finally:
            if w is not None: os.close(w)
            os.close(r)
            if child is not None: watch.stop(child, grace=.2)

    def test_sigterm_escalates_ignored_payload_without_touching_unrelated(self):
        _, run = self.fixture()
        source = ("import signal,time\nfrom pathlib import Path\n"
                  "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
                  "Path('ready').write_text('ready')\ntime.sleep(60)\n")
        path, value = run.prepare(self.argv(source), 8)
        r, w = os.pipe()
        child = None
        rows = []
        unrelated = subprocess.Popen(["/bin/sleep", "60"], start_new_session=True)
        try:
            child = run.spawn(path, value, w)
            os.close(w); w = None
            self.collect(r, rows, count=2)
            self.wait_file(path.parent/"work/ready", child)
            child.send_signal(signal.SIGTERM)
            out, err = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 130, err)
            self.assertTrue(self.collect(r, rows))
            end = adapter.validate_records(rows, value["runId"], child.pid)
            self.assertEqual(end["returncode"], -signal.SIGKILL)
            self.assertFalse(self.live(rows[1]["pid"]))
            self.assertIsNone(unrelated.poll())
        finally:
            if w is not None: os.close(w)
            os.close(r)
            if child is not None: watch.stop(child, grace=.2)
            watch.stop(unrelated, grace=.2)

    def test_actual_parent_sigkill_cleans_separate_payload_group(self):
        case, run = self.fixture()
        path, value = run.prepare(self.argv(
            "import signal,time\nfrom pathlib import Path\n"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
            "Path('ready').write_text('ready')\ntime.sleep(60)"), 8)
        owner_script = case / "owner.py"
        marker = case / "guardian.json"
        owner_script.write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            "sys.path.insert(0," + repr(str(adapter.HERE)) + ")\n"
            "from native_inspection_guard import InspectionRunner\n"
            "p=Path(sys.argv[1]);v=json.loads(p.read_text());fd=int(sys.argv[2])\n"
            "c=InspectionRunner.spawn(p,v,fd,stdout=sys.stdout.buffer,stderr=sys.stderr.buffer)\n"
            "os.close(fd)\nPath(sys.argv[3]).write_text(json.dumps(dict(pid=c.pid)))\nc.wait()\n")
        r, w = os.pipe()
        owner = None
        rows = []
        guardian_pid = None
        try:
            with (case/"owner.stdout").open("xb") as out, (case/"owner.stderr").open("xb") as err:
                owner = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(owner_script),
                                          str(path), str(w), str(marker)],
                                         pass_fds=(w,), stdout=out, stderr=err,
                                         start_new_session=True)
                os.close(w); w = None
                self.collect(r, rows, count=2)
                guardian_pid = rows[0]["guardianPid"]
                self.wait_file(path.parent/"work/ready", owner)
                os.kill(owner.pid, signal.SIGKILL)
                self.assertEqual(owner.wait(timeout=5), -signal.SIGKILL)
                self.assertTrue(self.collect(r, rows))
                end = adapter.validate_records(rows, value["runId"], guardian_pid)
                self.assertEqual(end["returncode"], -signal.SIGKILL)
                deadline = time.monotonic() + 5
                while self.live(guardian_pid) and time.monotonic() < deadline: time.sleep(.05)
                self.assertFalse(self.live(guardian_pid))
                self.assertFalse(self.live(rows[1]["pid"]))
                self.assertNotEqual(rows[1]["pgid"], os.getpgid(os.getpid()))
        finally:
            if w is not None: os.close(w)
            os.close(r)
            if owner is not None: watch.stop(owner, grace=.2)
            if guardian_pid and self.live(guardian_pid): os.kill(guardian_pid, signal.SIGTERM)

    def test_changed_program_binding_refuses_before_payload(self):
        case, run = self.fixture()
        program = case / "program"
        program.write_text("#!/bin/sh\nexit 0\n")
        program.chmod(0o700)
        path, value = run.prepare([str(program)], 5)
        program.write_text("#!/bin/sh\nexit 7\n")
        r, w = os.pipe()
        child = None
        rows = []
        try:
            child = run.spawn(path, value, w)
            os.close(w); w = None
            out, err = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 75)
            self.assertIn(b"INSPECTION_BINDINGS_CHANGED", err)
            self.assertTrue(self.collect(r, rows))
            self.assertEqual(rows, [])
            self.assertEqual(list((path.parent/"work").iterdir()), [])
        finally:
            if w is not None: os.close(w)
            os.close(r)
            if child is not None: watch.stop(child, grace=.2)

    def test_changed_descriptor_refuses_before_spawn(self):
        _, run = self.fixture()
        path, value = run.prepare(self.argv("pass"), 5)
        altered = copy.deepcopy(value)
        altered["timeout"] = 9
        path.write_text(json.dumps(altered))
        r, w = os.pipe()
        try:
            with self.assertRaisesRegex(ValueError, "INSPECTION_DESCRIPTOR_CHANGED"):
                run.spawn(path, value, w)
        finally:
            os.close(r); os.close(w)

    def test_timeout_and_output_overflow_fail_closed(self):
        _, run = self.fixture()
        for code, timeout in [("import time;time.sleep(60)", .5),
                              ("import os;os.write(1,b'x'*1048577)", 5)]:
            with self.assertRaisesRegex(ValueError, "INSPECTION_CONTROL_INCOMPLETE|INSPECTION_GUARDIAN_REFUSED"):
                self.call(run, self.argv(code), timeout=timeout)
            self.assertEqual(run.calls[-1]["guardianExitCode"], 75)
            job = next(p for p in run.root.iterdir()
                       if (p/"control.json").exists()
                       and json.loads((p/"control.json").read_text()) == run.calls[-1])
            self.assertLessEqual((job/"stdout").stat().st_size, adapter.OUTPUT_LIMIT)
            self.assertIn(b"refused-native-inspection:", (job/"stderr").read_bytes())
            starts = [r for r in run.calls[-1]["records"] if r["event"] == "payload-started"]
            self.assertEqual(len(starts), 1)
            self.assertFalse(self.live(starts[0]["pid"]))

    def test_false_missing_duplicate_and_malformed_proof_refused(self):
        _, run = self.fixture()
        self.assertEqual(self.call(run, self.argv("pass")).returncode, 0)
        good = run.calls[-1]["records"]
        run_id, pid = good[0]["runId"], good[0]["guardianPid"]
        bad = [[], good[:2], [*good, good[-1]], [{**good[0], "extra": True}, *good[1:]]]
        for field, val in [("stdoutClosed", False), ("bindingsUnchanged", False),
                           ("pid", float(good[2]["pid"])), ("sequence", True)]:
            altered = copy.deepcopy(good)
            altered[2][field] = val
            bad.append(altered)
        altered = copy.deepcopy(good); altered[1]["runId"] = "0"*32; bad.append(altered)
        for rows in bad:
            with self.assertRaises(ValueError):
                adapter.validate_records(rows, run_id, pid)


if __name__ == "__main__":
    unittest.main()
