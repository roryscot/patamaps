"""Small retained fixtures for host storage controls; no native build runs."""
import ast
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import retained_copy
import storage_guard

BASE = storage_guard.ROOT / ".tools/storage-guard-tests"
BASE.mkdir(parents=True, exist_ok=True)
FIXTURES = Path(tempfile.mkdtemp(prefix="controls-", dir=BASE))
print(f"Retained storage guard fixtures: {FIXTURES}")


class StorageGuardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURES / self.id().split(".")[-1]
        self.fixture.mkdir()
        self.install = self.fixture / "installed"
        self.install.mkdir()
        engine = self.fixture / "engine/scripts/guarded-run.mjs"
        engine.parent.mkdir(parents=True)
        (engine.parent.parent / "storage-policy.json").write_text(
            json.dumps({"reserveFreeBytes": 10000000000}))
        (self.install / "projects.json").write_text(json.dumps({
            "engine": str(engine), "node": "/configured/node"}))
        self.lease = self.fixture / "lease/active-run"
        self.lease.mkdir(parents=True)
        (self.lease / "owner.json").write_text(json.dumps({
            "pid": os.getpid(), "token": "matching-test-token"}))
        self.environment = {
            "LOCAL_STORAGE_PROJECT": str(storage_guard.ROOT),
            "WARGAME_STORAGE_LEASE_DIR": str(self.lease.parent),
            "WARGAME_STORAGE_OWNER_PID": str(os.getpid()),
            "WARGAME_STORAGE_RUN_TOKEN": "matching-test-token",
        }

    def test_only_matching_live_project_owner_is_inherited(self):
        with patch.dict(os.environ, self.environment, clear=True):
            self.assertTrue(storage_guard.live_parent())
            os.environ["WARGAME_STORAGE_RUN_TOKEN"] = "forged"
            self.assertFalse(storage_guard.live_parent())
            os.environ.update(self.environment)
            os.environ["LOCAL_STORAGE_PROJECT"] = "different-project"
            self.assertFalse(storage_guard.live_parent())

    def test_dead_owner_is_not_inherited(self):
        with patch.dict(os.environ, self.environment, clear=True), \
                patch.object(storage_guard.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(storage_guard.live_parent())

    def test_reserve_boundary_and_evidence_preservation(self):
        evidence = self.fixture / "evidence.txt"
        evidence.write_bytes(b"retain unique original")
        with patch.object(storage_guard, "INSTALL", self.install):
            with patch.object(storage_guard.shutil, "disk_usage", return_value=SimpleNamespace(free=9999999999)):
                with self.assertRaises(RuntimeError):
                    storage_guard.check_reserve()
            with patch.object(storage_guard.shutil, "disk_usage", return_value=SimpleNamespace(free=10000000000)):
                storage_guard.check_reserve()
        self.assertEqual(evidence.read_bytes(), b"retain unique original")

    def test_both_copy_helpers_refuse_before_creating_destination(self):
        source = self.fixture / "original.txt"
        source.write_bytes(b"retain original source")
        folder = self.fixture / "original-tree"
        folder.mkdir()
        (folder / "evidence.txt").write_bytes(b"retain original tree")
        with patch.object(storage_guard, "INSTALL", self.install), \
                patch.object(storage_guard.shutil, "disk_usage", return_value=SimpleNamespace(free=0)), \
                patch.object(retained_copy.subprocess, "run") as command:
            for function, original in [(retained_copy.copy_file, source), (retained_copy.copy_tree, folder)]:
                destination = self.fixture / "uncreated-parent" / function.__name__
                with self.assertRaises(RuntimeError):
                    function(original, destination)
                self.assertFalse(destination.parent.exists())
            command.assert_not_called()
        self.assertEqual(source.read_bytes(), b"retain original source")
        self.assertEqual((folder / "evidence.txt").read_bytes(), b"retain original tree")

    def test_supervisor_refusal_propagates_without_allocation(self):
        with patch.object(storage_guard, "INSTALL", self.install), \
                patch.object(storage_guard, "live_parent", return_value=False), \
                patch.object(storage_guard.subprocess, "run", return_value=SimpleNamespace(returncode=75)) as command:
            before = set(self.fixture.iterdir())
            with self.assertRaises(SystemExit) as rejection:
                storage_guard.ensure_guarded()
            self.assertEqual(rejection.exception.code, 75)
            self.assertEqual(set(self.fixture.iterdir()), before)
            self.assertEqual(command.call_count, 1)

    def test_missing_installation_does_not_launch(self):
        with patch.object(storage_guard, "INSTALL", self.fixture / "missing"), \
                patch.object(storage_guard, "live_parent", return_value=False), \
                patch.object(storage_guard.subprocess, "run") as command:
            with self.assertRaises(FileNotFoundError):
                storage_guard.ensure_guarded()
            command.assert_not_called()

    def test_entrypoints_guard_before_output_or_source_configuration(self):
        scripts = ["native.py", "prepare_oracle.py", "discovery_api.py",
                   "sdk_consumer.py", "scientific_bounds.py"]
        for name in scripts:
            tree = ast.parse((Path(__file__).parent / name).read_text())
            statements = [node for node in tree.body
                          if not isinstance(node, (ast.Import, ast.ImportFrom))
                          and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))]
            first = statements[0]
            self.assertIsInstance(first, ast.Expr, name)
            self.assertIsInstance(first.value, ast.Call, name)
            self.assertEqual(first.value.func.id, "ensure_guarded", name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
