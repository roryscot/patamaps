import subprocess,os,json,pathlib,hashlib,re
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';cargo='/Users/admin/.cargo/bin/cargo'
commands=[('build',[cargo,'build','--offline','-p','patamaps-cli']),('native-contracts-core',[cargo,'test','--locked','-p','patamaps-contracts','-p','patamaps-core']),('digest-controls',[node,'scripts/parity/digest_contracts.mjs']),('composition-controls',[node,'scripts/parity/composition_contracts.mjs']),('pack-controls',[node,'scripts/parity/pack_contracts.mjs']),('registry-controls',[node,'scripts/parity/registry_contracts.mjs'])]
rows=[];functional=[]
for label,command in commands:
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr:
  r=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 rows.append({'label':label,'command':command,'exitCode':r.returncode});print(label,r.returncode,flush=True)
 for match in re.finditer(r'(?m)^\{',(out/(label+'.stdout.log')).read_text()):
  try:
   observed=json.JSONDecoder().raw_decode((out/(label+'.stdout.log')).read_text()[match.start():])[0]
   if isinstance(observed,dict) and observed.get('receipt'):
    p=root/observed['receipt'];functional.append({'path':p.relative_to(root).as_posix(),'digest':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()})
  except ValueError:pass
 if r.returncode:break
receipt={'status':'passed' if len(rows)==len(commands) and all(r['exitCode']==0 for r in rows) else 'failed','commands':rows,'functionalEvidence':functional}
(out/'focused-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(out/'focused-receipt.json',flush=True)
raise SystemExit(0 if receipt['status']=='passed' else 1)
