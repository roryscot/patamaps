from pathlib import Path
import sys,time
sys.path.insert(0,"/Volumes/dev_src_case_sensitive/projects/patamaps/scripts")
from project_watch import guard
D=Path(__file__).resolve().parent
start=time.monotonic()
def tick(child):
 if time.monotonic()-start>60:raise RuntimeError("Diagnostic controller deadline")
if __name__=="__main__":raise SystemExit(guard([sys.executable,"-B",str(D/"driver.py")],tick=tick))
