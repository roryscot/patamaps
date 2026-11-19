"""Installed acceptance must not promote incomplete runtime or recovery receipts."""
import copy,unittest
from qualify_installed_next import retained_case_result

class InstalledRetainedControls(unittest.TestCase):
 def sample(self):
  result=dict(generatedOutputObservation=dict(changedFiles=0,before=dict(inventoryDigest='bound'),after=dict(inventoryDigest='bound')),
      retainedPortHandoffVerified=True,retainedSelectedExecution=dict(status='completed-selected-project-command',postExecutionSelectionVerified=True,selectionPointerUnchanged=True))
  probe={key:True for key in ['closedTreeSelected','realMemberAndLinkRefusalsBeforeEffects','standaloneTreeUnchanged','producerSourceAndToolsUnavailable','retainedRuntimeAccepted']}
  probe['runtimeMutationObservation']=dict(changedEntries=0)
  actual={key:True for key in ['imageBytesModesAndLinkTargetsVerified','readonlyWriteRefused','cacheWritePassed','cacheQuotaFailurePassed','producerUnavailableThroughoutBrowser','selectedGenerationUnchanged','renamedProducerPathsRestored','allOwnedContainersStopped']}
  actual['status']='passed-private-retained-next-runtime'
  return result,dict(retainedRuntime=actual),probe,dict(containers=[dict(role='probe',confirmedStopped=True),dict(role='app',confirmedStopped=True)])
 def test_complete_case_admits(self):
  observed=retained_case_result(*self.sample())
  self.assertTrue(observed['retainedRuntimeAccepted']);self.assertTrue(observed['producerRestored'])
 def test_native_postcheck_or_port_handoff_required(self):
  for key in ['postExecutionSelectionVerified','selectionPointerUnchanged']:
   values=self.sample();values[0]['retainedSelectedExecution'][key]=False
   with self.subTest(key=key),self.assertRaisesRegex(AssertionError,'SELECTION'):retained_case_result(*values)
  values=self.sample();values[0]['retainedPortHandoffVerified']=False
  with self.assertRaisesRegex(AssertionError,'PORT'):retained_case_result(*values)
 def test_mutable_output_cannot_be_promoted(self):
  for key in ['changedFiles','after']:
   values=self.sample();values[0]['generatedOutputObservation'][key]=1 if key=='changedFiles' else dict(inventoryDigest='changed')
   with self.subTest(key=key),self.assertRaisesRegex(AssertionError,'PRODUCER_CHANGED'):retained_case_result(*values)
  values=self.sample();values[2]['runtimeMutationObservation']['changedEntries']=1
  with self.assertRaisesRegex(AssertionError,'GENERATION_CHANGED'):retained_case_result(*values)
 def test_source_unavailability_and_generation_guards_required(self):
  for key in ['closedTreeSelected','realMemberAndLinkRefusalsBeforeEffects','standaloneTreeUnchanged','producerSourceAndToolsUnavailable','retainedRuntimeAccepted']:
   values=self.sample();values[2][key]=False
   with self.subTest(key=key),self.assertRaisesRegex(AssertionError,'OUTPUT_OR_SOURCE'):retained_case_result(*values)
 def test_image_enforcement_and_restoration_must_all_pass(self):
  initial=self.sample()
  for key in initial[1]['retainedRuntime']:
   values=copy.deepcopy(initial);values[1]['retainedRuntime'][key]='failed' if key=='status' else False
   with self.subTest(key=key),self.assertRaises(AssertionError):retained_case_result(*values)
 def test_missing_duplicate_or_surviving_container_refuses(self):
  initial=self.sample()[3]['containers']
  for containers in [[],initial[:1],[initial[0],initial[0]],[initial[0],dict(role='app',confirmedStopped=False)]]:
   values=self.sample();values[3]['containers']=containers
   with self.subTest(containers=containers),self.assertRaisesRegex(AssertionError,'OWNED_CONTAINERS'):retained_case_result(*values)

if __name__=='__main__':unittest.main()
