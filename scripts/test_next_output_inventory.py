"""Private output observations expose digests/counts, never generated key bytes."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from qualify_chatbot_next import private_output_inventory

class PrivateOutputControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix="next-private-output-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"]))
 def case(self):
  work=self.root/self._testMethodName;work.mkdir();staged=work/"owner";staged.mkdir()
  return work,staged
 def test_only_private_inventory_and_safe_summary(self):
  work,staged=self.case();base=staged/".next/server";base.mkdir(parents=True)
  secret=b"CONTROLLED_PRIVATE_ACTION_KEY_SENTINEL";(base/"server-reference-manifest.json").write_bytes(secret)
  records,summary=private_output_inventory(staged,work,"before")
  self.assertNotIn(secret.decode(),json.dumps(summary));self.assertNotIn(secret.decode(),json.dumps(records))
  self.assertEqual(summary["files"],1);self.assertEqual(summary["bytes"],len(secret))
  self.assertTrue((work/"private-next-output-before.json").is_file())
  (base/"server-reference-manifest.json").write_bytes(secret+b"x")
  _,changed=private_output_inventory(staged,work,"after")
  self.assertNotEqual(summary["inventoryDigest"],changed["inventoryDigest"])
 def test_member_symlink_records_metadata_without_following(self):
  work,staged=self.case();base=staged/".next";base.mkdir();outside=work/"private-directory";outside.mkdir();(outside/"private").write_text("preserved")
  (base/"link").symlink_to(outside,target_is_directory=True)
  with patch("qualify_chatbot_next.sha",side_effect=AssertionError("HASH_CALLED")):
   records,summary=private_output_inventory(staged,work,"observed")
  self.assertEqual(summary["symlinks"],1)
  self.assertFalse(summary["symlinkTargetsFollowed"])
  self.assertFalse(records["link"]["targetFollowed"])
  self.assertEqual(set(records),{"link"})
 def test_root_symlink_refuses_before_hash(self):
  work,staged=self.case();outside=work/"private-directory";outside.mkdir();(outside/"private").write_text("preserved")
  (staged/".next").symlink_to(outside,target_is_directory=True)
  with patch("qualify_chatbot_next.sha",side_effect=AssertionError("HASH_CALLED")):
   with self.assertRaisesRegex(AssertionError,"symlink"):private_output_inventory(staged,work,"refused")

if __name__=="__main__":unittest.main()
