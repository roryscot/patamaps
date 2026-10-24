"""Real Git partial-fetch/index controls; all fixtures are retained, never auto-purged."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from qualify_fumadocs_next import acquire_source, excluded


class SourceAcquisition(unittest.TestCase):
    def fixture(self, unsafe_link=False):
        parent = os.environ.get("PATAMAPS_TEST_RETAIN_ROOT")
        self.assertIsNotNone(parent, "Explicit retained fixture root required")
        root = Path(tempfile.mkdtemp(prefix="next-source-", dir=parent))
        origin = root / "origin"
        origin.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
        def git(*args, data=None, cwd=origin):
            return subprocess.check_output(["git", *args], cwd=cwd, input=data, env=env, stderr=subprocess.PIPE)
        git("init")
        files = {"package.json": '{"name":"fixture"}\n',
                 "apps/docs/.env": "CONTROL_ONLY_NOT_A_CREDENTIAL=one\n",
                 ".env.empty": "", ".npmrc": "CONTROL_ONLY_NOT_A_CREDENTIAL=two\n",
                 ".gitkeep": "", "docs/readme.md": "retained source\n",
                 "apps/docs/app/(group)/[id]/page.tsx": "export default function Page() { return null; }\n"}
        for name, text in files.items():
            path = origin / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (origin / "README.md").symlink_to(".env.empty" if unsafe_link else "docs/readme.md")
        git("add", "--all")
        tree = git("write-tree").decode().strip()
        revision = git("-c", "user.name=Rory Dahl", "-c", "user.email=rory.dahl@protonmail.com",
                       "commit-tree", tree, "-m", "Controlled source-acquisition fixture").decode().strip()
        git("update-ref", "refs/heads/main", revision)
        git("config", "uploadpack.allowFilter", "true")
        git("config", "uploadpack.allowAnySHA1InWant", "true")
        work, evidence = root / "work", root / "evidence"
        work.mkdir()
        evidence.mkdir()
        def run(label, command, cwd=None, data=None, **kwargs):
            return subprocess.check_output([str(a) for a in command], cwd=cwd, input=data,
                                           env=env, stderr=subprocess.PIPE)
        return origin, work, evidence, revision, run

    def test_reserved_paths_and_normal_names(self):
        for name in [".env", "apps/docs/.env", ".env.empty", "a/.npmrc", ".ssh/key"]:
            self.assertTrue(excluded(name), name)
        for name in ["next.config.mts", "apps/docs/environment.ts", "docs/readme.md",
                     "apps/docs/app/(group)/[id]/page.tsx"]:
            self.assertFalse(excluded(name), name)

    def test_actual_partial_fetch_omits_reserved_files_and_unique_blobs(self):
        origin, work, evidence, revision, run = self.fixture()
        owner, selected, omitted, inventory, audit = acquire_source(
            run, work, evidence, upstream=origin.as_uri(), revision=revision)
        self.assertEqual(len(selected), 5)
        self.assertEqual(len(omitted), 3)
        self.assertEqual(len(inventory), 5)
        self.assertFalse((owner / "apps/docs/.env").exists())
        self.assertFalse((owner / ".env.empty").exists())
        self.assertFalse((owner / ".npmrc").exists())
        self.assertTrue((owner / ".gitkeep").exists(), "Shared empty blob must remain usable through allowed path")
        self.assertEqual(os.readlink(owner / "README.md"), "docs/readme.md")
        self.assertTrue((owner / "apps/docs/app/(group)/[id]/page.tsx").is_file())
        audit("test-final-audit")

    def test_explicit_other_project_omission_profile_keeps_blob_audits(self):
        origin, work, evidence, revision, run = self.fixture()
        owner, selected, omitted, inventory, audit = acquire_source(
            run, work, evidence, upstream=origin.as_uri(), revision=revision,
            required_omissions=(".env.empty",))
        self.assertFalse((owner / ".env.empty").exists())
        self.assertEqual(len(inventory), 5)
        audit("other-profile-final-audit")

    def test_link_to_excluded_path_refuses_closed_source(self):
        origin, work, evidence, revision, run = self.fixture(unsafe_link=True)
        with self.assertRaises(FileNotFoundError):
            acquire_source(run, work, evidence, upstream=origin.as_uri(), revision=revision)
        self.assertFalse((work / "source/.env.empty").exists())


if __name__ == "__main__":
    unittest.main()
