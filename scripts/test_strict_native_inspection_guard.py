"""Darwin strict-mode guardian controls; fixtures are retained, never deleted."""
from pathlib import Path
import copy
import json
import os
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

import native_inspection_guard as adapter
import test_native_inspection_guard as baseline
import project_watch as watch


@unittest.skipUnless(sys.platform == "darwin", "requires qualified Darwin kernel")
class StrictInspectionGuardian(baseline.InspectionGuardian):
    def fixture(self):
        case, old = super().fixture()
        return case, adapter.InspectionRunner(old.root, case, strict=True, stop_grace=.2)

    def locked(self):
        case, run = self.fixture()
        state = case / "state"
        state.mkdir(mode=0o700)
        lock = state / "driver.lock"
        lock.touch(mode=0o600)
        return case, lock, adapter.InspectionRunner(run.root, case, driver_lock=lock, stop_grace=.2)

    def test_exact_lock_open_and_flock_retains_identity(self):
        _, lock, run = self.locked()
        before = lock.stat()
        source = ("import os,fcntl\n"
                  "fd=os.open(" + repr(str(lock)) + ",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)\n"
                  "fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                  "fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd);print('locked')\n")
        result = self.call(run, self.argv(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"locked\n")
        after = lock.stat()
        self.assertEqual((before.st_dev,before.st_ino,before.st_nlink,before.st_size),
                         (after.st_dev,after.st_ino,after.st_nlink,after.st_size))

    def test_lock_mutation_after_prepare_refuses_before_payload(self):
        _, lock, run = self.locked()
        path, value = run.prepare(self.argv("print('must-not-run')"), 5)
        lock.write_bytes(b"changed")
        r,w = os.pipe()
        child = None
        rows = []
        try:
            child = run.spawn(path,value,w)
            os.close(w);w=None
            out,err = child.communicate(timeout=8)
            self.assertEqual(child.returncode,75)
            self.assertIn(b"refused-native-inspection:",err)
            self.assertEqual(out,b"")
            self.assertTrue(self.collect(r,rows))
            self.assertEqual(rows,[])
            self.assertEqual(list((path.parent/"work").iterdir()),[])
        finally:
            if w is not None:os.close(w)
            os.close(r)
            if child is not None:watch.stop(child,grace=.2)

    def test_allowed_lock_write_invalidates_completion_proof(self):
        _, lock, run = self.locked()
        source = "from pathlib import Path;Path(" + repr(str(lock)) + ").write_bytes(b'changed')"
        with self.assertRaisesRegex(ValueError,"INSPECTION_STOP_UNCONFIRMED"):
            self.call(run,self.argv(source))
        self.assertEqual(lock.read_bytes(),b"changed")
        value = run.calls[-1]
        self.assertEqual(value["guardianExitCode"],0)
        self.assertIs(value["records"][-1]["bindingsUnchanged"],False)
        self.assertFalse(self.live(value["records"][1]["pid"]))

    def test_unknown_strict_kind_never_runs_unconfined(self):
        _,run = self.fixture()
        path,value = run.prepare(self.argv("print('must-not-run')"),5)
        value["inspection"]["kind"] = "caller-supplied-profile"
        path.write_text(json.dumps(value))
        r,w = os.pipe()
        child = None
        rows = []
        try:
            child = run.spawn(path,value,w)
            os.close(w);w=None
            out,err = child.communicate(timeout=8)
            self.assertEqual(child.returncode,75)
            self.assertIn(b"INSPECTION_MODE_PROTOCOL",err)
            self.assertEqual(out,b"")
            self.assertTrue(self.collect(r,rows))
            self.assertEqual(rows,[])
        finally:
            if w is not None:os.close(w)
            os.close(r)
            if child is not None:watch.stop(child,grace=.2)

    def test_unavailable_strict_platform_refuses_before_job_creation(self):
        case,run = self.fixture()
        with patch.object(adapter.sys,"platform","linux"):
            with self.assertRaisesRegex(RuntimeError,"isolation is unavailable"):
                adapter.InspectionRunner(run.root,case,strict=True)
        self.assertEqual(list(run.root.iterdir()),[])


if __name__ == "__main__":
    unittest.main()
