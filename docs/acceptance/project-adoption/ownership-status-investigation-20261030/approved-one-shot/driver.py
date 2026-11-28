from pathlib import Path
import json,hashlib,subprocess,os,time
D=Path(__file__).resolve().parent
F=json.loads((D/"frozen.json").read_text())
def sha(p):
 with Path(p).open("rb")as f:return hashlib.file_digest(f,"sha256").hexdigest()
for p,h in F["bindings"].items():assert sha(p)==h,"Diagnostic input changed"
assert os.environ.get("WARGAME_STORAGE_RUN_TOKEN"),"Canonical live lease required"
envshape={k:bool(os.environ.get(k))for k in["WARGAME_STORAGE_RUN_TOKEN","WARGAME_STORAGE_OWNER_PID","WARGAME_STORAGE_LEASE_DIR","NODE_OPTIONS"]}
start=time.monotonic()
try:
 p=subprocess.run([F["node"],"--import",str(D/"preload.mjs"),"--input-type=module","-e",(D/"probe.mjs").read_text()],capture_output=True,text=True,timeout=30)
 stdout=p.stdout;stderr=p.stderr;exitcode=p.returncode;timed=False
except subprocess.TimeoutExpired as e:
 stdout=(e.stdout or b"").decode(errors="replace");stderr=(e.stderr or b"").decode(errors="replace");exitcode=None;timed=True
with(D/"probe.stdout.private").open("x")as f:f.write(stdout)
with(D/"probe.stderr.private").open("x")as f:f.write(stderr)
stages=[]
for line in stderr.splitlines():
 try:
  row=json.loads(line)
  if set(row)=={"stage","atMs"}:stages.append(row)
 except json.JSONDecodeError:pass
result=dict(status="traced-ownership-precondition",timeout=timed,exitCode=exitcode,elapsedSeconds=time.monotonic()-start,stages=stages,environmentPresenceOnly=envshape,servicesStarted=0,apiRequests=0,applicationAcceptance=False)
with(D/"receipt.json").open("x")as f:json.dump(result,f,indent=2)
print(json.dumps(result))
raise SystemExit(124 if timed else exitcode)
