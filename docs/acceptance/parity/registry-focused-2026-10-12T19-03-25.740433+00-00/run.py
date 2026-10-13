from pathlib import Path
import os,json,subprocess,hashlib
ROOT=Path('/Users/admin/dev/patamaps/patamaps')
OUT=Path(__file__).resolve().parent
ENV={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
NODE='/Users/admin/.nvm/versions/node/v24.21.0/bin/node'
CARGO='/Users/admin/.cargo/bin/cargo'
commands=[('build',[CARGO,'build','--locked','-p','patamaps-cli']),('registry-tests',[CARGO,'test','--locked','-p','patamaps-core','--test','legacy_registry']),('original-registry',[NODE,str(ROOT/'scripts/parity/original.mjs'),'--registry'])]
receipt={'status':'running','scope':'Focused original executable-pack cases and native registry regression checks; not full parity','commands':[],'sourceInventory':[{'path':str(p.relative_to(ROOT)),'digest':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'crates').rglob('*.rs'))]+[{'path':str(p.relative_to(ROOT)),'digest':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'sdk/typescript').glob('*')) if p.is_file()]}
for label,command in commands:
 print('Starting '+label,flush=True)
 with (OUT/(label+'.stdout')).open('x') as stdout,(OUT/(label+'.stderr')).open('x') as stderr:
  result=subprocess.run(command,cwd=ROOT,env=ENV,stdout=stdout,stderr=stderr)
 receipt['commands'].append({'label':label,'command':command,'exitCode':result.returncode,'logs':{name:{'path':str((OUT/(label+'.'+name)).relative_to(ROOT)),'digest':'sha256:'+hashlib.sha256((OUT/(label+'.'+name)).read_bytes()).hexdigest()} for name in ['stdout','stderr']}})
 print(label+' exit '+str(result.returncode),flush=True)
 if result.returncode: break
receipt['status']='passed' if len(receipt['commands'])==len(commands) and all(c['exitCode']==0 for c in receipt['commands']) else 'failed'
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':receipt['status'],'receipt':str((OUT/'receipt.json').relative_to(ROOT))}),flush=True)
raise SystemExit(0 if receipt['status']=='passed' else 1)
