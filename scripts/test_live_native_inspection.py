"""Controlled live ownership faults; not an installed-supervisor attestation."""
from pathlib import Path
import copy,json,os,signal,socket,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
import native_inspection_guard as live
import project_watch as watch

WORKER = """
from pathlib import Path
import json,os,subprocess,sys
sys.path.insert(0,SCRIPTS)
import native_inspection_guard as live
spec=json.loads(Path(sys.argv[1]).read_text())
root=Path(spec["root"])
fd=int(sys.argv[2]) if len(sys.argv)>2 else None
if spec.get("fake"):
 def spawn(path,descriptor,control_write,*,stdout=subprocess.PIPE,stderr=subprocess.PIPE):
  return subprocess.Popen([sys.executable,"-I","-S","-B",spec["fake"],str(path),str(control_write),spec["mode"]],
   stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,pass_fds=(control_write,),close_fds=True,start_new_session=True)
 live.InspectionRunner.spawn=staticmethod(spawn)
run=live.InspectionRunner(root/"jobs",root,strict=True,stop_grace=.2,lifecycle_fd=fd)
try:
 result=run([str(Path(sys.executable).resolve()),"-I","-S","-B","-c",spec["payload"]],
  stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8,check=False)
 value=dict(ok=True,exitCode=result.returncode,stdout=result.stdout.decode(),stderr=result.stderr.decode())
except BaseException as e:
 value=dict(ok=False,errorType=type(e).__name__,error=str(e))
finally:
 value["calls"]=run.calls
 (root/"result.json").write_text(json.dumps(value,indent=2))
 if fd is not None:os.close(fd)
"""

FAKE = """
from pathlib import Path
import json,os,subprocess,sys,time
d=json.loads(Path(sys.argv[1]).read_text());fd=int(sys.argv[2]);mode=sys.argv[3]
common=dict(runId=d["runId"],guardianPid=os.getpid(),parentPid=os.getppid())
def emit(event,sequence,**values):
 raw=(json.dumps(dict(common,event=event,sequence=sequence,**values))+"\\n").encode()
 if mode=="fragmented":
  for i in range(0,len(raw),7):os.write(fd,raw[i:i+7]);time.sleep(.001)
 else:os.write(fd,raw)
if mode=="malformed":os.write(fd,b"{not-json}\\n");time.sleep(60)
elif mode=="oversized":os.write(fd,b"x"*13000);time.sleep(60)
elif mode=="partial":os.write(fd,b'{"event":');os.close(fd)
elif mode=="pending":emit("launch-pending",0);time.sleep(60)
elif mode=="pending-survivor":
 emit("launch-pending",0)
 child=subprocess.Popen(["/bin/sleep","60"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
  stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True)
 (Path(sys.argv[1]).parent/"unregistered-worker.json").write_text(json.dumps(dict(pid=child.pid,guardianPid=os.getpid())))
 time.sleep(60)
elif mode=="fragmented":
 emit("launch-pending",0)
 child=subprocess.Popen([sys.executable,"-I","-S","-B","-c","import time;time.sleep(.4);print('fragmented')"],
  close_fds=True,start_new_session=True)
 emit("payload-started",1,pid=child.pid,pgid=child.pid)
 code=child.wait()
 emit("payload-stopped",2,pid=child.pid,pgid=child.pid,returncode=code,
  stdoutClosed=True,stderrClosed=True,bindingsUnchanged=True)
 os.close(fd)
"""

