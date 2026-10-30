from pathlib import Path
import sys,os,json,subprocess,time
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps")
sys.path.insert(0,str(R/"scripts"))
from project_watch import guard
B=Path(__file__).resolve().parent
DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
def read(p):return json.loads(p.read_text())
def inspect():
 p=B/"container.json"
 if not p.exists():return None
 cfg=read(p)
 r=subprocess.run([DOCKER,"inspect",cfg["containerId"]],capture_output=True,text=True,timeout=20)
 if r.returncode:raise RuntimeError("OWNED_CONTAINER_INSPECTION_UNCERTAIN")
 d=json.loads(r.stdout)[0];labels=d["Config"].get("Labels")or{}
 assert d["Id"]==cfg["containerId"]and labels.get("patamaps.auth.owner")==cfg["ownerToken"]and labels.get("buildctl.project")==str(R)
 return d
def cleanup():
 d=inspect()
 if d and(d["State"]["Running"]or d["State"]["Restarting"]):
  subprocess.run([DOCKER,"stop","--time","10",d["Id"]],capture_output=True,timeout=20,check=True)
 d=inspect()
 assert d is None or(not d["State"]["Running"]and not d["State"]["Restarting"]and d["State"]["Pid"]==0)
 (B/"owned-container-stop.json").write_text(json.dumps(dict(stopped=True,containerId=None if d is None else d["Id"],containerDeleted=False,dataDeleted=False)))
def tick(child):
 if time.monotonic()-began>600:raise RuntimeError("OWNED_AUTH_PHASE_DEADLINE")
 for n in["migrate","seed","server"]:
  for suffix in["stdout","stderr"]:
   p=B/"run"/(n+"."+suffix)
   if p.exists()and p.stat().st_size>4194304:raise RuntimeError("OWNED_AUTH_LOG_BOUND")
 if time.monotonic()-tick.last>5:
  tick.last=time.monotonic();total=0;count=0
  data=B/"database"
  if data.exists():
   for folder,dirs,files in os.walk(data):
    for name in files:
     p=Path(folder)/name
     if p.is_symlink():continue
     total+=p.stat().st_blocks*512;count+=1
     if count>16384 or total>536870912:raise RuntimeError("OWNED_DATABASE_GROWTH_BOUND")
tick.last=0
if __name__=="__main__":
 began=time.monotonic()
 raise SystemExit(guard([sys.executable,"-B",str(B/"run.py")],cleanup=cleanup,tick=tick))
