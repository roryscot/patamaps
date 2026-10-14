import ast,hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path('/Users/admin/dev/patamaps/patamaps');sys.path.insert(0,str(root/'scripts/parity'));sys.path.insert(0,str(root/'scripts/capabilities'))
from storage_guard import ensure_guarded,node_runtime
from identity import identities
from retained_copy import copy_tree
ensure_guarded()
phase=sys.argv[1];ranges={'install':(20,24),'rust-sdk':(24,35),'memory':(35,42),'source':(42,51),'runtime':(51,56),'interfaces':(56,64)};assert phase in ranges
work=root/'.tools/capabilities/installed-bmgsq0pg';original_output=root/'docs/acceptance/capabilities/installed-2026-10-14T22-17-26.355315Z'
source,=(work/'source').iterdir();original_driver=root/'scripts/capabilities/install.py';raw=original_driver.read_bytes();assert raw==(source/'scripts/capabilities/install.py').read_bytes()
tree=ast.parse(raw);main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');nodes=next(n for n in main.body if isinstance(n,ast.Try)).body;assert len(nodes)==65
out=root/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('installed-bounded-'+phase+'-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes());(out/'original-install.py').write_bytes(raw)
commands=[];report={'status':'running','phase':phase,'retainedWork':work.relative_to(root).as_posix(),'originalPackageReceipt':(original_output/'receipt.json').relative_to(root).as_posix(),'originalDriverDigest':'sha256:'+hashlib.sha256(raw).hexdigest(),'commands':commands,'scope':'Execute the original installation assertions and commands in bounded guarded phases; reuse one exact package/source tree. Original interrupted receipt remains unchanged.','deleted':[],'storageSettingsChanged':False};receipt=out/'receipt.json'
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def save():receipt.write_text(json.dumps(report,indent=2)+'\n')
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','PYTHONDONTWRITEBYTECODE':'1','CARGO_TARGET_DIR':str(root/'target/package-test'),'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk'}
cargo=Path('/Users/admin/.cargo/bin/cargo');rustc=Path('/Users/admin/.cargo/bin/rustc')
def run(label,argv,cwd=root,environment=env):
 result=subprocess.run([str(v) for v in argv],cwd=cwd,env=environment,capture_output=True)
 item={'label':label,'argv':[str(v) for v in argv],'exitCode':result.returncode}
 for stream in ['stdout','stderr']:
  raw=getattr(result,stream);log=out/(label+'.'+stream+'.log');log.write_bytes(raw);item[stream]={'path':log.relative_to(root).as_posix(),'digest':digest(raw)}
 commands.append(item);save();print(json.dumps({'check':label,'exitCode':result.returncode}),flush=True)
 assert result.returncode==0,label+' failed; inspect retained logs'
 return result.stdout.decode()
context={'__builtins__':__builtins__,'ROOT':root,'Path':Path,'json':json,'os':os,'sys':sys,'tarfile':__import__('tarfile'),'work':work,'output':original_output,'source':source,'installation':work/'installation','cli':work/'installation/bin/patamaps','consumer':work/'consumer','env':env,'cargo':cargo,'rustc':rustc,'digest':digest,'identities':identities,'run':run,'copy_tree':copy_tree,'node_runtime':node_runtime}
def execute(selected):
 exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),str(original_driver),'exec'),context)
save()
try:
 # Extraction was completed in separately recorded bounded stages. Execute all
 # original source/archive assertions without creating or re-extracting a tree.
 validation=[nodes[i] for i in [0,2,3,4,5,6,9,10,11,12,13,14,15,16,17,18,19]]
 execute(validation);report['sourceInventoryEntries']=len(context['inventory']);report['sourceInventoryDigest']=context['distribution']['sourceInventoryDigest'];report['engines']=context['expected'];report['sourceBytesVerified']=True
 if phase!='install':assert json.loads(subprocess.check_output([context['cli'],'engine']))==context['expected']
 first,last=ranges[phase];selected=nodes[first:last];report['executedStatementRange']=[first,last];report['originalStatementsDigest']=digest(ast.dump(ast.Module(body=selected,type_ignores=[]),include_attributes=False).encode());save()
 execute(selected)
 report.update(status='passed',outputs={name:context[name] for name in ['generation','memory','source_report','source_cli'] if name in context},completedAtUtc=datetime.now(timezone.utc).isoformat())
except BaseException as error:report.update(status='failed',error=str(error));raise
finally:save();print(json.dumps({'status':report['status'],'phase':phase,'receipt':str(receipt.relative_to(root))}),flush=True)
