"""Real filesystem public-tool controls; fixture installs do not qualify pnpm or Next."""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import qualify_chatbot_next as subject

class PublicPnpmControls(unittest.TestCase):
 def setUp(self):
  self.case=Path(tempfile.mkdtemp(prefix="public-pnpm-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"]))
  self.shared=self.case/"public";self.shared.mkdir()
  self.body=b"controlled public tool fixture\n";self.calls=[]
  self.expected="sha256:"+hashlib.sha256(self.body).hexdigest()
  self.digest_patch=patch.object(subject,"PNPM_ENTRY_DIGEST",self.expected)
  self.digest_patch.start();self.addCleanup(self.digest_patch.stop)
 def install(self,label,argv):
  self.calls.append((label,argv))
  self.assertEqual(label,"pnpm-install-tool")
  self.assertEqual(argv[:2],["npm","install"])
  self.assertIn("pnpm@10.32.1",argv);self.assertIn("--ignore-scripts",argv)
  self.assertEqual(Path(argv[-1]),self.shared/"npm-bootstrap-cache")
  root=Path(argv[argv.index("--prefix")+1]);(root/"node_modules/pnpm/bin").mkdir(parents=True)
  (root/"node_modules/.bin").mkdir()
  (root/"node_modules/.bin/pnpm").symlink_to("../pnpm/bin/pnpm.cjs")
  (root/"node_modules/pnpm/bin/pnpm.cjs").write_bytes(self.body)
  (root/"node_modules/pnpm/package.json").write_text(json.dumps(dict(version="10.32.1")))
  (root/"package-lock.json").write_text('{"controlled":"pinned-public-package"}')
 def create(self):return subject.public_pnpm_bootstrap(self.shared,self.install)
 def test_second_consumer_reuses_complete_identical_tool_without_install(self):
  root,first=self.create();root2,second=self.create()
  self.assertEqual(root,root2);self.assertFalse(first["reused"]);self.assertTrue(second["reused"])
  self.assertEqual(first["identity"],second["identity"]);self.assertEqual(len(self.calls),1)
  self.assertEqual(subject.public_pnpm_identity(root),first["identity"])
 def test_changed_entry_refused_before_another_install(self):
  root,_=self.create();entry=root/"node_modules/pnpm/bin/pnpm.cjs";entry.rename(self.case/"entry.original");entry.write_bytes(b"changed")
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_ENTRY"):self.create()
  self.assertEqual(len(self.calls),1)
 def test_missing_member_refused_without_repairing_or_installing(self):
  root,_=self.create();(root/"package-lock.json").rename(self.case/"lock.original")
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_FILES"):self.create()
  self.assertEqual(len(self.calls),1)
 def test_mode_change_refuses(self):
  root,_=self.create();entry=root/"node_modules/pnpm/bin/pnpm.cjs";entry.chmod(0o700)
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_BOOTSTRAP_CHANGED"):self.create()
  self.assertEqual(len(self.calls),1)
 def test_external_identical_link_refused(self):
  root,_=self.create();outside=self.case/"identical";outside.write_bytes(self.body)
  (root/"external-link").symlink_to(outside)
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_EXTERNAL_LINK"):self.create()
  self.assertEqual(len(self.calls),1)
 def test_partial_bootstrap_refuses_without_install(self):
  (self.shared/"pnpm-bootstrap").mkdir()
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_PARTIAL_BOOTSTRAP"):self.create()
  self.assertFalse(self.calls)
 def test_missing_seal_and_symlink_seal_refuse_without_install(self):
  root,_=self.create();seal=self.shared/"pnpm-bootstrap.json";seal.rename(self.case/"seal.original")
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_PARTIAL_BOOTSTRAP"):self.create()
  seal.symlink_to(self.case/"seal.original")
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_PARTIAL_BOOTSTRAP"):self.create()
  self.assertEqual(len(self.calls),1)
 def test_wrong_pinned_version_refused_without_writing_seal(self):
  def install_wrong(label,argv):
   self.install(label,argv);p=self.shared/"pnpm-bootstrap/node_modules/pnpm/package.json";p.rename(self.case/"package.original");p.write_text('{"version":"other"}')
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_VERSION"):subject.public_pnpm_bootstrap(self.shared,install_wrong)
  self.assertFalse((self.shared/"pnpm-bootstrap.json").exists())
 def test_extra_member_refuses_even_with_identical_entry(self):
  root,_=self.create();(root/"unexpected").write_text("additional public member")
  with self.assertRaisesRegex(AssertionError,"PUBLIC_PNPM_BOOTSTRAP_CHANGED"):self.create()
  self.assertEqual(len(self.calls),1)

if __name__=="__main__":unittest.main()
