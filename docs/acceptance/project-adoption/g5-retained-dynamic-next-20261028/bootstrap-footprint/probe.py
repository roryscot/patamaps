"""Bounded public pnpm bootstrap footprint probe; no owner qualification."""
import hashlib,json,os,subprocess,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
assert os.environ.get("WARGAME_STORAGE_RUN_TOKEN")
NODE=Path("/Users/admin/.nvm/versions/node/v22.23.3/bin/node")
NPM=NODE.parent/"npm"
def inventory(root):
 rows={}
 for parent,dirs,files in os.walk(root,followlinks=False):
  for name in sorted(files):
   p=Path(parent)/name
   if p.is_symlink():continue
   st=p.stat();rows[str(p.relative_to(root))]=dict(bytes=st.st_size,allocated=st.st_blocks*512,digest=hashlib.sha256(p.read_bytes()).hexdigest())
 return rows
def size(rows):return dict(files=len(rows),bytes=sum(x["bytes"]for x in rows.values()),allocated=sum(x["allocated"]for x in rows.values()))
cache=BASE/"npm-cache";cache.mkdir()
result=dict(status="running",applicationRun=False,filesDeleted=0,policyChanged=False,scope="Public pnpm@10.32.1 bootstrap only; Intel footprint does not predict Linux filesystem savings",cases={})
for label in ["a","b"]:
 home=BASE/("home-"+label);home.mkdir();tmp=BASE/("tmp-"+label);tmp.mkdir()
 user=BASE/("npm-user-"+label+".conf");user.write_text("");global_config=BASE/("npm-global-"+label+".conf");global_config.write_text("")
 env=dict(PATH=str(NODE.parent)+":/usr/bin:/bin",HOME=str(home),TMPDIR=str(tmp),npm_config_userconfig=str(user),npm_config_globalconfig=str(global_config))
 prefix=BASE/("tools-"+label)
 with (BASE/(label+".stdout")).open("xb")as out,(BASE/(label+".stderr")).open("xb")as err:
  subprocess.run([str(NPM),"install","--prefix",str(prefix),"pnpm@10.32.1","--ignore-scripts","--no-audit","--no-fund","--cache",str(cache)],env=env,cwd=BASE,stdout=out,stderr=err,timeout=120,check=True)
 version=subprocess.check_output([str(NODE),str(prefix/"node_modules/pnpm/bin/pnpm.cjs"),"--version"],env=env,cwd=BASE,text=True,timeout=15).strip()
 assert version=="10.32.1"
 rows=inventory(prefix/"node_modules/pnpm")
 result["cases"][label]=dict(version=version,pnpm=size(rows),pnpmEntryDigest=hashlib.sha256((prefix/"node_modules/pnpm/bin/pnpm.cjs").read_bytes()).hexdigest(),npmCache=size(inventory(cache)))
 if label=="a":first=rows
 else:assert rows==first
result["status"]="passed"
result["samePinnedPackageBytes"]=True
result["isolatedHomesAndTemporaryDirectories"]=True
result["secondCacheGrowthBytes"]=result["cases"]["b"]["npmCache"]["allocated"]-result["cases"]["a"]["npmCache"]["allocated"]
result["linuxSavingsEstablished"]=False
result["runtimeRepairAttemptUsed"]=False
(BASE/"result.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
