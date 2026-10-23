"""Verify installed source identities and execute an explicit selected application command."""
import argparse,hashlib,importlib.util,json,os,platform,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"));from project_watch import stop
def sha(p):return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
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
 def unchanged():
  names={p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()}
  return names=={i["path"] for i in inventory}|{"source-inventory.json"} and all((ROOT/i["path"]).is_file() and (ROOT/i["path"]).stat().st_size==i["bytes"] and sha(ROOT/i["path"])==i["digest"] for i in inventory)
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
