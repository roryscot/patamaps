"""Installed-source boundaries and rejection of incomplete owner-build evidence."""
import copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from qualify_miniserve_linux import qualification_source
from qualify_installed_rust_build import case_result,HARNESSES,HTTP

class InstalledRustBuildControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.root=Path(tempfile.mkdtemp(prefix='installed-rust-controls-',dir=os.environ['PATAMAPS_TEST_RETAIN_ROOT'])).resolve()
 def source(self):
  root=self.root/self._testMethodName;root.mkdir();(root/'program.py').write_text('public program\n')
  raw=(root/'program.py').read_bytes();inventory=[dict(path='program.py',digest='sha256:'+hashlib.sha256(raw).hexdigest(),bytes=len(raw))]
  (root/'source-inventory.json').write_text(json.dumps(inventory)+'\n')
  return root,'sha256:'+hashlib.sha256((root/'source-inventory.json').read_bytes()).hexdigest()
 def fixture(self):
  base=Path(__file__).resolve().parent.parent/'docs/acceptance/project-adoption/g3-cargo-registry-context-20261023/registry-accepted-40050181349'
  result=json.loads((base/'receipt.json').read_bytes());execution=json.loads((base/'execution.json').read_bytes())
  identity=dict(sourceInventoryDigest='sha256:'+'0'*64,sourceFiles=1,sourceIsInstalled=True)
  result.update(sourceRevision=None,installedSourceIdentity=identity,installedSourceInventoryUnchanged=True)
  return result,execution,identity,result['relocatedCompiler']['engine'],'sha256:'+result['relocatedCompiler']['sha256']
 def test_bound_installed_source_needs_no_git(self):
  root,digest=self.source()
  with patch('qualify_miniserve_linux.subprocess.check_output',side_effect=AssertionError('Git must not run')):
   revision,identity=qualification_source(root,digest)
  self.assertIsNone(revision);self.assertTrue(identity['sourceIsInstalled'])
 def test_unbound_installed_source_refuses_before_git(self):
  root,digest=self.source()
  with patch('qualify_miniserve_linux.subprocess.check_output') as git:
   with self.assertRaisesRegex(AssertionError,'EXPLICIT_BINDING'):qualification_source(root,None)
   git.assert_not_called()
 def test_changed_installed_bytes_refuse_before_compiler(self):
  root,digest=self.source();(root/'program.py').write_text('changed\n')
  with patch('qualify_miniserve_linux.subprocess.check_output') as compiler:
   with self.assertRaisesRegex(AssertionError,'BYTES_CHANGED'):qualification_source(root,digest)
   compiler.assert_not_called()
 def test_installed_mode_cannot_build_or_reuse_checkout_compiler(self):
  root,digest=self.source()
  for build,reuse in [(True,False),(False,True),(True,True)]:
   with self.subTest(build=build,reuse=reuse),self.assertRaisesRegex(AssertionError,'CANNOT_BUILD_CHECKOUT'):qualification_source(root,digest,build,reuse)
 def test_wrong_inventory_digest_refuses(self):
  root,digest=self.source()
  with self.assertRaisesRegex(AssertionError,'INVENTORY_CHANGED'):qualification_source(root,'sha256:'+'f'*64)
 def test_checkout_mode_preserves_git_identity(self):
  root=self.root/self._testMethodName;root.mkdir()
  with patch('qualify_miniserve_linux.subprocess.check_output',return_value='fixed-checkout\n'):
   self.assertEqual(qualification_source(root,None),('fixed-checkout',None))
 def test_real_historical_contract_fixture_validates_without_claiming_a_new_run(self):
  result,execution,identity,engine,digest=self.fixture()
  checked=case_result(result,execution,identity,engine,digest)
  self.assertEqual(checked['upstreamTestsPassed'],325);self.assertEqual(checked['httpControls'],HTTP);self.assertEqual(sum(HARNESSES),325)
 def test_aggregate_counts_cannot_hide_changed_or_ignored_harnesses(self):
  for mutation in ['redistribute','ignored','lost-harness']:
   result,execution,identity,engine,digest=self.fixture()
   if mutation=='redistribute':
    result['upstreamTestSummaries'][0][0]='42';result['upstreamTestSummaries'][1][0]='16'
   elif mutation=='ignored':result['upstreamTestSummaries'][0][2]='1'
   else:result['upstreamTestSummaries'].pop()
   with self.subTest(mutation=mutation),self.assertRaisesRegex(AssertionError,'UPSTREAM_HARNESSES'):case_result(result,execution,identity,engine,digest)
 def test_pass_label_does_not_replace_actual_controls(self):
  for field,location,value in [('sourceBuild','result',False),('runtimeControls','result',['made-up']*8),('kernelLimitsVerified','execution',False),('memoryAllowance','execution',1024),('allOwnedContainersStopped','execution',False)]:
   result,execution,identity,engine,digest=self.fixture();target=result if location=='result' else execution;target[field]=value
   with self.subTest(field=field),self.assertRaises(AssertionError):case_result(result,execution,identity,engine,digest)
 def test_other_compiler_or_unbound_source_cannot_be_accepted(self):
  result,execution,identity,engine,digest=self.fixture()
  with self.assertRaisesRegex(AssertionError,'COMPILER'):case_result(result,execution,identity,engine,'sha256:'+'f'*64)
  wrong=copy.deepcopy(identity);wrong['sourceInventoryDigest']='sha256:'+'f'*64
  with self.assertRaisesRegex(AssertionError,'SOURCE_BINDING'):case_result(result,execution,wrong,engine,digest)

if __name__=='__main__':unittest.main()
