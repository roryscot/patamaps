"""Archive install boundaries; preserve all generated cases."""
import io,os,stat,tarfile,tempfile,unittest
from qualify_installed_miniserve import install_selected_state
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
 def test_selected_state_directory_modes(self):
  case=self.work/self._testMethodName;case.mkdir();archive=case/"state.tar.gz"
  with tarfile.open(archive,"w:gz") as t:
   d=tarfile.TarInfo("selected-state/context");d.type=tarfile.DIRTYPE;d.mode=0o700;t.addfile(d)
   f=tarfile.TarInfo("selected-state/context/runtime");f.size=1;f.mode=0o755;t.addfile(f,io.BytesIO(b"x"))
  installed=install_selected_state(archive,case/"import")
  self.assertEqual(stat.S_IMODE((installed/"context").stat().st_mode),0o700)
  self.assertEqual(stat.S_IMODE((installed/"context/runtime").stat().st_mode),0o755)
 def test_existing_destination(self):
  case,path=self.archive([("package/a",b"a",None)]);target=case/"installed";target.mkdir();(target/"sentinel").write_text("keep")
  with self.assertRaises(FileExistsError):install_archive(path,target,case)
  self.assertEqual((target/"sentinel").read_text(),"keep")
 def test_registry_state_explicit_profile(self):
  case,path=self.archive([("registry-state/candidate/cache/member.crate",b"original controlled bytes",None)])
  installed=install_selected_state(path,case/"import",profile="registry")
  self.assertEqual((installed/"candidate/cache/member.crate").read_bytes(),b"original controlled bytes")
  with self.assertRaises(AssertionError):install_selected_state(path,case/"default-refuses")
 def test_registry_state_unknown_profile(self):
  case,path=self.archive([("registry-state/member",b"x",None)])
  with self.assertRaisesRegex(ValueError,"IMPORT_PROFILE"):install_selected_state(path,case/"import",profile="unknown")
  self.assertFalse((case/"import").exists())
 def test_registry_state_traversal(self):
  case,path=self.archive([("registry-state/../../outside",b"x",None)])
  with self.assertRaises(AssertionError):install_selected_state(path,case/"import",profile="registry")
  self.assertFalse((case/"outside").exists())
 def test_registry_state_symlink(self):
  case,path=self.archive([("registry-state/link",b"","symlink")])
  with self.assertRaises(AssertionError):install_selected_state(path,case/"import",profile="registry")
 def test_registry_state_duplicate(self):
  case,path=self.archive([("registry-state/a",b"a",None),("registry-state/a",b"b",None)])
  with self.assertRaises(AssertionError):install_selected_state(path,case/"import",profile="registry")
if __name__=="__main__":unittest.main()
