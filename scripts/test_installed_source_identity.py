"""Bound installed-source inventory checks; preserve every generated case."""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from installed_selected import verify_installed_source

def digest(raw):return "sha256:"+hashlib.sha256(raw).hexdigest()

class InstalledSourceControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix="installed-source-guard-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"]))
 def prepare(self,entries=None):
  root=self.root/self._testMethodName;root.mkdir();(root/"a.txt").write_bytes(b"bound source")
  rows=entries or [dict(path="a.txt",bytes=12,digest=digest(b"bound source"))]
  raw=(json.dumps(rows)+"\n").encode();(root/"source-inventory.json").write_bytes(raw)
  return root,digest(raw)
 def test_exact_source_without_git(self):
  root,binding=self.prepare();self.assertFalse((root/".git").exists())
  result=verify_installed_source(root,binding);self.assertEqual(result["sourceFiles"],1)
 def test_changed_bytes(self):
  root,binding=self.prepare();(root/"a.txt").write_bytes(b"changed data")
  with self.assertRaisesRegex(AssertionError,"BYTES_CHANGED"):verify_installed_source(root,binding)
 def test_changed_manifest(self):
  root,binding=self.prepare();(root/"source-inventory.json").write_bytes(b"[]")
  with self.assertRaisesRegex(AssertionError,"INVENTORY_CHANGED"):verify_installed_source(root,binding)
 def test_missing_member(self):
  root,binding=self.prepare();(root/"a.txt").rename(self.root/"missing-original.retained")
  with self.assertRaisesRegex(AssertionError,"MEMBERS_CHANGED"):verify_installed_source(root,binding)
 def test_extra_member(self):
  root,binding=self.prepare();(root/"extra.txt").write_text("retained")
  with self.assertRaisesRegex(AssertionError,"MEMBERS_CHANGED"):verify_installed_source(root,binding)
 def test_identical_external_symlink_refuses(self):
  root,binding=self.prepare();original=self.root/"external-original.retained";(root/"a.txt").rename(original);(root/"a.txt").symlink_to(original)
  with self.assertRaisesRegex(AssertionError,"SYMLINK"):verify_installed_source(root,binding)
 def test_traversal_refuses(self):
  root,binding=self.prepare([dict(path="../outside",bytes=0,digest=digest(b""))])
  with self.assertRaisesRegex(AssertionError,"SOURCE_PATH"):verify_installed_source(root,binding)
 def test_duplicate_member_refuses(self):
  entry=dict(path="a.txt",bytes=12,digest=digest(b"bound source"));root,binding=self.prepare([entry,entry])
  with self.assertRaisesRegex(AssertionError,"SOURCE_ENTRY"):verify_installed_source(root,binding)
 def test_boolean_size_refuses(self):
  root,binding=self.prepare([dict(path="a.txt",bytes=True,digest=digest(b"bound source"))])
  with self.assertRaisesRegex(AssertionError,"SOURCE_BYTES"):verify_installed_source(root,binding)
 def test_wrong_binding_refuses(self):
  root,_=self.prepare()
  with self.assertRaisesRegex(AssertionError,"INVENTORY_CHANGED"):verify_installed_source(root,"sha256:"+"0"*64)

if __name__=="__main__":unittest.main()
