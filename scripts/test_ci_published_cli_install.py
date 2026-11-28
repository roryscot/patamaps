import tempfile
import unittest
from pathlib import Path

from ci_published_cli_install import executable_path


class ExecutablePathTests(unittest.TestCase):
    def test_preserves_rustup_proxy_name_instead_of_resolving_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            bindir = Path(temporary) / "bin"
            bindir.mkdir()
            rustup = bindir / "rustup"
            rustup.write_text("shim target")
            cargo = bindir / "cargo"
            rustc = bindir / "rustc"
            cargo.symlink_to(rustup)
            rustc.symlink_to(rustup)

            self.assertEqual(executable_path(cargo), cargo)
            self.assertEqual(executable_path(rustc), rustc)
            self.assertEqual(executable_path(cargo).name, "cargo")

    def test_rejects_missing_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                executable_path(Path(temporary) / "cargo")


if __name__ == "__main__":
    unittest.main()
