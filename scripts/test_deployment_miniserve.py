"""Frozen config boundary controls; all generated case files remain."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
class ConfigurationControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  parent=Path(os.environ["PATAMAPS_TEST_RETAIN_ROOT"]);assert parent.is_dir()
  cls.work=Path(tempfile.mkdtemp(prefix="miniserve-config-",dir=parent))
 def exercise(self,raw,good=False):
  case=self.work/self._testMethodName;case.mkdir();(case/"public").mkdir();(case/"public/status.txt").write_text("checked\n");(case/"runtime").write_bytes(b"controlled bytes");(case/"probe.sh").write_text("#!/bin/bash\ntrue\n")
  (case/"service.json").write_text(raw)
  command=[sys.executable,str(ROOT/"scripts/deployment/miniserve/prepare_bundle.py")]
  r=subprocess.run(command,cwd=case,capture_output=True,text=True,timeout=10)
  (case/"stdout").write_text(r.stdout);(case/"stderr").write_text(r.stderr)
  if good:
   self.assertEqual(r.returncode,0,r.stderr);r=subprocess.run([*command,"--verify"],cwd=case,capture_output=True,text=True,timeout=10);self.assertEqual(r.returncode,0,r.stderr)
   self.assertIn("--port 9100",(case/"bundle/launch.sh").read_text())
  else:self.assertNotEqual(r.returncode,0);self.assertFalse((case/"bundle").exists())
 def config(self,**changes):
  return dict(schemaVersion="miniserve-qualified-1",nonsecret=True,target="linux/amd64",bind="127.0.0.1",port=9100,routePrefix="/qualified",documentRoot="public",**changes)
 def test_valid(self):self.exercise(json.dumps(self.config()),True)
 def test_duplicate(self):self.exercise(json.dumps(self.config())[:-1]+',"port":9101}')
 def test_unknown_setting(self):self.exercise(json.dumps({**self.config(),"authFile":"not-read"}))
 def test_boolean_port(self):self.exercise(json.dumps({**self.config(),"port":True}))
 def test_overflow_port(self):self.exercise(json.dumps({**self.config(),"port":65536}))
 def test_privileged_port(self):self.exercise(json.dumps({**self.config(),"port":80}))
 def test_public_bind(self):self.exercise(json.dumps({**self.config(),"bind":"0.0.0.0"}))
 def test_traversal(self):self.exercise(json.dumps({**self.config(),"documentRoot":"../outside"}))
 def test_unknown_target(self):self.exercise(json.dumps({**self.config(),"target":"windows/amd64"}))
 def test_not_nonsecret(self):self.exercise(json.dumps({**self.config(),"nonsecret":False}))

class SourceSelectionControls(unittest.TestCase):
 def selected(self,extra=None,changed=None):
  from qualify_miniserve_linux import select_captured_source,PUBLIC_TEST_FIXTURES
  names=["Cargo.toml","Cargo.lock","src/main.rs",*PUBLIC_TEST_FIXTURES]
  return select_captured_source(names+(extra or []),{**PUBLIC_TEST_FIXTURES,**(changed or {})})
 def test_public_fixture_bytes_stay_out_of_capture(self):
  self.assertEqual(self.selected(),["Cargo.toml","Cargo.lock","src/main.rs"])
 def test_new_key_refuses(self):
  with self.assertRaisesRegex(ValueError,"FORBIDDEN_SOURCE_INPUT"):self.selected(["settings/private.pem"])
 def test_dotenv_refuses(self):
  with self.assertRaisesRegex(ValueError,"FORBIDDEN_SOURCE_INPUT"):self.selected([".env.production"])
 def test_changed_fixture_refuses(self):
  with self.assertRaisesRegex(ValueError,"REVIEW_PUBLIC_TEST_FIXTURE_BLOB"):self.selected(changed={"tests/data/key_ec.pem":"0"*40})
 def test_new_fixture_refuses(self):
  with self.assertRaisesRegex(ValueError,"REVIEW_PUBLIC_TEST_FIXTURE_SET"):self.selected(["tests/data/extra.pem"])

if __name__=="__main__":unittest.main()
