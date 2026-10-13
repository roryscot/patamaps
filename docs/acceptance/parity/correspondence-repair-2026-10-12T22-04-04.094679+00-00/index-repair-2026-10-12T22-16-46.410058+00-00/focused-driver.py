import subprocess,pathlib,os,json
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent;node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node'
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
rows=[]
for label,cmd in [('freeze-correspondence',[node,'scripts/parity/correspondence_contracts.mjs','--freeze-only']),('freeze-references',[node,'scripts/parity/reference_contracts.mjs','--freeze-only']),('build',['/Users/admin/.cargo/bin/cargo','build','--locked','-p','patamaps-cli']),('correspondence-controls',[node,'scripts/parity/correspondence_contracts.mjs']),('reference-controls',[node,'scripts/parity/reference_contracts.mjs'])]:
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr: result=subprocess.run(cmd,cwd=root,env=env,stdout=stdout,stderr=stderr)
 rows.append({'label':label,'command':cmd,'exitCode':result.returncode});print(label,result.returncode,flush=True)
 if result.returncode:break
(out/'focused-receipt.json').write_text(json.dumps({'schemaVersion':'1.0.0','status':'passed' if len(rows)==5 and all(x['exitCode']==0 for x in rows) else 'failed','commands':rows},indent=2)+'\n')
raise SystemExit(0 if len(rows)==5 and all(x['exitCode']==0 for x in rows) else 1)
