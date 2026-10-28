"""Focused derived-profile controls; synthetic receipts are not runtime acceptance."""
import copy,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from chatbot_dynamic_profile import RETAINED_DYNAMIC_PROFILE,DYNAMIC_CONTROLS,validate_mode,retained_dynamic_mode
from chatbot_rewrite_profile import REWRITE_CONTROLS
from qualify_chatbot_runtime import EXPECTED_CONTROLS
from qualify_installed_next import dynamic_case_result,retained_dynamic_case_result
from next_retained_runtime import DRIVERS
from qualify_next_standalone import retained_dynamic_refusals
import test_installed_dynamic_next as original_dynamic
import test_installed_retained_next as original_retained
import next_retained_runtime

ROOT=Path(__file__).resolve().parents[1]
class RetainedDynamicControls(unittest.TestCase):
 def fixture(self):
  return Path(tempfile.mkdtemp(prefix="retained-dynamic-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"]))
 def sample(self):
  # Deliberately composed synthetic acceptance input. Real41-group application
  # evidence must come from the new CI profile, never from these old receipts.
  result,runtime,browser=original_dynamic.InstalledDynamicControls().sample()
  retained,actual,probe,owned=original_retained.InstalledRetainedControls().sample()
  result.update(retained);runtime.update(actual)
  result["sourceTextFiles"]=175
  result["retainedDynamicProfile"]=runtime["retainedDynamicProfile"]=RETAINED_DYNAMIC_PROFILE
  accepted=json.loads((ROOT/"docs/acceptance/project-adoption/g5-installed-retained-next-20261024/accepted-40071420581/source-receipt.json").read_bytes())
  result["rewriteQualification"]=copy.deepcopy(accepted["rewriteQualification"])
  result["rewriteQualification"]["originalSourceContextDigest"]=result["sourceContextDigest"]
  result["dynamicRouteQualification"].update(configurationProfile=RETAINED_DYNAMIC_PROFILE,
    originalOwnerConfigurationPreserved=False,derivedSourceContextDigest=result["rewriteQualification"]["derivedSourceContextDigest"])
  runtime.update(sourceMutationRequested=True,qualificationConfigurationOverlay=True)
  controls=[dict(name=name,passed=True)for name in sorted(EXPECTED_CONTROLS|REWRITE_CONTROLS|DYNAMIC_CONTROLS)]
  browser["controls"]=copy.deepcopy(controls);runtime["browserControls"]=copy.deepcopy(controls)
  probe["retainedDynamicProfileRefusals"]=dict(profile=RETAINED_DYNAMIC_PROFILE,
    **{key:True for key in ["baselineCommandAdmitted","strippedProfileRefused","strippedModeRefused",
      "disabledDynamicRefused","missingDriverRefused","changedDriverRefused","selectionPointerUnchanged"]},
    sealedCommandCodeInputs=["runtime-descriptor.json",*("scripts/"+name for name in DRIVERS)])
  return result,runtime,browser,probe,owned
 def test_complete_synthetic_profile_requires_all41_and_retained_contract(self):
  values=self.sample();result=retained_dynamic_case_result(*values)
  self.assertEqual(len(values[2]["controls"]),41)
  self.assertTrue(result["retainedDynamicProfileAccepted"])
  self.assertTrue(result["retainedRuntimeAccepted"])
  self.assertFalse(result["originalOwnerConfigurationPreserved"])
 def test_derived_mode_is_explicit_and_preserves_original_refusals(self):
  good=dict(runtime=True,rewrites=True,standalone=True,retained=True)
  validate_mode(**good,derived_retained=True)
  for field in good:
   value=dict(good);value[field]=False
   with self.subTest(field=field),self.assertRaisesRegex(AssertionError,"PROFILE"):validate_mode(**value,derived_retained=True)
  with self.assertRaisesRegex(AssertionError,"PROFILE"):validate_mode(**good)
  for invalid in [0,1,None,"true"]:
   with self.subTest(invalid=invalid),self.assertRaisesRegex(AssertionError,"PROFILE"):validate_mode(**good,derived_retained=invalid)
  for verified in [False,1,"true",None]:
   with self.subTest(verified=verified),self.assertRaisesRegex(AssertionError,"PROFILE"):
    validate_mode(**good,derived_retained=True,installed=True,verified_installation=verified)
 def test_sealed_mode_metadata_is_closed_and_legacy_absence_is_explicit(self):
  self.assertFalse(retained_dynamic_mode({}))
  self.assertTrue(retained_dynamic_mode(dict(dynamicRoutes=True,retainedDynamicProfile=RETAINED_DYNAMIC_PROFILE)))
  for value in [{},dict(dynamicRoutes=False),dict(dynamicRoutes=1),dict(dynamicRoutes="true"),
    dict(dynamicRoutes=True),dict(retainedDynamicProfile=RETAINED_DYNAMIC_PROFILE),
    dict(dynamicRoutes=True,retainedDynamicProfile="unknown")]:
   if not value:continue
   with self.subTest(value=value),self.assertRaisesRegex(AssertionError,"PROFILE"):retained_dynamic_mode(value)
 def test_original_config_validator_cannot_promote_derived_case(self):
  values=self.sample()
  with self.assertRaises(AssertionError):dynamic_case_result(*values[:3])
 def test_missing_duplicate_failed_or_downgraded_groups_refuse(self):
  for index,key in [(1,"browserControls"),(2,"controls")]:
   for mutation in ["missing","duplicate","failed","no-dynamic","no-rewrites"]:
    values=self.sample();controls=values[index][key]
    if mutation=="missing":controls.pop()
    if mutation=="duplicate":controls[-1]=copy.deepcopy(controls[0])
    if mutation=="failed":controls[-1]["passed"]=False
    if mutation=="no-dynamic":values[index][key]=[c for c in controls if c["name"]not in DYNAMIC_CONTROLS]
    if mutation=="no-rewrites":values[index][key]=[c for c in controls if c["name"]not in REWRITE_CONTROLS]
    with self.subTest(index=index,mutation=mutation),self.assertRaisesRegex(AssertionError,"EXACT_CONTROLS"):retained_dynamic_case_result(*values)
 def test_exact_original_rule_count_is_required_and_boolean_is_not_a_count(self):
  self.assertEqual(self.sample()[0]["rewriteQualification"]["originalRulesPreserved"],4)
  for count in [True,False,0,3,5,"4",None]:
   values=self.sample();values[0]["rewriteQualification"]["originalRulesPreserved"]=count
   with self.subTest(count=count),self.assertRaisesRegex(AssertionError,"REWRITES"):retained_dynamic_case_result(*values)
 def test_profile_source_and_context_bindings_are_required(self):
  for mutation in ["parent-profile","runtime-profile","context","original-claim","source"]:
   values=self.sample()
   if mutation=="parent-profile":values[0]["retainedDynamicProfile"]="unknown"
   if mutation=="runtime-profile":values[1]["retainedDynamicProfile"]="unknown"
   if mutation=="context":values[0]["dynamicRouteQualification"]["derivedSourceContextDigest"]="changed"
   if mutation=="original-claim":values[0]["dynamicRouteQualification"]["originalOwnerConfigurationPreserved"]=True
   if mutation=="source":values[0]["dynamicSourceBindings"]["sourceMutated"]=True
   with self.subTest(mutation=mutation),self.assertRaises(AssertionError):retained_dynamic_case_result(*values)
 def test_each_real_before_effects_control_and_exact_code_input_set_required(self):
  for key in ["baselineCommandAdmitted","strippedProfileRefused","strippedModeRefused","disabledDynamicRefused",
      "missingDriverRefused","changedDriverRefused","selectionPointerUnchanged"]:
   values=self.sample();values[3]["retainedDynamicProfileRefusals"][key]=False
   with self.subTest(key=key),self.assertRaisesRegex(AssertionError,"CODE_INPUTS"):retained_dynamic_case_result(*values)
  for path in ["runtime-descriptor.json","scripts/chatbot_dynamic_profile.py"]:
   values=self.sample();values[3]["retainedDynamicProfileRefusals"]["sealedCommandCodeInputs"].remove(path)
   with self.subTest(path=path),self.assertRaisesRegex(AssertionError,"CODE_INPUTS"):retained_dynamic_case_result(*values)
 def test_private_data_generation_and_runtime_enforcement_remain_required(self):
  for index,key in [(1,"credentialsCaptured"),(1,"rawRuntimeLogsUploaded"),(1,"externalModelAccepted")]:
   values=self.sample();values[index][key]=True
   with self.subTest(key=key),self.assertRaises(AssertionError):retained_dynamic_case_result(*values)
  values=self.sample();values[1]["retainedRuntime"]["readonlyWriteRefused"]=False
  with self.assertRaisesRegex(AssertionError,"ENFORCEMENT"):retained_dynamic_case_result(*values)
  values=self.sample()
  for index in [1,2]:values[index]["dynamicRouteWitness"]["generationPostAttempts"]=1
  with self.assertRaises(AssertionError):retained_dynamic_case_result(*values)
 def test_mixed_parent_and_child_flags_refuse_before_directory_creation(self):
  for program,extra,expected in [
   ("qualify_installed_next.py",["--retained-dynamic-routes","--dynamic-routes"],"PROFILE_COMBINATION"),
   ("qualify_installed_next.py",["--retained-dynamic-routes","--retained-runtime"],"PROFILE_COMBINATION"),
   ("qualify_chatbot_next.py",["--retained-dynamic-routes","--runtime","--rewrites"],"EXPLICIT_MODE"),
   ("qualify_chatbot_next.py",["--retained-dynamic-routes"],"QUALIFICATION_PROFILE"),
  ]:
   case=self.fixture();args=[sys.executable,"-B",str(ROOT/"scripts"/program),*extra,
      "--work",str(case/"work"),"--evidence",str(case/"evidence")]
   if program=="qualify_chatbot_next.py":args+=["--cli",str(case/"forbidden")]
   value=subprocess.run(args,capture_output=True,text=True)
   self.assertNotEqual(value.returncode,0);self.assertIn(expected,value.stderr)
   self.assertFalse((case/"work").exists());self.assertFalse((case/"evidence").exists())
 def test_invalid_selected_descriptor_refuses_before_runtime_work(self):
  case=self.fixture();config=case/"config.json";work=case/"work"
  config.write_text(json.dumps(dict(profile="patamaps-retained-next-runtime-1",dynamicRoutes=True,
    retainedDynamicProfile="unknown",runtimeWork=str(work))))
  with patch.object(sys,"argv",["next_retained_runtime.py",str(config)]),patch.object(sys,"platform","linux"),patch.dict(os.environ,{"GITHUB_ACTIONS":"true"}):
   with self.assertRaisesRegex(AssertionError,"PROFILE"):next_retained_runtime.main()
  self.assertFalse(work.exists())
 def test_before_effects_harness_mutates_actual_owned_files_and_restores_identities(self):
  case=self.fixture();work=case/"work";work.mkdir();state=case/"state";state.mkdir()
  candidate=case/"candidate";(candidate/"scripts").mkdir(parents=True)
  (state/"selected.json").write_text('{"bound":"pointer"}')
  descriptor=candidate/"runtime-descriptor.json";descriptor.write_text(json.dumps(dict(dynamicRoutes=True,retainedDynamicProfile=RETAINED_DYNAMIC_PROFILE)))
  driver=candidate/"scripts/chatbot_dynamic_profile.py";driver.write_text("bound actual fixture driver")
  files=[descriptor,driver]
  before={str(p):dict(bytes=p.read_bytes(),ino=p.stat().st_ino)for p in files}
  calls=[]
  def independent_stub(label,argv,expected=0):
   command=json.loads(Path(argv[-1]).read_text())
   self.assertEqual(set(command["invocation"]["codeInputs"]),{"runtime-descriptor.json","scripts/chatbot_dynamic_profile.py"})
   unchanged=all(p.exists()and p.read_bytes()==before[str(p)]["bytes"]for p in files)
   if expected==0:
    self.assertTrue(unchanged);calls.append((label,0))
    return json.dumps(dict(status="completed-selected-project-command"))
   self.assertFalse(unchanged,"negative must actually change a captured input")
   self.assertEqual(expected,2);calls.append((label,2));return ""
  result=retained_dynamic_refusals(Path("/controlled/cli"),state,candidate,work,independent_stub,["scripts/chatbot_dynamic_profile.py"])
  self.assertEqual([code for _,code in calls],[0,2,2,2,2,2])
  self.assertTrue(result["strippedModeRefused"])
  for p in files:
   self.assertEqual(p.read_bytes(),before[str(p)]["bytes"]);self.assertEqual(p.stat().st_ino,before[str(p)]["ino"])
  self.assertEqual(len(list(work.glob("*.changed"))),4)

if __name__=="__main__":unittest.main()
