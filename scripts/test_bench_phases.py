"""Retained per-child observations: no file cleanup, no raw stderr publication."""
import hashlib,json,os,signal,subprocess,sys,tempfile,unittest
from pathlib import Path
from bench_phases import measured,rss_observation

class RetainedMeasurementControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix='retained-measure-controls-',dir=os.environ['PATAMAPS_TEST_RETAIN_ROOT']))
 def case(self):
  root=self.root/self._testMethodName;root.mkdir();return root,root/'sample'
 def command(self,source):return [sys.executable,'-B','-c',source]
 def read(self,stem):return json.loads(Path(str(stem)+'.measurement.json').read_bytes())
 def test_success_retains_private_bytes_and_explicit_units(self):
  root,stem=self.case();sample,stdout=measured(self.command('import sys;print("public-result");sys.stderr.write(sys.stdin.read())'),root,{},stdin=b'private-stderr-marker',retained=stem)
  self.assertEqual(stdout,b'public-result\n');self.assertEqual(sample['exitCode'],0)
  self.assertEqual(sample['measurementStatus'],'completed');self.assertNotIn('stderr',sample)
  self.assertNotIn('private-stderr-marker',json.dumps(sample));self.assertGreater(sample['peakRssBytes'],0)
  self.assertEqual(sample,self.read(stem))
  for suffix,expected in [('stdout',stdout),('stderr',b'private-stderr-marker'),('stdin',b'private-stderr-marker')]:
   path=Path(str(stem)+'.'+suffix);self.assertEqual(path.read_bytes(),expected);self.assertEqual(path.stat().st_mode&0o777,0o600)
  self.assertEqual(sample['stderrDigest'],'sha256:'+hashlib.sha256(b'private-stderr-marker').hexdigest())
 def test_nonzero_is_an_observation_not_a_pass(self):
  root,stem=self.case();sample,_=measured(self.command('raise SystemExit(7)'),root,{},retained=stem)
  self.assertEqual(sample['exitCode'],7);self.assertEqual(sample['measurementStatus'],'completed')
 def test_timeout_reaps_only_own_child_and_retains_record(self):
  root,stem=self.case()
  program='import time;time.sleep(30)'
  with self.assertRaises(TimeoutError):measured(self.command(program),root,{},deadline=.3,retained=stem)
  value=self.read(stem);self.assertEqual(value['failureType'],'TimeoutError');self.assertEqual(value['exitCode'],-signal.SIGKILL)
  with self.assertRaises(ProcessLookupError):os.kill(self.read(stem)['pid'],0)
  self.assertTrue(Path(str(stem)+'.stdout').exists())
 def test_monitor_refusal_stops_child_and_preserves_unrelated_session(self):
  root,stem=self.case()
  unrelated=subprocess.Popen(self.command('import time;time.sleep(30)'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  def monitor():
   raise RuntimeError('fixed-ownership-refusal')
  try:
   program='import time;time.sleep(30)'
   with self.assertRaisesRegex(RuntimeError,'ownership'):measured(self.command(program),root,{},retained=stem,monitor=monitor)
   self.assertIsNone(unrelated.poll());self.assertEqual(self.read(stem)['failureType'],'RuntimeError')
   with self.assertRaises(ProcessLookupError):os.kill(self.read(stem)['pid'],0)
  finally:
   unrelated.kill();unrelated.wait(timeout=5)
 def test_log_overflow_refuses_without_hashing_truncated_bytes(self):
  root,stem=self.case()
  with self.assertRaisesRegex(ValueError,'log bound'):measured(self.command('import sys;sys.stdout.write("x"*32768)'),root,{},retained=stem,maximum_log_bytes=16)
  value=self.read(stem);self.assertEqual(value['measurementStatus'],'failed');self.assertGreater(value['stdoutBytes'],16)
  self.assertIsNone(value['stdoutDigest']);self.assertGreater(Path(str(stem)+'.stdout').stat().st_size,16)
 def test_existing_output_refuses_without_overwrite(self):
  root,stem=self.case();original=Path(str(stem)+'.stdout');original.write_bytes(b'preserve-original')
  with self.assertRaises(FileExistsError):measured(self.command('print("forbidden")'),root,{},retained=stem)
  self.assertEqual(original.read_bytes(),b'preserve-original');self.assertFalse(Path(str(stem)+'.measurement.json').exists())
 def test_existing_measurement_refuses_before_command_effects(self):
  root,stem=self.case();record=Path(str(stem)+'.measurement.json');record.write_text('preserve-measurement')
  marker=root/'forbidden.marker'
  program='from pathlib import Path;Path('+repr(str(marker))+').write_text("forbidden")'
  with self.assertRaises(FileExistsError):measured(self.command(program),root,{},retained=stem)
  self.assertEqual(record.read_text(),'preserve-measurement');self.assertFalse(marker.exists())
 def test_launch_failure_does_not_invent_rss(self):
  root,stem=self.case()
  with self.assertRaises(FileNotFoundError):measured(['/unavailable-measurement-command'],root,{},retained=stem)
  value=self.read(stem);self.assertEqual(value['failureType'],'FileNotFoundError');self.assertIsNone(value['peakRssBytes'])
 def test_rss_units_and_invalid_values_are_explicit(self):
  self.assertEqual(rss_observation(1024,'Darwin')['peakRssBytes'],1024)
  self.assertEqual(rss_observation(1024,'Linux')['peakRssBytes'],1024*1024)
  for value,system in [(True,'Linux'),(-1,'Darwin'),(0,'unknown')]:
   with self.subTest(value=value,system=system),self.assertRaises(ValueError):rss_observation(value,system)

if __name__=='__main__':unittest.main()
