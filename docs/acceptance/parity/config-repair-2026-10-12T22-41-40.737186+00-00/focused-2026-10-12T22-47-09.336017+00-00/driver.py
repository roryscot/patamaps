import subprocess,os,json,pathlib,re
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';python='/opt/homebrew/bin/python3';cargo='/Users/admin/.cargo/bin/cargo'
commands=[('clippy',[cargo,'clippy','--locked','--workspace','--all-targets','--','-D','warnings']),('config-native',[cargo,'test','--locked','-p','patamaps-scientific','--test','legacy_config']),('config-controls',[node,'scripts/parity/config_contracts.mjs']),('installed-sdk',[python,'-B','scripts/parity/sdk_consumer.py']),('original-config',[node,'scripts/parity/original.mjs','--config'])]
rows=[]
for label,command in commands:
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr: result=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 rows.append({'label':label,'command':command,'exitCode':result.returncode});print(label,result.returncode,flush=True)
 if result.returncode:break
(out/'receipt.json').write_text(json.dumps({'status':'passed' if len(rows)==len(commands) and all(x['exitCode']==0 for x in rows) else 'failed','commands':rows},indent=2)+'\n');print(out/'receipt.json',flush=True)
raise SystemExit(0 if len(rows)==len(commands) and all(x['exitCode']==0 for x in rows) else 1)
