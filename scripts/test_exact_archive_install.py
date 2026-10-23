"""Archive install boundaries; preserve all generated cases."""
import io,os,tarfile,tempfile,unittest
from pathlib import Path
from cross_stack_package import install_archive
class InstallArchiveControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  parent=Path(os.environ["PATAMAPS_TEST_RETAIN_ROOT"]);assert parent.is_dir()
  cls.work=Path(tempfile.mkdtemp(prefix="exact-archive-install-",dir=parent))
 def archive(self,members):
  case=self.work/self._testMethodName;case.mkdir();path=case/"package.tar.gz"
  with tarfile.open(path,"w:gz") as t:
   for name,data,kind in members:
    m=tarfile.TarInfo(name);m.mode=0o755
    if kind=="symlink":m.type=tarfile.SYMTYPE;m.linkname="outside";t.addfile(m)
    else:m.size=len(data);t.addfile(m,io.BytesIO(data))
  return case,path
 def reject(self,members):
  case,path=self.archive(members)
  with self.assertRaises((AssertionError,ValueError)):install_archive(path,case/"installed",case)
  self.assertFalse((case/"outside").exists())
 def test_valid_exact_bytes_and_executable(self):
  case,path=self.archive([("package/bin/cli",b"verified",None)])
  root=install_archive(path,case/"installed",case)
  self.assertEqual((root/"bin/cli").read_bytes(),b"verified");self.assertTrue(os.access(root/"bin/cli",os.X_OK))
 def test_traversal(self):self.reject([("../../outside",b"x",None)])
 def test_absolute(self):self.reject([(str(self.work/self._testMethodName/"outside"),b"x",None)])
 def test_symbolic_link(self):self.reject([("package/link",b"","symlink")])
 def test_multiple_prefixes(self):self.reject([("first/a",b"a",None),("second/b",b"b",None)])
 def test_duplicate(self):self.reject([("package/a",b"a",None),("package/a",b"b",None)])
 def test_normalized_duplicate(self):self.reject([("package/a",b"a",None),("package/./a",b"b",None)])
 def test_existing_destination(self):
  case,path=self.archive([("package/a",b"a",None)]);target=case/"installed";target.mkdir();(target/"sentinel").write_text("keep")
  with self.assertRaises(FileExistsError):install_archive(path,target,case)
  self.assertEqual((target/"sentinel").read_text(),"keep")
if __name__=="__main__":unittest.main()
