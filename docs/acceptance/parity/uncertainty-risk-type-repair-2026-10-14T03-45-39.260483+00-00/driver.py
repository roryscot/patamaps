from pathlib import Path
import json,os,sys,subprocess,tempfile,hashlib
root=Path.cwd();out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
from storage_copy import copy_file
ensure_guarded()
old=Path(json.loads((out/'scope.json').read_text())['retainedPreviousStage'])
stage=Path(tempfile.mkdtemp(prefix='patamaps-uncertainty-types-',dir='/private/tmp'))
for source in (root/'sdk/typescript').rglob('*'):
 if source.is_file():copy_file(source,stage/'node_modules/patamaps-native-sdk-draft'/source.relative_to(root/'sdk/typescript'))
for source in (old/'reference-contracts').rglob('*.d.ts'):copy_file(source,stage/'reference-contracts'/source.relative_to(old/'reference-contracts'))
for name in ['type-contracts.mts','consumer.mts','negative.mts']:copy_file(old/name,stage/name)
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';tsc='/Users/admin/dev/SEEDZ/metamap/node_modules/typescript/lib/tsc.js';rows=[]
for label,filename in [('declarations','type-contracts.mts'),('positive','consumer.mts'),('negative','negative.mts')]:
 command=[node,tsc,filename,'--strict','--module','NodeNext','--moduleResolution','NodeNext','--target','ES2022','--lib','ES2022','--noEmit']
 result=subprocess.run(command,cwd=stage,capture_output=True)
 for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:(out/(label+'.'+stream+'.log')).write_bytes(data)
 rows.append({'label':label,'command':command,'exitCode':result.returncode});assert result.returncode==(2 if label=='negative' else 0),(label,result.stdout.decode())
(out/'receipt.json').write_text(json.dumps({'status':'passed','commands':rows,'retainedStage':str(stage),'previousStageModified':False,'runtimeChanged':False,'sourceDigest':'sha256:'+hashlib.sha256((root/'sdk/typescript/legacy-uncertainty-risk.d.ts').read_bytes()).hexdigest()},indent=2)+'\n')
print('declarations and positive consumers pass; negative program rejects')