@unittest.skipUnless(sys.platform=="darwin","requires qualified Darwin process identity")
class LiveOwnership(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(tempfile.mkdtemp(prefix="live-ownership-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"])).resolve()
  cls.root.chmod(0o700)
 def fixture(self):
  case=self.root/self._testMethodName;case.mkdir(mode=0o700)
  (case/"jobs").mkdir(mode=0o700)
  return case
 def payload(self,close=False):
  return ("import json,os,signal,time\nfrom pathlib import Path\n"
   "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
   "closed=True\n"
   "for fd in range(3,96):\n"
   " try:os.write(fd,b'forged-observer');closed=False\n"
   " except OSError:pass\n"
   "Path('ready').write_text('ready')\n"+
   ("os.close(1);os.close(2)\n" if close else "")+
   "while not Path('go').exists():time.sleep(.02)\n"+
   ("" if close else "print(json.dumps(dict(extraDescriptorsClosed=closed)))\n"))
 def launch(self,case,mode="normal",fd=None,close=False):
  (case/"worker.py").write_text(WORKER.replace("SCRIPTS",repr(str(Path(live.__file__).parent))))
  spec=dict(root=str(case),mode=mode,payload=self.payload(close))
  if mode!="normal":
   (case/"fake.py").write_text(FAKE);spec["fake"]=str(case/"fake.py")
  (case/"spec.json").write_text(json.dumps(spec))
  with (case/"worker.stdout").open("xb") as out,(case/"worker.stderr").open("xb") as err:
   return subprocess.Popen([sys.executable,"-I","-S","-B",str(case/"worker.py"),str(case/"spec.json")]+([str(fd)] if fd is not None else []),
    stdout=out,stderr=err,pass_fds=((fd,) if fd is not None else ()),start_new_session=True)
 def wait(self,case,child,predicate,seconds=12):
  deadline=time.monotonic()+seconds
  while time.monotonic()<deadline:
   snapshots=list((case/"jobs").glob("*/live.json"))
   for p in snapshots:
    try:v=json.loads(p.read_text())
    except (OSError,ValueError):continue
    if predicate(v):
     (case/"observed-live.json").write_text(json.dumps(v,indent=2))
     return p.parent,v
   if child.poll() is not None:break
   time.sleep(.02)
  self.fail("live phase missing: "+(case/"worker.stderr").read_text())
 def result(self,case,child):
  child.wait(timeout=12)
  self.assertEqual(child.returncode,0,(case/"worker.stderr").read_text())
  return json.loads((case/"result.json").read_text())
 def cleanup(self,case,child):
  if child.poll() is None:watch.stop(child,grace=.5)
  for p in (case/"jobs").glob("*/live.json"):
   value=json.loads(p.read_text())
   for key in ["guardianIdentity","nativeIdentity"]:
    identity=value.get(key)
    if identity is not None:
     live.stop_registered(identity,.2)
 def normal(self,close=False,kill=False):
  case=self.fixture();child=self.launch(case,close=close)
  try:
   job,v=self.wait(case,child,lambda v:v["phase"]=="payload-started" and v["nativeIdentity"] is not None)
   self.assertIs(v["registrationKnown"],True)
   self.assertEqual(v["acceptedRecordCount"],2)
   self.assertIsNone(child.poll())
   self.assertTrue(live.same_process(v["nativeIdentity"],live.process_identity(v["nativeIdentity"]["pid"])))
   deadline=time.monotonic()+5
   while not (job/"work/ready").exists():
    self.assertIsNone(child.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.01)
   if kill:os.kill(v["guardianPid"],signal.SIGKILL)
   else:(job/"work/go").write_text("go")
   result=self.result(case,child)
   if kill:
    self.assertFalse(result["ok"])
    self.assertIn("INSPECTION_CONTROL_INCOMPLETE",result["error"])
    self.assertIs(result["calls"][0]["cleanup"]["confirmed"],True)
    self.assertIs(result["calls"][0]["controlComplete"],False)
   else:
    self.assertTrue(result["ok"],result)
    self.assertEqual(result["exitCode"],0)
    if not close:self.assertIs(json.loads(result["stdout"])["extraDescriptorsClosed"],True)
    self.assertIs(result["calls"][0]["controlComplete"],True)
   self.assertFalse(live.group_live(v["nativeIdentity"]["pid"]))
  finally:self.cleanup(case,child)
 def test_records_visible_before_worker_exit(self):self.normal()
 def test_early_stdout_close_does_not_finish_ownership(self):self.normal(close=True)
 def test_guardian_sigkill_stops_registered_native(self):self.normal(kill=True)
 def fake(self,mode,kill=False):
  case=self.fixture();child=self.launch(case,mode)
  try:
   if kill:
    job,v=self.wait(case,child,lambda v:v["phase"]=="launch-pending")
    self.assertIs(v["registrationKnown"],False)
    os.kill(v["guardianPid"],signal.SIGKILL)
   value=self.result(case,child)
   paths=list((case/"jobs").glob("*/control.json"));self.assertEqual(len(paths),1)
   receipt=json.loads(paths[0].read_text())
   if mode=="fragmented":
    self.assertTrue(value["ok"],value)
    self.assertEqual(value["stdout"],"fragmented\n")
    self.assertEqual(len(receipt["records"]),3)
   else:
    self.assertFalse(value["ok"])
    self.assertIs(receipt["controlComplete"],False)
    self.assertIs(receipt["cleanup"]["confirmed"],False)
    raw=paths[0].parent/"control.raw"
    self.assertTrue(raw.exists())
    self.assertLessEqual(raw.stat().st_size,3*live.MAX_RECORD_BYTES)
   return value
  finally:self.cleanup(case,child)
 def test_pending_launch_sigkill_stays_unsealed(self):
  self.assertIn("INSPECTION_CONTROL_INCOMPLETE",self.fake("pending",True)["error"])
 def test_pending_launch_with_unregistered_survivor_stays_uncertain(self):
  case=self.fixture();child=self.launch(case,"pending-survivor")
  unknown_identity=None
  try:
   job,v=self.wait(case,child,lambda v:v["phase"]=="launch-pending")
   marker=job/"unregistered-worker.json";deadline=time.monotonic()+5
   while not marker.exists():
    self.assertIsNone(child.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.01)
   owned=json.loads(marker.read_text());unknown_identity=live.process_identity(owned["pid"])
   self.assertEqual(unknown_identity["parentPid"],v["guardianPid"])
   self.assertEqual(unknown_identity["pgid"],owned["pid"])
   os.kill(v["guardianPid"],signal.SIGKILL)
   value=self.result(case,child)
   self.assertFalse(value["ok"])
   self.assertIs(value["calls"][0]["cleanup"]["confirmed"],False)
   self.assertIs(value["calls"][0]["controlComplete"],False)
   self.assertTrue(live.same_process(unknown_identity,live.process_identity(owned["pid"])))
   self.assertTrue(live.group_live(owned["pid"]))
   (case/"unregistered-survivor.json").write_text(json.dumps(dict(identity=unknown_identity,
    workerSurvivedRefusal=True,unconfirmedOwnershipPreserved=True),indent=2))
  finally:
   if unknown_identity is not None:
    self.assertTrue(live.stop_registered(unknown_identity,.2))
   self.cleanup(case,child)
 def test_fragmented_control_records_are_accepted(self):self.fake("fragmented")
 def test_malformed_record_is_retained_and_refused(self):
  self.assertEqual(self.fake("malformed")["errorType"],"JSONDecodeError")
 def test_oversized_control_is_bounded_and_refused(self):
  self.assertIn("INSPECTION_CONTROL_",self.fake("oversized")["error"])
 def test_partial_control_at_eof_refuses(self):
  self.assertIn("INSPECTION_CONTROL_PARTIAL_RECORD",self.fake("partial")["error"])
 def test_kernel_identity_mismatch_never_signals(self):
  case=self.fixture()
  child=subprocess.Popen(["/bin/sleep","60"],start_new_session=True)
  try:
   identity=live.process_identity(child.pid);forged=dict(identity,startMicroseconds=identity["startMicroseconds"]+1)
   with patch.object(live.os,"killpg") as signal_group:
    self.assertIs(live.stop_registered(forged,.05),False)
    signal_group.assert_not_called()
   self.assertIsNone(child.poll())
   (case/"identity-refusal.json").write_text(json.dumps(dict(identity=identity,forged=forged,refused=True)))
  finally:watch.stop(child,grace=.2)
 def test_duplicate_or_changed_prefix_is_rejected(self):
  case=self.fixture();common=dict(runId="a"*32,guardianPid=10,parentPid=20)
  first=dict(common,event="launch-pending",sequence=0)
  second=dict(common,event="payload-started",sequence=1,pid=30,pgid=30)
  live.validate_prefix([first,second],"a"*32,10)
  for rows in [[first,first],[first,dict(second,parentPid=21)],[dict(first,extra=True)]]:
   with self.assertRaises(ValueError):live.validate_prefix(rows,"a"*32,10)
  (case/"prefix-refusal.json").write_text(json.dumps(dict(refused=3)))
 def observer(self,transport,lose=False):
  case=self.fixture()
  if transport=="pipe":
   reader,writer=os.pipe();reader_socket=writer_socket=None
  else:
   reader_socket,writer_socket=socket.socketpair()
   reader,writer=reader_socket.fileno(),writer_socket.fileno()
  child=self.launch(case,fd=writer)
  if writer_socket is None:os.close(writer)
  else:writer_socket.close()
  try:
   job,v=self.wait(case,child,lambda v:v["phase"]=="payload-started" and v["nativeIdentity"] is not None)
   os.set_blocking(reader,False)
   captured=bytearray()
   deadline=time.monotonic()+5
   while b"payload-started" not in captured:
    self.assertLess(time.monotonic(),deadline)
    try:chunk=os.read(reader,65536)
    except BlockingIOError:time.sleep(.01);continue
    self.assertTrue(chunk)
    captured.extend(chunk)
   self.assertIn(b"payload-started",captured)
   if lose:
    reader_socket.close();reader_socket=None;reader=None
   (job/"work/go").write_text("go")
   result=self.result(case,child)
   if lose:
    self.assertFalse(result["ok"])
    self.assertIs(result["calls"][0]["controlComplete"],False)
    self.assertIs(result["calls"][0]["observerComplete"],False)
   else:
    while True:
     try:chunk=os.read(reader,65536)
     except BlockingIOError:break
     if not chunk:break
     captured.extend(chunk)
    frames=[json.loads(line) for line in captured.splitlines()]
    self.assertEqual([x["event"] for x in frames],["guardian-launch-pending","guardian-started","guardian-record","guardian-record","guardian-record","inspection-finished"])
    self.assertEqual([x["sequence"] for x in frames],list(range(6)))
    self.assertTrue(result["ok"],result)
    self.assertIs(json.loads(result["stdout"])["extraDescriptorsClosed"],True)
    (case/"observer.json").write_text(json.dumps(frames,indent=2))
   self.assertFalse(live.group_live(v["nativeIdentity"]["pid"]))
  finally:
   if reader_socket is not None:reader_socket.close()
   elif reader is not None:os.close(reader)
   self.cleanup(case,child)
 def test_outer_pipe_is_live_and_not_inherited(self):self.observer("pipe")
 def test_outer_socketpair_is_live_and_not_inherited(self):self.observer("socket")
 def test_observer_loss_after_registration_refuses(self):self.observer("socket",True)
 def test_broken_observer_refuses_before_spawn(self):
  case=self.fixture();r,w=os.pipe();os.close(r)
  run=live.InspectionRunner(case/"jobs",case,strict=True,lifecycle_fd=w)
  try:
   with self.assertRaises(BrokenPipeError):
    run([str(Path(sys.executable).resolve()),"-c","pass"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3,check=False)
   self.assertIsNone(run.calls[0]["guardianPid"])
   self.assertIs(run.calls[0]["controlComplete"],False)
   self.assertIs(run.calls[0]["observerComplete"],False)
  finally:os.close(w)

if __name__=="__main__":unittest.main()
