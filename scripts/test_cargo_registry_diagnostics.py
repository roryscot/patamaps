"""Safe failure summaries must preserve facts without publishing raw payloads."""
import json,unittest
from cargo_registry_container import failure_summary
class DiagnosticControls(unittest.TestCase):
 def test_private_payload_not_published(self):
  raw="test tls::listener ... FAILED\nthread 'listener' panicked at tests/tls.rs:18:2:\nassertion failed: PRIVATE_SENTINEL_CONTENT\ntest result: FAILED. 3 passed; 1 failed; 0 ignored"
  value=failure_summary(raw,"")
  self.assertEqual(value['failedTests'],['tls::listener'])
  self.assertEqual(value['panicLocations'],['tests/tls.rs:18:2'])
  self.assertEqual(value['testSummaries'],[('FAILED','3','1','0')])
  self.assertNotIn('PRIVATE_SENTINEL_CONTENT',json.dumps(value))
 def test_capacity_and_compiler_codes(self):
  value=failure_summary('',"error[E0382]: PRIVATE_SOURCE_TEXT\nerror: could not compile `miniserve`\nNo space left on device\nsignal: 9, SIGKILL\nunable to find library -lssl")
  self.assertEqual(value['categories'],['disk-full'])
  self.assertEqual(value['rustcErrorCodes'],['E0382'])
  self.assertEqual(value['compileFailures'],['miniserve'])
  self.assertEqual(value['signals'],[('9','KILL')])
  self.assertEqual(value['missingLibraries'],['ssl'])
  self.assertNotIn('PRIVATE_SOURCE_TEXT',json.dumps(value))
 def test_unknown_payload_stays_private(self):
  self.assertTrue(all(not v for v in failure_summary('PRIVATE_UNKNOWN_PAYLOAD','').values()))
 def test_success_summary(self):
  value=failure_summary('test result: ok. 325 passed; 0 failed; 0 ignored','')
  self.assertEqual(value['testSummaries'],[('ok','325','0','0')])
  self.assertEqual(value['failedTests'],[])
if __name__=='__main__':unittest.main()
