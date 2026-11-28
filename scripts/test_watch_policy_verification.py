"""Controlled policy/protocol regressions; these are not host reservation acceptance."""
import argparse,contextlib,hashlib,io,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
import project_watch as watch

KEY="sha256:"+"a"*64
OTHER="sha256:"+"b"*64

class WatchPolicyVerification(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix="watch-policy-verification-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"])).resolve()
 def case(self,mode="normal"):
  root=self.root/self._testMethodName;root.mkdir()
  state=root/"state";state.mkdir();(state/"selected.json").write_text(json.dumps({"inputKey":KEY}))
  key=root/"current-key";key.write_text(KEY);audit=root/"native-audit.jsonl"
  compiler=root/"compiler"
  compiler.write_text("#!"+sys.executable+"\n"+(
   "import json,os,sys\nfrom pathlib import Path\n"
   "root=Path(__file__).parent\ncmd=sys.argv[1]\n"
   "with (root/'native-audit.jsonl').open('a') as f:f.write(json.dumps(dict(command=cmd,reserved=os.environ.get('WATCH_TEST_RESERVED')=='1'))+'\\n')\n"
   "if cmd=='project-build-verify':\n"
   " assert os.environ.get('WATCH_TEST_RESERVED')=='1','full verification escaped policy'\n"
   " if (root/'native-failure').exists():raise SystemExit(7)\n"
   " print(json.dumps(dict(status='verified-selected-build-bindings',inputKey=json.loads((root/'state/selected.json').read_text())['inputKey'])))\n"
   "elif cmd=='project-build':\n"
   " assert os.environ.get('WATCH_TEST_RESERVED')=='1','build escaped policy'\n"
   " print(json.dumps(dict(status='unchanged-project-build',inputKey='sha256:'+'a'*64,verification='not-repeated',cacheHits=0)))\n"
   "elif cmd=='project-build-input-key':print(json.dumps(dict(status='observed-project-build-inputs',commandsExecuted=False,inputKey=(root/'current-key').read_text())))\n"
   "else:raise SystemExit(9)\n"))
  compiler.chmod(0o700)
  runner=root/"runner.py"
  runner.write_text(
   "import hashlib,json,os,subprocess,sys\nfrom pathlib import Path\n"
   "root=Path(__file__).parent;mode="+repr(mode)+"\n"
   "with (root/'runner-audit.txt').open('a') as f:f.write('call\\n')\n"
   "if mode=='skip':raise SystemExit(0)\n"
   "if mode in ['wrong-nonce','duplicate']:\n"
   " p=json.loads(sys.argv[-1]);r=dict(status='verified-project-watch-selection',nonce=p['nonce'] if mode=='duplicate' else '0'*32,inputKey="+repr(KEY)+",selectedPointerDigest='sha256:'+hashlib.sha256((root/'state/selected.json').read_bytes()).hexdigest())\n"
   " print(json.dumps(r));\n"
   " if mode=='duplicate':print(json.dumps(r))\n"
   " raise SystemExit(0)\n"
   "if mode=='oversize':\n"
   " sys.stdout.write('x'*1048577);sys.stdout.flush();raise SystemExit(0)\n"
   "code=subprocess.call(sys.argv[1:],env=dict(os.environ,WATCH_TEST_RESERVED='1'))\n"
   "if code==0 and mode=='changed-source':(root/'current-key').write_text("+repr(OTHER)+")\n"
   "if code==0 and mode=='changed-pointer':(root/'state/selected.json').write_text(json.dumps(dict(inputKey="+repr(OTHER)+")))\n"
   "raise SystemExit(code)\n")
  return argparse.Namespace(plan=root/"plan.json",source=root,state=state,compiler=compiler,
   context=None,preparation=None,inspection_timeout_ms=5000,runner=[sys.executable,"-B",str(runner)]),root
 def verify(self,args,parent=None):
  with contextlib.redirect_stdout(io.StringIO()):
   return watch.policy_verified_selection(args,os.getppid() if parent is None else parent,hashlib.sha256(Path(watch.__file__).read_bytes()).digest())
 def test_full_scan_is_reserved_and_parent_only_observes_key(self):
  args,root=self.case();result=self.verify(args)
  self.assertEqual(result["inputKey"],KEY)
  rows=[json.loads(x) for x in (root/"native-audit.jsonl").read_text().splitlines()]
  self.assertEqual(rows,[{"command":"project-build-verify","reserved":True},
   {"command":"project-build-input-key","reserved":True},{"command":"project-build-input-key","reserved":False}])
 def test_skipped_policy_refuses_even_with_current_selection(self):
  args,root=self.case("skip")
  with self.assertRaisesRegex(ValueError,"WATCH_VERIFICATION_RECORD_REFUSED"):self.verify(args)
  self.assertFalse((root/"native-audit.jsonl").exists())
 def test_wrong_nonce_refuses(self):
  args,_=self.case("wrong-nonce")
  with self.assertRaisesRegex(ValueError,"WATCH_VERIFICATION_RECORD_REFUSED"):self.verify(args)
 def test_duplicate_record_refuses(self):
  args,_=self.case("duplicate")
  with self.assertRaisesRegex(ValueError,"WATCH_VERIFICATION_RECORD_REFUSED"):self.verify(args)
 def test_failed_native_verification_cannot_complete_update(self):
  args,root=self.case();(root/"native-failure").touch()
  with self.assertRaisesRegex(ValueError,"WATCH_POLICY_VERIFICATION_REFUSED"):self.verify(args)
  rows=[json.loads(x) for x in (root/"native-audit.jsonl").read_text().splitlines()]
  self.assertEqual(len(rows),1);self.assertTrue(rows[0]["reserved"])
 def test_source_change_during_policy_handoff_refuses(self):
  args,_=self.case("changed-source")
  with self.assertRaisesRegex(ValueError,"WATCH_SELECTION_DOES_NOT_MATCH_CURRENT_INPUTS"):self.verify(args)
 def test_pointer_change_during_policy_handoff_refuses(self):
  args,_=self.case("changed-pointer")
  with self.assertRaisesRegex(ValueError,"WATCH_VERIFICATION_RECORD_REFUSED"):self.verify(args)
 def test_output_bound_preserves_unrelated_session(self):
  args,_=self.case("oversize")
  unrelated=subprocess.Popen([sys.executable,"-B","-c","import time;time.sleep(90)"],start_new_session=True)
  try:
   with self.assertRaisesRegex(ValueError,"WATCH_VERIFICATION_OUTPUT_LIMIT"):self.verify(args)
   self.assertIsNone(unrelated.poll())
  finally:watch.stop(unrelated)
 def test_parent_relationship_change_cancels_reserved_verification(self):
  args,_=self.case()
  with self.assertRaises(KeyboardInterrupt):self.verify(args,parent=os.getppid()+1000000)
 def test_changed_driver_refuses_before_native_execution(self):
  args,root=self.case()
  payload={n:str(getattr(args,n)) if getattr(args,n) is not None else None for n in ["plan","source","state","compiler","context","preparation"]}
  payload.update(inspectionTimeoutMs=5000,nonce="1"*32,driverDigest="0"*64)
  with self.assertRaisesRegex(ValueError,"WATCH_VERIFICATION_INPUT"):watch.verify_selected_step(json.dumps(payload))
  self.assertFalse((root/"native-audit.jsonl").exists())


 def test_main_queues_build_and_verification_before_completion(self):
  args,root=self.case();script=root/"controlled-main.py"
  # Only the argument parser is replaced: this fixture has no native build and
  # tests the real main loop/guard chain inside the outer test reservation.
  script.write_text("import argparse,sys\nfrom pathlib import Path\nsys.path.insert(0,"+repr(str(Path(watch.__file__).parent))+")\nimport project_watch as w\na=argparse.Namespace(**"+repr({k:(str(v) if isinstance(v,Path) else v) for k,v in vars(args).items()})+")\n"+
   "for n in ['plan','source','state','compiler']:setattr(a,n,Path(getattr(a,n)))\n"+
   "a.poll_ms=100;a.debounce_ms=0;w.arguments=lambda:a\n"+
   "try:w.main()\nexcept KeyboardInterrupt:raise SystemExit(130)\n")
  out=root/"main.stdout";err=root/"main.stderr";child=None
  try:
   with out.open("xb") as o,err.open("xb") as e:
    child=subprocess.Popen([sys.executable,"-B",str(script)],stdout=o,stderr=e,start_new_session=True)
    deadline=time.monotonic()+20
    while "completed-project-build-update" not in out.read_text():
     self.assertIsNone(child.poll(),err.read_text());self.assertLess(time.monotonic(),deadline,err.read_text());time.sleep(.05)
    child.send_signal(signal.SIGTERM);self.assertEqual(child.wait(timeout=10),130)
   self.assertEqual((root/"runner-audit.txt").read_text().splitlines(),["call","call"])
   rows=[json.loads(x) for x in (root/"native-audit.jsonl").read_text().splitlines()]
   full=[x for x in rows if x["command"] in ["project-build","project-build-verify"]]
   self.assertEqual(full,[{"command":"project-build","reserved":True},{"command":"project-build-verify","reserved":True}])
   events=[json.loads(x) for x in out.read_text().splitlines() if x.startswith("{")]
   self.assertEqual(sum(e.get("status")=="completed-project-build-update" for e in events),1)
  finally:watch.stop(child)

if __name__=="__main__":unittest.main()
