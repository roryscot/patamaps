import subprocess,os,json,pathlib,hashlib,re
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';python='/opt/homebrew/bin/python3';cargo='/Users/admin/.cargo/bin/cargo'
commands=[('build',[cargo,'build','--locked','-p','patamaps-cli']),('clippy',[cargo,'clippy','--locked','--workspace','--all-targets','--','-D','warnings']),('native',[python,'-B','scripts/parity/native.py']),('installed-sdk',[python,'-B','scripts/parity/sdk_consumer.py']),('digest-controls',[node,'scripts/parity/digest_contracts.mjs']),('digest-utf16-controls',[node,'scripts/parity/digest_contracts.mjs','--utf16']),('composition-controls',[node,'scripts/parity/composition_contracts.mjs']),('graph-controls',[node,'scripts/parity/graph_contracts.mjs']),('factory-control',[node,str(out/'factory-check.mjs')]),('registry-controls',[node,'scripts/parity/registry_contracts.mjs']),('file-controls',[node,'scripts/parity/pack_contracts.mjs','--files']),('nested-controls',[node,'scripts/parity/pack_contracts.mjs','--nested']),('pack-controls',[node,'scripts/parity/pack_contracts.mjs']),('frozen-validation',[node,'scripts/parity/legacy_validation.mjs'])]
commands += [('original-'+name,[node,'scripts/parity/original.mjs']+([] if name=='canonical' else ['--'+name])) for name in ['canonical','sssom','discovery','sssom-adapter','validation','registry','graph','composition']]
commands += [('discovery-api',[python,'-B','scripts/parity/discovery_api.py']),('scientific-bounds',[python,'-B','scripts/parity/scientific_bounds.py'])]
prior=root/"docs/acceptance/parity/digest-functional-refresh-2026-10-12T20-59-53.294259+00-00/receipt.json"
prior_record=json.loads(prior.read_bytes())
assert prior_record['commands'][3]['label']=='installed-sdk' and prior_record['commands'][3]['exitCode']==1
assert all(row['exitCode']==0 for row in prior_record['commands'][:3])
assert json.loads(subprocess.check_output([root/'target/debug/patamaps','engine']))==prior_record['candidateEngine']
assert 'sha256:'+hashlib.sha256((root/'target/debug/patamaps').read_bytes()).hexdigest()==prior_record['binaryDigest']
rows=prior_record['commands'][:3];functional=[entry for entry in prior_record['functionalEvidence'] if '/native-' in entry['path']]
assert len(functional)==1
commands=commands[3:]
expected_rows=len(commands)+3
for row in rows:
 label=row['label']
 for stream in ['stdout','stderr']:
  (out/(label+'.'+stream+'.log')).write_bytes((prior.parent/(label+'.'+stream+'.log')).read_bytes())
 row['retainedCommandRun']=prior.relative_to(root).as_posix()

for label,command in commands:
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr:
  result=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 row={'label':label,'command':command,'exitCode':result.returncode};rows.append(row);print(label,result.returncode,flush=True)
 text=(out/(label+'.stdout.log')).read_text();found=[]
 for match in re.finditer(r'(?m)^\{',text):
  try:
   observed=json.JSONDecoder().raw_decode(text[match.start():])[0]
   if isinstance(observed,dict) and observed.get('receipt'):found.append(observed)
  except ValueError:pass
 assert len(found)<=1,(label,'ambiguous receipt')
 if found:
  receipt=root/found[0]['receipt'];raw=receipt.read_bytes();functional.append({'path':receipt.relative_to(root).as_posix(),'digest':'sha256:'+hashlib.sha256(raw).hexdigest()})
  if label.startswith('original-') and result.returncode==0:
   attach=[python,'-B','scripts/parity/verify.py','--record',str(receipt)]
   with (out/(label+'.attachment.stdout.log')).open('w') as stdout,(out/(label+'.attachment.stderr.log')).open('w') as stderr:
    attached=subprocess.run(attach,cwd=root,env=env,stdout=stdout,stderr=stderr)
   row['attachmentExitCode']=attached.returncode;print(label+' attachment',attached.returncode,flush=True)
 if result.returncode:break
binary=root/'target/debug/patamaps'
record={'schemaVersion':'1.0.0','status':'passed' if len(rows)==expected_rows and all(r['exitCode']==0 for r in rows) else 'failed','commands':rows,'functionalEvidence':functional,'binaryDigest':'sha256:'+hashlib.sha256(binary.read_bytes()).hexdigest(),'candidateEngine':json.loads(subprocess.check_output([binary,'engine'])),'reusedPassedBuildNativeRun':{'path':prior.relative_to(root).as_posix(),'digest':'sha256:'+hashlib.sha256(prior.read_bytes()).hexdigest()},'scope':'Current unchecked digest/UTF-16/composition/graph/registry/JSON/native/installed SDK/discovery/scientific components, including the source-bound native collator patch. Original callbacks and expectations remain unchanged. Complete accepted-domain/package/platform parity remains unresolved.'}
(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(out/'receipt.json',flush=True)
raise SystemExit(0 if record['status']=='passed' else 1)
