"""Refuse incomplete installed dynamic cases; use an actual accepted owner receipt."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chatbot_dynamic_profile import validate_mode
from qualify_installed_next import dynamic_case_result
import qualify_chatbot_next

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / "docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024/accepted-40125656603"

class InstalledDynamicControls(unittest.TestCase):
    def sample(self):
        return tuple(json.loads((ACCEPTED / name).read_bytes())
                     for name in ["receipt.json", "runtime.json", "browser-auth.json"])

    def fixture(self):
        parent = os.environ.get("PATAMAPS_TEST_RETAIN_ROOT")
        self.assertIsNotNone(parent, "Explicit retained fixture root required")
        return Path(tempfile.mkdtemp(prefix="installed-dynamic-", dir=parent))

    def test_complete_actual_profile_admits(self):
        result = dynamic_case_result(*self.sample())
        self.assertTrue(result["originalOwnerConfigurationPreserved"])
        self.assertTrue(result["dynamicRouteWitness"]["fixturesUnchanged"])

    def test_each_required_final_qualification_must_pass(self):
        for key in ["buildBindingsVerified", "runtimeAccepted", "sourceBytesUnchanged",
                    "privateEvidenceBarrierPassed", "ownedRuntimesStopped"]:
            values = self.sample()
            values[0]["dynamicRouteQualification"][key] = False
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "QUALIFICATION"):
                dynamic_case_result(*values)

    def test_original_owner_membership_and_git_blobs_required(self):
        for key in ["sourceFiles", "sourceTextFiles"]:
            values = self.sample(); values[0][key] -= 1
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "OWNER_SOURCE"):
                dynamic_case_result(*values)
        values = self.sample()
        blobs = values[0]["dynamicSourceBindings"]["gitBlobs"]
        blobs[next(iter(blobs))] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "SOURCE_BINDINGS"):
            dynamic_case_result(*values)

    def test_overlaid_or_retained_profiles_cannot_be_promoted(self):
        for key in ["rewriteQualification", "standaloneProbe", "retainedSelectedExecution"]:
            values = self.sample(); values[0][key] = {}
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "ORIGINAL_PROFILE"):
                dynamic_case_result(*values)

    def test_scope_and_private_evidence_flags_are_authoritative(self):
        for key in ["sourceMutationRequested", "qualificationConfigurationOverlay", "credentialsCaptured",
                    "rawRuntimeLogsUploaded", "externalModelAccepted"]:
            values = self.sample(); values[1][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "RUNTIME_SCOPE"):
                dynamic_case_result(*values)

    def test_duplicate_missing_or_failed_controls_refuse(self):
        for mutate in ["duplicate", "missing", "failed"]:
            values = self.sample(); controls = values[2]["controls"]
            if mutate == "duplicate": controls[-1] = copy.deepcopy(controls[0])
            if mutate == "missing": controls.pop()
            if mutate == "failed": controls[-1]["passed"] = False
            with self.subTest(mutate=mutate), self.assertRaisesRegex(AssertionError, "EXACT_CONTROLS"):
                dynamic_case_result(*values)

    def test_both_upstream_test_counts_required(self):
        for index in [1, 2]:
            values = self.sample(); values[index]["upstreamPageTests"] = 3
            with self.subTest(index=index), self.assertRaisesRegex(AssertionError, "UPSTREAM_TESTS"):
                dynamic_case_result(*values)

    def test_browser_shutdown_required(self):
        for key in ["ownedBrowserStopped", "ownedHttpsProxyStopped"]:
            values = self.sample(); values[2][key] = False
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "BROWSER_CLEANUP"):
                dynamic_case_result(*values)

    def test_witness_copies_must_agree(self):
        values = self.sample()
        values[2]["dynamicRouteWitness"]["fixturesUnchanged"] = False
        with self.assertRaisesRegex(AssertionError, "WITNESS_BINDING"):
            dynamic_case_result(*values)

    def test_wrong_refusal_status_cannot_be_promoted(self):
        values = self.sample()
        for index in [1, 2]: values[index]["dynamicRouteWitness"]["guestPrivateStatus"] = 200
        with self.assertRaisesRegex(AssertionError, "REFUSAL_STATUS"):
            dynamic_case_result(*values)

    def test_changed_fixtures_or_generation_or_disclosure_refuse(self):
        for key, value in [("fixturesUnchanged", False), ("generationPostAttempts", 1),
                           ("rawFixtureValuesPublished", True)]:
            values = self.sample()
            for index in [1, 2]: values[index]["dynamicRouteWitness"][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                dynamic_case_result(*values)

    def test_only_explicit_verified_installation_can_admit(self):
        validate_mode(runtime=True, installed=True, verified_installation=True)
        for verified in [False, None, "true", 1]:
            with self.subTest(verified=verified), self.assertRaisesRegex(AssertionError, "DYNAMIC_QUALIFICATION_PROFILE"):
                validate_mode(runtime=True, installed=True, verified_installation=verified)

    def test_unverified_installed_cli_refuses_before_effects(self):
        root = self.fixture()
        work, evidence, marker = root / "work", root / "evidence", root / "compiler.marker"
        sentinel = root / "compiler.sh"
        sentinel.write_text("#!/bin/sh\nexit 91\n"); sentinel.chmod(0o700)
        argv = ["qualify_chatbot_next.py", "--dynamic-routes", "--runtime",
                "--installed-inventory-digest", "sha256:" + "0" * 64,
                "--cli", str(sentinel), "--work", str(work), "--evidence", str(evidence)]
        with patch.object(sys, "argv", argv), patch("platform.system", return_value="Linux"), \
             patch("platform.machine", return_value="x86_64"), patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
             patch("subprocess.Popen", side_effect=AssertionError("compiler or child started")):
            with self.assertRaisesRegex((AssertionError, FileNotFoundError), "INSTALLED_SOURCE"):
                qualify_chatbot_next.main()
        self.assertFalse(work.exists()); self.assertFalse(evidence.exists()); self.assertFalse(marker.exists())

    def test_parent_rejects_retained_combination_before_effects(self):
        root = self.fixture()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/qualify_installed_next.py"),
                                 "--dynamic-routes", "--retained-runtime",
                                 "--work", str(root / "work"), "--evidence", str(root / "evidence")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INSTALLED_DYNAMIC_PROFILE_COMBINATION", result.stderr)
        self.assertFalse((root / "work").exists()); self.assertFalse((root / "evidence").exists())

if __name__ == "__main__":
    unittest.main()
