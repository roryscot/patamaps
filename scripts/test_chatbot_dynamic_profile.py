"""Pinned source identity and compiled route admission controls; retain fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import chatbot_dynamic_profile as profile

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "docs/acceptance/project-adoption/g3-next-dynamic-runtime-20261024/intake.json"
OBSERVATION = ROOT / "docs/acceptance/project-adoption/g3-chatbot-source-20261023/native-observations.json"


class DynamicProfile(unittest.TestCase):
    def fixture(self):
        parent = os.environ.get("PATAMAPS_TEST_RETAIN_ROOT")
        self.assertIsNotNone(parent, "Explicit retained fixture root required")
        return Path(tempfile.mkdtemp(prefix="dynamic-profile-", dir=parent))

    def observed(self):
        return json.loads(OBSERVATION.read_bytes())

    def test_matches_frozen_source_and_runtime_contract(self):
        intake = json.loads(INTAKE.read_bytes())
        self.assertEqual(profile.SOURCE_BLOBS, intake["publicGitBlobs"])
        self.assertEqual(profile.DYNAMIC_CONTROLS, set(intake["runtimeControls"]))
        self.assertEqual(len(profile.DYNAMIC_CONTROLS), 13)

    def test_exact_git_blob_source_bytes(self):
        root = self.fixture()
        path = root / "page.tsx"
        raw = b"export default function Page() { return null; }\n"
        path.write_bytes(raw)
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        with patch.object(profile, "SOURCE_BLOBS", {"page.tsx": blob}):
            record = profile.verify_sources(root)
        self.assertEqual(record["gitBlobs"], {"page.tsx": blob})
        self.assertFalse(record["sourceMutated"])
        self.assertEqual(path.read_bytes(), raw)

    def test_changed_source_refuses_without_mutation(self):
        root = self.fixture()
        path = root / "page.tsx"
        path.write_bytes(b"changed source\n")
        with patch.object(profile, "SOURCE_BLOBS", {"page.tsx": "0" * 40}):
            with self.assertRaisesRegex(AssertionError, "DYNAMIC_OWNER_SOURCE_CHANGED"):
                profile.verify_sources(root)
        self.assertEqual(path.read_bytes(), b"changed source\n")

    def test_source_link_refuses_without_touching_target(self):
        root = self.fixture()
        target = root / "target.tsx"
        target.write_bytes(b"target preserved\n")
        (root / "page.tsx").symlink_to(target.name)
        with patch.object(profile, "SOURCE_BLOBS", {"page.tsx": "0" * 40}):
            with self.assertRaisesRegex(AssertionError, "DYNAMIC_OWNER_SOURCE_FILE"):
                profile.verify_sources(root)
        self.assertEqual(target.read_bytes(), b"target preserved\n")

    def test_real_compiled_fixture_preserves_opaque_observation_scope(self):
        observed = self.observed()
        before = copy.deepcopy(observed)
        record = profile.verify_compiled(observed)
        self.assertEqual(len(record["bindings"]), 3)
        self.assertFalse(record["nativeRuntimeClaim"])
        self.assertFalse(record["regexExecuted"])
        self.assertTrue(record["runtimeWitnessRequired"])
        self.assertEqual(observed, before)

    def test_missing_or_duplicate_dynamic_binding_refuses(self):
        for duplicate in [False, True]:
            observed = self.observed()
            entities = observed["shard"]["entities"]
            entity = next(e for e in entities if e["kind"] == "next-build-route"
                          and e["attributes"].get("page") == "/chat/[id]")
            if duplicate:
                entities.append(copy.deepcopy(entity))
            else:
                entities.remove(entity)
            with self.assertRaisesRegex(AssertionError, "DYNAMIC_NATIVE_REQUIRED_BINDING"):
                profile.verify_compiled(observed)

    def test_wrong_physical_module_refuses(self):
        observed = self.observed()
        entity = next(e for e in observed["shard"]["entities"] if e["kind"] == "next-build-module"
                      and e["attributes"].get("routePath") == "/chat/[id]")
        entity["attributes"]["moduleFile"] = "app/chat/[id]/page.js"
        with self.assertRaisesRegex(AssertionError, "DYNAMIC_NATIVE_MODULE_BINDING"):
            profile.verify_compiled(observed)

    def test_invented_category_methods_or_executed_regex_refuses(self):
        for key, value in [("category", "static"), ("httpMethods", "GET"), ("regexExecuted", True)]:
            observed = self.observed()
            entity = next(e for e in observed["shard"]["entities"] if e["kind"] == "next-build-route"
                          and e["attributes"].get("page") == "/chat/[id]")
            entity["attributes"][key] = value
            with self.assertRaisesRegex(AssertionError, "DYNAMIC_NATIVE_ROUTE_CLASSIFICATION"):
                profile.verify_compiled(observed)

    def test_invented_native_runtime_claim_refuses(self):
        observed = self.observed()
        observed["shard"]["metadata"]["observation"]["runtimeEstablished"] = True
        with self.assertRaisesRegex(AssertionError, "DYNAMIC_NATIVE_OBSERVATION_SCOPE"):
            profile.verify_compiled(observed)

    def test_only_original_runtime_profile_is_admitted(self):
        profile.validate_mode(runtime=True)
        for values in [dict(runtime=False), *[dict(runtime=True, **{key: True})
                       for key in ["rewrites", "standalone", "retained", "installed"]]]:
            with self.assertRaisesRegex(AssertionError, "DYNAMIC_QUALIFICATION_PROFILE"):
                profile.validate_mode(**values)

    def test_invalid_cli_mode_refuses_before_effects(self):
        root = self.fixture()
        work, evidence = root / "work", root / "evidence"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/qualify_chatbot_next.py"),
                                 "--dynamic-routes", "--work", str(work), "--evidence", str(evidence),
                                 "--cli", str(root / "unavailable-compiler")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DYNAMIC_QUALIFICATION_PROFILE", result.stderr)
        self.assertFalse(work.exists())
        self.assertFalse(evidence.exists())


if __name__ == "__main__":
    unittest.main()
