import subprocess,os,json,pathlib,hashlib
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';python='/opt/homebrew/bin/python3';cargo='/Users/admin/.cargo/bin/cargo'
commands=[('build',[cargo,'build','--locked','-p','patamaps-cli']),('native',[python,'-B','scripts/parity/native.py']),('registry-controls',[node,'scripts/parity/registry_contracts.mjs']),('file-controls',[node,'scripts/parity/pack_contracts.mjs','--files']),('nested-controls',[node,'scripts/parity/pack_contracts.mjs','--nested']),('pack-controls',[node,'scripts/parity/pack_contracts.mjs']),('frozen-validation',[node,'scripts/parity/legacy_validation.mjs'])]
commands += [('original-'+name,[node,'scripts/parity/original.mjs']+([] if name=='canonical' else ['--'+name])) for name in ['canonical','sssom','discovery','sssom-adapter','validation','registry','graph']]
commands += [('discovery-api',[python,'-B','scripts/parity/discovery_api.py']),('scientific-bounds',[python,'-B','scripts/parity/scientific_bounds.py'])]
rows=[];functional=[]
reused=['docs/acceptance/parity/graph-controls-2026-10-12T19-52-17.896Z/receipt.json',str(sorted((root/'docs/acceptance/parity').glob('sdk-consumer-*/receipt.json'))[-1].relative_to(root)),'docs/acceptance/parity/graph-focused-2026-10-12T19-55-44.279878+00-00/receipt.json']
for path in reused:
 raw=(root/path).read_bytes();r=json.loads(raw);assert r['status'] in ['passed','matched']
 if 'candidate' in r:
  assert r['candidate']['binaryDigest']=='sha256:'+hashlib.sha256((root/'target/debug/patamaps').read_bytes()).hexdigest()
  for item in r['candidate'].get('sdkSourceInventory',[]):assert item['digest']=='sha256:'+hashlib.sha256((root/item['path']).read_bytes()).hexdigest()
 functional.append({'path':path,'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),'reused':True})
for label,command in commands:
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr:
  result=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 row={'label':label,'command':command,'exitCode':result.returncode};rows.append(row);print(label,result.returncode,flush=True)
 text=(out/(label+'.stdout.log')).read_text();receipt=None
 try:
  observed=json.JSONDecoder().raw_decode(text.lstrip())[0]
  if isinstance(observed,dict) and observed.get('receipt'):receipt=root/observed['receipt']
 except ValueError:pass
 if receipt:
  raw=receipt.read_bytes();component=json.loads(raw);functional.append({'path':receipt.relative_to(root).as_posix(),'digest':'sha256:'+hashlib.sha256(raw).hexdigest()})
  if label.startswith('original-') and result.returncode==0:
   attach=[python,'-B','scripts/parity/verify.py','--record',str(receipt)]
   with (out/(label+'.attachment.stdout.log')).open('w') as stdout,(out/(label+'.attachment.stderr.log')).open('w') as stderr:
    attached=subprocess.run(attach,cwd=root,env=env,stdout=stdout,stderr=stderr)
   row['attachmentExitCode']=attached.returncode
   print(label+' attachment',attached.returncode,flush=True)
   # Existing rows can be stale until the last original scope is refreshed.
 if result.returncode:break
binary=root/'target/debug/patamaps'
record={'schemaVersion':'1.0.0','status':'passed' if len(rows)==len(commands) and all(r['exitCode']==0 for r in rows) else 'failed','commands':rows,'functionalEvidence':functional,'binaryDigest':'sha256:'+hashlib.sha256(binary.read_bytes()).hexdigest(),'candidateEngine':json.loads(subprocess.check_output([binary,'engine'])),'scope':'Current graph/native/SDK component refresh. Original callbacks and expectations remain unchanged; complete package, accepted-domain and platform parity remain unresolved.'}
(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(out/'receipt.json',flush=True)
raise SystemExit(0 if record['status']=='passed' else 1)
