import hashlib,json,os,re,subprocess,sys
from pathlib import Path
root=Path.cwd();out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
config=json.loads((out/'config.json').read_text())
env={**os.environ,'PATAMAPS_PARITY_NODE':config['nodeRuntime'],'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
binary=root/'target/debug/patamaps';binary_digest=sha(binary.read_bytes())
engine=json.loads(subprocess.check_output([binary,'engine']));source_ids=identities(root)

source_files=sorted(path for path in (root/'sdk/typescript').rglob('*') if path.is_file())+sorted((root/'scripts/parity').glob('*.py'))+sorted((root/'scripts/parity').glob('*.mjs'))
source_inventory=[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in source_files]
node=Path(config['nodeRuntime']);node_digest=sha(node.read_bytes());node_descriptor=json.loads(subprocess.check_output([node,'-p','JSON.stringify({version:process.version,uv:process.versions.uv,platform:process.platform,architecture:process.arch})']))
with (out/'build.stdout.log').open('x') as stdout,(out/'build.stderr.log').open('x') as stderr:
 built=subprocess.run(['/Users/admin/.cargo/bin/cargo','build','--locked','-p','patamaps-cli'],cwd=root,env=env,stdout=stdout,stderr=stderr)
assert built.returncode==0
binary_digest=sha(binary.read_bytes());engine=json.loads(subprocess.check_output([binary,'engine']));assert all(engine[k]==v for k,v in identities(root).items())
rows=[]
functional=[]
reused=[]
if config.get('resumeFromSameProductionCandidate'):
 prior_path=root/config['resumeFromSameProductionCandidate'];prior=json.loads(prior_path.read_text())
 assert prior['status']=='failed' and len(prior['commands'])==13 and prior['commands'][-1]['label']=='installed-sdk' and prior['commands'][-1]['exitCode']==1
 assert prior['binaryDigest']==binary_digest and prior['candidateEngine']==engine and prior['nodeRuntime']['digest']==node_digest and prior['nodeRuntime']['path']==str(node)
 before={r['path']:r['digest'] for r in prior['sourceInventory']};after={r['path']:r['digest'] for r in source_inventory};assert before.keys()==after.keys()
 differences=[path for path in before if before[path]!=after[path]];assert differences==['scripts/parity/sdk_consumer.py']
 fix=config['positiveFixtureCorrection'];original=(root/fix['beforeSource']).read_bytes();current=(root/differences[0]).read_bytes()
 assert sha(original)==fix['beforeDigest']==before[differences[0]] and sha(current)==fix['afterDigest']==after[differences[0]]
 assert original.count(fix['oldLine'].encode())==1 and current==original.replace(fix['oldLine'].encode(),fix['newLine'].encode())
 rows=prior['commands'][:-1];assert len(rows)==12 and all(r['exitCode']==0 for r in rows)
 for index,row in enumerate(rows):assert row['command']==config['commands'][index]['command'] and row['label']==config['commands'][index]['label']
 functional=[r for r in prior['functionalEvidence'] if r['path']!='docs/acceptance/parity/sdk-consumer-2026-10-14T00-47-29.107098Z/receipt.json']
 for receipt in functional:assert sha((root/receipt['path']).read_bytes())==receipt['digest']
 reused=[{'path':prior_path.relative_to(root).as_posix(),'digest':sha(prior_path.read_bytes()),'checks':12,'sameProductionBinarySdkAndNodeVerified':True,'isolatedConsumerFixtureDifferenceVerified':True,'correction':fix}]

def save(status):
 record={'schemaVersion':'1.0.0','status':status,'commands':rows,'functionalEvidence':functional,'binaryDigest':binary_digest,'candidateEngine':engine,'sourceInventory':source_inventory,'scope':config['scope'],'reusedEvidence':reused,'nodeRuntime':{'path':str(node),'digest':node_digest,**node_descriptor},'diagnosticOnlyPriorFailures':['docs/acceptance/parity/viability-signed-zero-functional-refresh-2026-10-13T20-39-08.658345+00-00/receipt.json','docs/acceptance/parity/viability-timeout-diagnostic-2026-10-13T21-31-04.553167+00-00/receipt.json','docs/acceptance/parity/viability-node-timeout-probe-2026-10-13T21-39-00.654866+00-00/receipt.json'],'driverDigest':sha(Path(__file__).read_bytes())}
 (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
save('running')
for case in config['commands'][len(rows):]:
 label,command=case['label'],case['command']
 print('Starting '+label,flush=True)
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr:
  result=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 row={'label':label,'command':command,'exitCode':result.returncode};rows.append(row)
 print(label+' '+str(result.returncode),flush=True)
 stdout=(out/(label+'.stdout.log')).read_text();found=[]
 for match in re.finditer(r'(?m)^\{',stdout):
  try:
   value=json.JSONDecoder().raw_decode(stdout[match.start():])[0]
   if isinstance(value,dict) and value.get('receipt'):found.append(value)
  except ValueError:pass
 assert len(found)<=1,(label,'ambiguous receipt')
 if found:
  receipt=root/found[0]['receipt'];functional.append({'path':receipt.relative_to(root).as_posix(),'digest':sha(receipt.read_bytes())})
  if label.startswith('original-') and result.returncode==0:
   with (out/(label+'.attachment.stdout.log')).open('w') as stdout,(out/(label+'.attachment.stderr.log')).open('w') as stderr:
    attached=subprocess.run(['/opt/homebrew/bin/python3','-B','scripts/parity/verify.py','--record',str(receipt)],cwd=root,env=env,stdout=stdout,stderr=stderr)
   row['attachmentExitCode']=attached.returncode
   attachment_text=(out/(label+'.attachment.stdout.log')).read_text()
   if not attachment_text.strip():
    row['attachmentFailure']='Verifier produced no structured result; retained stderr gives the cause';save('evidence-attachment-failed');raise AssertionError(label)
   ledger=json.loads(attachment_text);ids={v['id'] for v in json.loads(receipt.read_text())['obligations']}
   row['attachedObligationsVerified']=not any(v['id'] in ids for v in ledger['invalidEvidence'])
   if not row['attachedObligationsVerified']:save('evidence-attachment-failed');raise AssertionError(label)
 save('running' if not result.returncode else 'failed')
 if result.returncode:print(out/'receipt.json',flush=True);raise SystemExit(result.returncode)
assert sha(node.read_bytes())==node_digest
assert sha(binary.read_bytes())==binary_digest
assert all(engine[k]==v for k,v in identities(root).items())
assert all(sha((root/f['path']).read_bytes())==f['digest'] for f in source_inventory)
save('passed');print(out/'receipt.json',flush=True)
