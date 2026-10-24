"""Verify installed source identities and execute an explicit selected application command."""
import argparse,hashlib,importlib.util,json,os,platform,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"));from project_watch import stop
def sha(p):return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()

def verify_installed_source(root, expected_digest):
 """Verify a bound package inventory without Git or following source symlinks."""
 from pathlib import PurePosixPath
 import re
 from package_source import MAX_SOURCE_BYTES
 root=Path(root)
 assert root.is_dir() and not root.is_symlink(), "INSTALLED_SOURCE_ROOT"
 manifest=root/"source-inventory.json"
 assert manifest.is_file() and not manifest.is_symlink(), "INSTALLED_SOURCE_INVENTORY"
 assert re.fullmatch(r"sha256:[0-9a-f]{64}",expected_digest), "INSTALLED_SOURCE_DIGEST"
 assert manifest.stat().st_size <= 4*1024**2 and sha(manifest)==expected_digest, "INSTALLED_SOURCE_INVENTORY_CHANGED"
 entries=json.loads(manifest.read_bytes())
 assert isinstance(entries,list) and 0<len(entries)<=16384, "INSTALLED_SOURCE_INVENTORY"
 expected=set()
 total=manifest.stat().st_size
 for item in entries:
  assert isinstance(item,dict) and set(item)=={"path","digest","bytes"}, "INSTALLED_SOURCE_ENTRY"
  name=item["path"]
  assert isinstance(name,str), "INSTALLED_SOURCE_PATH"
  path=PurePosixPath(name)
  assert name and not path.is_absolute() and ".." not in path.parts and path.as_posix()==name and name!="source-inventory.json", "INSTALLED_SOURCE_PATH"
  assert name not in expected and re.fullmatch(r"sha256:[0-9a-f]{64}",item["digest"]), "INSTALLED_SOURCE_ENTRY"
  assert type(item["bytes"]) is int and 0<=item["bytes"]<=MAX_SOURCE_BYTES, "INSTALLED_SOURCE_BYTES"
  expected.add(name);total+=item["bytes"]
 assert total<=MAX_SOURCE_BYTES, "INSTALLED_SOURCE_BYTES"
 actual=set()
 for path in root.rglob("*"):
  assert not path.is_symlink(), "INSTALLED_SOURCE_SYMLINK"
  if path.is_dir():continue
  assert path.is_file(), "INSTALLED_SOURCE_MEMBER"
  actual.add(path.relative_to(root).as_posix())
 assert actual==expected|{"source-inventory.json"}, "INSTALLED_SOURCE_MEMBERS_CHANGED"
 for item in entries:
  path=root/item["path"]
  assert path.stat().st_size==item["bytes"] and sha(path)==item["digest"], "INSTALLED_SOURCE_BYTES_CHANGED"
 return dict(sourceInventoryDigest=expected_digest,sourceFiles=len(entries),sourceIsInstalled=True)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ["compiler","state","command","output"]:p.add_argument("--"+n,type=Path,required=True)
 a=p.parse_args()
 if not (platform.system()=="Linux" and os.environ.get("GITHUB_ACTIONS")=="true"):
  guard=Path(os.environ.get("LOCAL_STORAGE_PROJECT","/unavailable"))/"scripts/parity/storage_guard.py"
  spec=importlib.util.spec_from_file_location("installed_selected_storage_guard",guard);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  if not module.live_parent():raise RuntimeError("A live existing storage supervisor is required")
 output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
 inventory=json.loads((ROOT/"source-inventory.json").read_bytes())
 inventory_digest=sha(ROOT/"source-inventory.json")
 def unchanged():
  verify_installed_source(ROOT,inventory_digest)
  return True
 assert unchanged()
 sys.path.insert(0,str(ROOT/"scripts/parity"));from identity import identities
 r=dict(status="running",sourceInventoryDigest=sha(ROOT/"source-inventory.json"),sourceFiles=len(inventory),commands=[],productionActivation=False)
 def save():(output/"receipt.json").write_text(json.dumps(r,indent=2)+"\n")
 def run(label,args):
  start=time.monotonic()
  with (output/(label+".stdout")).open("xb") as out,(output/(label+".stderr")).open("xb") as err:
   child=subprocess.Popen([sys.executable,str(ROOT/"scripts/project_watch.py"),"__guard",*map(str,args)],cwd=output,env={k:v for k,v in os.environ.items() if k in ["PATH","HOME","TMPDIR"]},stdout=out,stderr=err,start_new_session=True)
   try:code=child.wait(timeout=180)
   finally:stop(child)
  r["commands"].append(dict(label=label,exitCode=code,elapsedMs=round((time.monotonic()-start)*1000)));save();assert code==0,(label,code)
  return json.loads((output/(label+".stdout")).read_text())
 try:
  compiler=a.compiler.resolve(strict=True);r["compilerDigest"]=sha(compiler)
  engine=run("installed-engine",[compiler,"engine"]);assert engine=={"schemaVersion":"0.1.0","documentType":"executor-description",**identities(ROOT)}
  verify=run("selected-bindings",[compiler,"project-build-verify",a.state.resolve()]);assert verify["status"]=="verified-selected-build-bindings"
  report=run("selected-execution",[compiler,"project-exec-selected",a.state.resolve(),a.command.resolve()])
  assert report["status"]=="completed-selected-project-command" and report["postExecutionSelectionVerified"] and report["selectionPointerUnchanged"]
  assert unchanged()
  r.update(status="passed-installed-selected-application-workflow",engine=engine,execution=report,sourceInventoryUnchanged=True,sourceIsInstalled=True,fixtureScriptsImported=False)
 except BaseException as e:r.update(status="failed",error=str(e));save();raise
 save();print(json.dumps(dict(status=r["status"],sourceFiles=len(inventory))))
if __name__=="__main__":main()
