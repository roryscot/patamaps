"""Wrapper limits refuse before effects; real owned-child timeout retains other sessions."""
import os,shlex,subprocess,sys,tempfile,unittest
from pathlib import Path
from installed_selected import ROOT,arguments,wait_installed_child
from project_watch import stop

class InstalledSelectedLimits(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix='installed-selected-limits-',dir=os.environ['PATAMAPS_TEST_RETAIN_ROOT'])).resolve()
 def case(self):
  p=self.root/self._testMethodName;p.mkdir();return p
 def argv(self,root):
  return ['--compiler',str(root/'compiler'),'--state',str(root/'state'),'--command',str(root/'command.json'),'--output',str(root/'output')]
 def test_existing_callers_keep_180_second_defaults(self):
  root=self.case();a=arguments(self.argv(root))
  self.assertEqual((a.inspection_timeout_seconds,a.execution_timeout_seconds),(180,180))
  self.assertFalse((root/'output').exists())
 def test_owner_override_does_not_change_native_command_file(self):
  root=self.case();command=root/'command.json';raw=b'{"nativeCommandBound":180000}\n';command.write_bytes(raw)
  a=arguments(self.argv(root)+['--inspection-timeout-seconds','900','--execution-timeout-seconds','1200'])
  self.assertEqual((a.inspection_timeout_seconds,a.execution_timeout_seconds),(900,1200))
  self.assertEqual(command.read_bytes(),raw);self.assertFalse((root/'output').exists())
 def test_inclusive_wrapper_bounds(self):
  root=self.case()
  for value in ['1','3600']:
   a=arguments(self.argv(root)+['--inspection-timeout-seconds',value,'--execution-timeout-seconds',value])
   self.assertEqual((a.inspection_timeout_seconds,a.execution_timeout_seconds),(int(value),int(value)))
 def invalid(self,flag):
  root=self.case();marker=root/'compiler.marker';compiler=root/'compiler'
  compiler.write_text('#!/bin/sh\nprintf invoked > '+shlex.quote(str(marker))+'\nexit 91\n');compiler.chmod(0o700)
  for i,value in enumerate(['0','-1','3601','1.5','invalid']):
   out=root/('output-'+str(i));argv=self.argv(root);argv[-1]=str(out)
   result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/installed_selected.py'),*argv,flag,value],capture_output=True,timeout=10)
   self.assertEqual(result.returncode,2,(flag,value));self.assertIn(b'1..3600',result.stderr)
   self.assertFalse(out.exists());self.assertFalse(marker.exists())
 def test_invalid_inspection_refuses_before_output_or_compiler(self):
  self.invalid('--inspection-timeout-seconds')
 def test_invalid_execution_refuses_before_output_or_compiler(self):
  self.invalid('--execution-timeout-seconds')
 def test_wait_success_reaps_child(self):
  root=self.case()
  with (root/'child.stdout').open('xb') as out,(root/'child.stderr').open('xb') as err:
   child=subprocess.Popen([sys.executable,'-B','-c','print("completed")'],stdout=out,stderr=err,start_new_session=True)
   self.assertEqual(wait_installed_child(child,5),0)
  self.assertIsNotNone(child.returncode);self.assertEqual((root/'child.stdout').read_text(),'completed\n')
 def test_timeout_stops_guarded_owned_workload_preserving_unrelated_session(self):
  root=self.case();worker=root/'worker.py';pidfile=root/'worker.pid'
  worker.write_text('from pathlib import Path\nimport os,time\nPath('+repr(str(pidfile))+').write_text(str(os.getpid()))\ntime.sleep(60)\n')
  with (root/'owned.stdout').open('xb') as out,(root/'owned.stderr').open('xb') as err:
   unrelated=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'],stdout=out,stderr=err,start_new_session=True)
   child=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/project_watch.py'),'__guard',sys.executable,'-B',str(worker)],stdout=out,stderr=err,start_new_session=True)
   try:
    with self.assertRaises(subprocess.TimeoutExpired):wait_installed_child(child,1)
    self.assertIsNotNone(child.returncode);self.assertIsNone(unrelated.poll())
    self.assertTrue(pidfile.exists(),'guarded worker must have started')
    pid=int(pidfile.read_text())
    with self.assertRaises(ProcessLookupError):os.kill(pid,0)
   finally:
    stop(child);stop(unrelated)

if __name__=='__main__':unittest.main()
