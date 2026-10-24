"""Retained fixtures test refusals; no application builds or timed acceptance."""
import copy,json,os,tempfile,unittest
from pathlib import Path
import bench_axum_build as build
import bench_axum_retained as driver

class AxumMeasurementControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix='axum-measure-controls-',dir=os.environ['PATAMAPS_TEST_RETAIN_ROOT'])).resolve()
 def case(self):
  root=self.root/self._testMethodName;root.mkdir();return root
 def proof(self):
  return dict(id='fixture-owned',phase='benchmark',ownerAlive=True,ownerIdentityVerified=True,ownerIsAncestor=True,heartbeatStale=False,cancellationRequested=False,state='running',project=str(driver.ROOT.resolve()),enforcement='native-exclusive',exclusive=True,otherActiveReservations=0,runningContainers=0,interactiveReserve=dict(cpu=2,memoryBytes=4*1024**3,diskBytes=5*1024**3),machine=dict(cpu=8,memoryBytes=16*1024**3,freeMemoryBytes=0,freeDiskBytes=20*1024**3),memoryPressureLevel=1,memoryPressureCapacityEstimateBytes=8*1024**3)
 def fixture(self,root):
  state=root/'state';attempt=state/'attempts'/'fixture';candidate=attempt/'candidate';bundle=candidate/'bundle';bundle.mkdir(parents=True)
  for name in [*build.LIBRARIES,'consumer']:(bundle/name).write_bytes(b'fixture-artifact:'+name.encode())
  artifacts=build.artifact_rows(bundle)
  build.write(bundle/'lineage.json',dict(profile='patamaps-axum-measured-bundle-1',phase='cold',sourceLibDigest='fixture',artifacts=artifacts))
  selected=dict(attempt='attempts/fixture',inputKey='fixture-input-key');build.write(state/'selected.json',selected)
  actual=dict(status='verified-measured-axum-build',upstreamTestsPassed=459,consumerValue='cold',bundleUnchanged=True,testSummaries=[dict(passed=n,failed=0,ignored=0) for n in [423,16,15,5]])
  verification=dict(status='completed-project-command',programSucceeded=True,selectedInputsUnchanged=True,executableUnchanged=True,stdout=dict(text=json.dumps(actual)));build.write(attempt/'verify-001.json',verification)
  (candidate/'generated').mkdir();build.write(candidate/'generated/cargo-packages.json',dict(entries=[dict(subject=dict(attributes=dict(name=n))) for n in ['axum','axum-core','axum-extra','axum-macros']]))
  return state,attempt,bundle,verification
 def test_counts_require_all_four_unignored_harnesses(self):
  text='\n'.join('test result: ok. %d passed; 0 failed; 0 ignored'%n for n in [423,16,15,5])
  self.assertEqual(sum(r['passed'] for r in build.test_summaries(text)),459)
  for bad in [text.replace('423','422'),text.replace('0 ignored','1 ignored'),text+'\ntest result: FAILED',text+'\ntest result: ok. 0 passed; 0 failed; 0 ignored']:
   with self.subTest(bad=bad),self.assertRaises(AssertionError):build.test_summaries(bad)
 def test_ownership_requires_live_exclusive_uncancelled_owner(self):
  self.assertEqual(driver.validate_ownership(self.proof(),'benchmark')['id'],'fixture-owned')
  for key,value in [('phase','functional'),('ownerAlive',False),('ownerIdentityVerified',False),('ownerIsAncestor',False),('heartbeatStale',True),('cancellationRequested',True),('state','needs-review'),('project','/another-project'),('enforcement','unknown'),('exclusive',False),('otherActiveReservations',1),('runningContainers',1),('memoryPressureLevel',2),('memoryPressureCapacityEstimateBytes',0)]:
   proof=self.proof();proof[key]=value
   with self.subTest(key=key),self.assertRaises(AssertionError):driver.validate_ownership(proof,'benchmark')
 def test_interactive_cpu_disk_headroom_is_required(self):
  for key,value in [('cpu',3),('freeDiskBytes',0)]:
   proof=self.proof();proof['machine'][key]=value
   with self.subTest(key=key),self.assertRaises(AssertionError):driver.validate_ownership(proof,'benchmark')
 def test_functional_preparation_cannot_promote_to_benchmark(self):
  proof=self.proof();proof.update(phase='functional',runningContainers=1)
  driver.validate_ownership(proof,'functional')
  with self.assertRaises(AssertionError):driver.validate_ownership(proof,'benchmark')
 def test_footprint_counts_links_without_following_them(self):
  root=self.case();data=root/'data';data.mkdir();(data/'one').write_bytes(b'x'*4096);os.link(data/'one',data/'alias')
  outside=root/'outside';outside.mkdir();(outside/'large').write_bytes(b'x'*8192);(data/'pointer').symlink_to(outside,target_is_directory=True)
  observed=driver.footprint(data)
  self.assertEqual(observed['files'],2);self.assertEqual(observed['symlinks'],1);self.assertEqual(observed['logicalFileBytes'],8192);self.assertEqual(observed['hardlinkAliases'],1)
  self.assertEqual(observed['allocatedBytes'],sum(p.lstat().st_blocks*512 for p in [data,data/'one',data/'pointer']))
 def test_footprint_refuses_special_files(self):
  root=self.case();os.mkfifo(root/'fifo')
  with self.assertRaisesRegex(AssertionError,'FOOTPRINT_SPECIAL'):driver.footprint(root)
 def test_capture_configs_rejects_content_digest_and_length_changes(self):
  root=self.case();capture=dict(inputs=[])
  for name in ['workspace.json','policy.json','package-projection.json']:
   (root/name).write_bytes(b'{}\n');capture['inputs'].append(dict(content='{}\n',receipt=dict(path=name,digest=driver.sha(root/name),byteLength=3)))
  self.assertEqual(len(driver.capture_configs(capture,root)),3)
  for field,value in [('content','changed'),('digest','sha256:changed'),('byteLength',99)]:
   wrong=copy.deepcopy(capture)
   if field=='content':wrong['inputs'][0][field]=value
   else:wrong['inputs'][0]['receipt'][field]=value
   with self.subTest(field=field),self.assertRaises(AssertionError):driver.capture_configs(wrong,root)
 def test_selection_checks_receipt_flags_and_test_counts(self):
  root=self.case();state,attempt,bundle,verification=self.fixture(root)
  pointer,summary=driver.inspect_selection(state,'cold');self.assertEqual(summary['upstreamTestsPassed'],459)
  driver.inspect_selection(state,'cold',pointer,True)
  for key in ['programSucceeded','selectedInputsUnchanged','executableUnchanged']:
   wrong=copy.deepcopy(verification);wrong[key]=False;(attempt/'verify-001.json').write_text(json.dumps(wrong))
   with self.subTest(key=key),self.assertRaisesRegex(AssertionError,'VERIFICATION_COMMAND'):driver.inspect_selection(state,'cold')
  wrong=copy.deepcopy(verification);actual=json.loads(wrong['stdout']['text']);actual['testSummaries'][0]['ignored']=1;wrong['stdout']['text']=json.dumps(actual);(attempt/'verify-001.json').write_text(json.dumps(wrong))
  with self.assertRaisesRegex(AssertionError,'TEST_COUNTS'):driver.inspect_selection(state,'cold')
 def test_selection_refuses_changed_artifacts_modes_and_phase(self):
  root=self.case();state,attempt,bundle,verification=self.fixture(root)
  with self.assertRaisesRegex(AssertionError,'SELECTED_EDIT'):driver.inspect_selection(state,'edit-1')
  artifact=bundle/'consumer';original=artifact.read_bytes();mode=artifact.stat().st_mode&0o777
  artifact.chmod(mode^0o100)
  with self.assertRaisesRegex(AssertionError,'SELECTED_ARTIFACT'):driver.inspect_selection(state,'cold')
  artifact.chmod(mode);artifact.write_bytes(original+b'tampered')
  with self.assertRaisesRegex(AssertionError,'SELECTED_ARTIFACT'):driver.inspect_selection(state,'cold')
 def test_selection_refuses_path_escape_warm_pointer_change_and_false_edit(self):
  root=self.case();state,attempt,bundle,verification=self.fixture(root);pointer=(state/'selected.json').read_bytes()
  with self.assertRaisesRegex(AssertionError,'NOOP_POINTER'):driver.inspect_selection(state,'cold',pointer+b' ',True)
  with self.assertRaisesRegex(AssertionError,'EDIT_SELECTION'):driver.inspect_selection(state,'cold',pointer,False)
  for escaped in ['../outside','/outside','attempts/../outside']:
   (state/'selected.json').write_text(json.dumps(dict(attempt=escaped,inputKey='x')))
   with self.subTest(path=escaped),self.assertRaisesRegex(AssertionError,'ATTEMPT_PATH'):driver.inspect_selection(state,'cold')
 def test_noop_and_changed_build_semantics_are_distinct(self):
  driver.require_result(dict(status='unchanged-project-build',verification='not-repeated',cacheHits=0),True)
  driver.require_result(dict(status='selected-project-build',verification='commands-executed'),False)
  for result in [dict(status='unchanged-project-build',verification='not-repeated',cacheHits=1),dict(status='unchanged-project-build',verification='commands-executed',cacheHits=0),dict(status='selected-project-build',verification='commands-executed',cacheHits=0)]:
   with self.subTest(result=result),self.assertRaises(AssertionError):driver.require_result(result,True)
 def test_plan_pins_environment_outputs_and_control_inputs(self):
  root=self.case();cargo=root/'cargo';rustc=root/'rustc';cargo.write_bytes(b'fixture-cargo');rustc.write_bytes(b'fixture-rustc')
  prior=dict(workspace=dict(sources=[dict(config=dict(features=['axum/ws'],defaultFeatures=True,view='resolved',platform='x86_64-apple-darwin',cargoHome='/fixture-registry'),invocation=dict(executable='/old'))]),project=dict(nonsecretConfiguration={},components=[]))
  plan=driver.make_plan(prior,root,root/'cli',cargo,rustc,['axum/src/lib.rs'])
  self.assertEqual(plan['maximumRetainedAttempts'],8);self.assertEqual(plan['project']['nonsecretConfiguration']['jobs'],'2');self.assertEqual(plan['project']['nonsecretConfiguration']['offline'],'true')
  self.assertEqual(plan['project']['nonsecretConfiguration']['targetDir'],str(root/'cargo-target'))
  self.assertEqual(len(plan['project']['inputs']),5);self.assertEqual([o['path'] for o in plan['outputs']],['bundle','generated/cargo-packages.json'])
  self.assertEqual(plan['buildSteps'][0]['invocation']['codeInputs'],plan['verificationSteps'][0]['invocation']['codeInputs'])
  self.assertNotIn('--verify',plan['buildSteps'][0]['invocation']['arguments']);self.assertIn('--verify',plan['verificationSteps'][0]['invocation']['arguments'])
  self.assertEqual(prior['workspace']['sources'][0]['invocation']['executable'],'/old')
 def test_schedule_is_one_cold_three_unchanged_and_three_edits(self):
  schedule=driver.phase_schedule();self.assertEqual(len(schedule),7);self.assertEqual(schedule[0],('cold','cold',900));self.assertEqual([p[0] for p in schedule[1:4]],['warm-1','warm-2','warm-3']);self.assertEqual([p[1] for p in schedule[4:]],['edit-1','edit-2','edit-3'])
  with self.assertRaises(AssertionError):build.probe_suffix('unfrozen-phase')

if __name__=='__main__':unittest.main()
