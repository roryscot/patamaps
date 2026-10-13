import subprocess,os,json,pathlib,hashlib,re
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';python='/opt/homebrew/bin/python3';cargo='/Users/admin/.cargo/bin/cargo'
commands=[('build',[cargo,'build','--locked','-p','patamaps-cli']),('clippy',[cargo,'clippy','--locked','--workspace','--all-targets','--','-D','warnings']),('native',[python,'-B','scripts/parity/native.py']),('installed-sdk',[python,'-B','scripts/parity/sdk_consumer.py']),('config-controls',[node,'scripts/parity/config_contracts.mjs']),('correspondence-controls',[node,'scripts/parity/correspondence_contracts.mjs']),('reference-controls',[node,'scripts/parity/reference_contracts.mjs']),('reporting-controls',[node,'scripts/parity/reporting_contracts.mjs']),('digest-controls',[node,'scripts/parity/digest_contracts.mjs']),('digest-utf16-controls',[node,'scripts/parity/digest_contracts.mjs','--utf16']),('composition-controls',[node,'scripts/parity/composition_contracts.mjs']),('graph-controls',[node,'scripts/parity/graph_contracts.mjs']),('factory-control',[node,str(out/'factory-check.mjs')]),('registry-controls',[node,'scripts/parity/registry_contracts.mjs']),('file-controls',[node,'scripts/parity/pack_contracts.mjs','--files']),('nested-controls',[node,'scripts/parity/pack_contracts.mjs','--nested']),('pack-controls',[node,'scripts/parity/pack_contracts.mjs']),('frozen-validation',[node,'scripts/parity/legacy_validation.mjs'])]
commands += [('original-'+name,[node,'scripts/parity/original.mjs']+([] if name=='canonical' else ['--'+name])) for name in ['canonical','sssom','discovery','sssom-adapter','validation','registry','graph','composition','reporting','correspondence','config','workspace','adapter-registry']]
commands += [('workspace-controls',[node,'scripts/parity/workspace_contracts.mjs']),('workspace-workflow',[python,'-B','scripts/parity/workspace_workflow.py'])]
commands += [('discovery-api',[python,'-B','scripts/parity/discovery_api.py']),('scientific-bounds',[python,'-B','scripts/parity/scientific_bounds.py'])]
rows=[{'label': 'build', 'command': ['/Users/admin/.cargo/bin/cargo', 'build', '--locked', '-p', 'patamaps-cli'], 'exitCode': 0}, {'label': 'clippy', 'command': ['/Users/admin/.cargo/bin/cargo', 'clippy', '--locked', '--workspace', '--all-targets', '--', '-D', 'warnings'], 'exitCode': 0}, {'label': 'native', 'command': ['/opt/homebrew/bin/python3', '-B', 'scripts/parity/native.py'], 'exitCode': 0}, {'label': 'installed-sdk', 'command': ['/opt/homebrew/bin/python3', '-B', 'scripts/parity/sdk_consumer.py'], 'exitCode': 0, 'reusedReceipt': 'docs/acceptance/parity/sdk-consumer-2026-10-12T23-22-55.960374Z/receipt.json', 'reusedReceiptDigest': 'sha256:94a3c0352ed48895d0881244c976cb46592a8c095f228ca85a8894ccaed26328'}]
functional=[{'path': 'docs/acceptance/parity/native-2026-10-12T23-21-14.540265Z/receipt.json', 'digest': 'sha256:11f12147e5edf3e2fe31de12845f8c820dcb4c1e80ebd2ebaa5f7d377f60ee00'}, {'path': 'docs/acceptance/parity/sdk-consumer-2026-10-12T23-22-55.960374Z/receipt.json', 'digest': 'sha256:94a3c0352ed48895d0881244c976cb46592a8c095f228ca85a8894ccaed26328'}]
reusedEvidence=[{'path': 'docs/acceptance/parity/workspace-functional-refresh-2026-10-12T23-20-50.998726+00-00/receipt.json', 'digest': 'sha256:d039d1a2650e72188e1913239268ede129abe06cab1cadfb4b7bfa60fbaa6b9b'}, {'path': 'docs/acceptance/parity/sdk-consumer-2026-10-12T23-22-55.960374Z/receipt.json', 'digest': 'sha256:94a3c0352ed48895d0881244c976cb46592a8c095f228ca85a8894ccaed26328'}]
for label,command in commands[4:]:
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
 if result.returncode or row.get('attachmentExitCode',0):break
binary=root/'target/debug/patamaps'
record={'schemaVersion':'1.0.0','status':'passed' if len(rows)==len(commands) and all(r['exitCode']==0 and r.get('attachmentExitCode',0)==0 for r in rows) else 'failed','commands':rows,'functionalEvidence':functional,'reusedEvidence':reusedEvidence,'binaryDigest':'sha256:'+hashlib.sha256(binary.read_bytes()).hexdigest(),'candidateEngine':json.loads(subprocess.check_output([binary,'engine'])),'scope':'Current workspace/cache/outputs/custom-adapter/configuration parsing/loading/correspondence/reference/reporting/diff/digest/UTF-16/composition/graph/registry/JSON/native/installed SDK/discovery/scientific components, including the source-bound native collator patch. Original callbacks and expectations remain unchanged. Complete accepted-domain/package/platform parity remains unresolved.'}
(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(out/'receipt.json',flush=True)
raise SystemExit(0 if record['status']=='passed' else 1)
