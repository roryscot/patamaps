"""Private standalone inventory/copy controls; retain all generated cases."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from qualify_next_standalone import inventory, summary, encoded, digest, copy_bound, changed_summary

class StandalonePrivateControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="standalone-private-", dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"]))
    def case(self):
        work = self.root/self._testMethodName
        work.mkdir()
        source = work/"source";source.mkdir()
        return work, source
    def descriptor(self, work, source):
        rows = inventory(source);path = work/"private.json";path.write_bytes(encoded(rows))
        return dict(profile="patamaps-standalone-owner-probe-1", privateSourceRoot=str(source),
                    privateInventoryPath=str(path), inventoryDigest=digest(encoded(rows)), producer={})
    def test_private_bytes_absent_from_metadata(self):
        work,source = self.case()
        value = b"PRIVATE_ACTION_KEY_SENTINEL"
        (source/"server-reference-manifest.json").write_bytes(value)
        rows = inventory(source);public = summary(rows)
        self.assertNotIn(value.decode(), json.dumps(rows))
        self.assertNotIn(value.decode(), json.dumps(public))
        self.assertEqual(public["files"],1);self.assertEqual(public["bytes"],len(value))
    def test_symlink_target_never_read(self):
        work,source = self.case()
        outside=work/"outside";outside.mkdir();(outside/"private").write_text("preserved")
        (source/"link").symlink_to(outside,target_is_directory=True)
        with patch("qualify_next_standalone.hashlib.file_digest",side_effect=AssertionError("FOLLOWED")):
            rows=inventory(source)
        self.assertEqual(set(rows),{".","link"})
        self.assertFalse(rows["link"]["targetFollowed"])
    def test_root_symlink_refuses(self):
        work,source=self.case();link=work/"link";link.symlink_to(source,target_is_directory=True)
        with self.assertRaisesRegex(AssertionError,"STANDALONE_ROOT"):inventory(link)
    def test_special_file_refuses_before_read(self):
        work,source=self.case();os.mkfifo(source/"fifo")
        with self.assertRaisesRegex(AssertionError,"SPECIAL_FILE"):inventory(source)
    def test_exact_binary_modes_and_relative_link_copy(self):
        work,source=self.case();(source/"nested").mkdir()
        (source/"nested/program").write_bytes(b"\x00\xff\x80data");(source/"nested/program").chmod(0o751)
        (source/"alias").symlink_to("nested/program")
        descriptor=self.descriptor(work,source)
        target=work/"bundle";copy_bound(descriptor,target)
        self.assertEqual(inventory(source),inventory(target))
        self.assertEqual(os.readlink(target/"alias"),"nested/program")
        self.assertEqual((target/"nested/program").stat().st_mode&0o777,0o751)
    def test_changed_source_refuses_before_copy(self):
        work,source=self.case();(source/"app").write_bytes(b"original")
        descriptor=self.descriptor(work,source);(source/"app").write_bytes(b"changed")
        with self.assertRaisesRegex(AssertionError,"SOURCE_CHANGED"):copy_bound(descriptor,work/"bundle")
        self.assertFalse((work/"bundle").exists())
    def test_changed_mode_refuses_before_copy(self):
        work,source=self.case();(source/"app").write_bytes(b"original")
        descriptor=self.descriptor(work,source);(source/"app").chmod(0o700)
        with self.assertRaisesRegex(AssertionError,"SOURCE_CHANGED"):copy_bound(descriptor,work/"bundle")
        self.assertFalse((work/"bundle").exists())
    def test_changed_inventory_refuses_before_copy(self):
        work,source=self.case();(source/"app").write_text("original")
        descriptor=self.descriptor(work,source);Path(descriptor["privateInventoryPath"]).write_bytes(b"{}")
        with self.assertRaisesRegex(AssertionError,"INVENTORY_CHANGED"):copy_bound(descriptor,work/"bundle")
        self.assertFalse((work/"bundle").exists())
    def test_changed_summary_counts_only_no_private_paths_or_bytes(self):
        work,source=self.case()
        (source/"server-reference-manifest.json").write_text("PRIVATE_INITIAL_ACTION_KEY")
        before=inventory(source)
        (source/".next/cache").mkdir(parents=True)
        (source/".next/cache/private-session-name").write_text("PRIVATE_NEW_BYTES")
        (source/"server-reference-manifest.json").write_text("PRIVATE_CHANGED_ACTION_KEY")
        after=inventory(source);observation=changed_summary(before,after)
        self.assertEqual(observation["changedEntries"],4)
        self.assertEqual(observation["categories"],dict(cache=2,diagnostics=0,**{"server-rendered":0,"other":2}))
        self.assertEqual(observation["changes"],dict(added=3,removed=0,changed=1))
        public=json.dumps(observation)
        for private in ["private-session-name","PRIVATE_NEW_BYTES","PRIVATE_CHANGED_ACTION_KEY","server-reference-manifest.json"]:
            self.assertNotIn(private,public)
        self.assertFalse(observation["detailedInventoryPublished"])
    def test_unknown_descriptor_refuses_before_copy(self):
        work,source=self.case();descriptor=self.descriptor(work,source);descriptor["unknown"]=True
        with self.assertRaisesRegex(AssertionError,"DESCRIPTOR"):copy_bound(descriptor,work/"bundle")
        self.assertFalse((work/"bundle").exists())

if __name__=="__main__":unittest.main()
