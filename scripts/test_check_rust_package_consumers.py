import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from check_rust_package_consumers import unpack


class PackageExtraction(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(
            prefix="patamaps-package-consumer-test-",
            dir=os.environ.get("PATAMAPS_TEST_RETAIN_ROOT"),
        ))

    def archive(self, name, entries):
        path = self.root / name
        with tarfile.open(path, "w:gz") as out:
            for member, data, kind in entries:
                info = tarfile.TarInfo(member)
                if kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = "elsewhere"
                    out.addfile(info)
                else:
                    info.size = len(data)
                    out.addfile(info, io.BytesIO(data))
        return path

    def test_regular_package_file_is_preserved(self):
        archive = self.archive("safe.crate", [("core-1/src/lib.rs", b"example", "file")])
        dest = self.root / "safe"
        dest.mkdir()
        unpack(archive, dest, "core-1")
        self.assertEqual((dest / "core-1/src/lib.rs").read_bytes(), b"example")

    def test_traversal_symlinks_and_duplicate_members_are_refused(self):
        cases = [
            [("core-1/../../outside", b"x", "file")],
            [("core-1/link", b"", "symlink")],
            [("core-1/src/a", b"a", "file"), ("core-1/src/a", b"b", "file")],
        ]
        for index, entries in enumerate(cases):
            with self.subTest(index=index):
                archive = self.archive(f"bad-{index}.crate", entries)
                dest = self.root / f"bad-{index}"
                dest.mkdir()
                with self.assertRaises(ValueError):
                    unpack(archive, dest, "core-1")
                self.assertEqual(list(dest.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
