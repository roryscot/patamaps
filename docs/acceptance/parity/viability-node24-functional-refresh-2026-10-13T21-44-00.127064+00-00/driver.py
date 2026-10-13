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
assert all(engine[k]==v for k,v in source_ids.items())
source_files=sorted(path for path in (root/'sdk/typescript').rglob('*') if path.is_file())+sorted((root/'scripts/parity').glob('*.py'))+sorted((root/'scripts/parity').glob('*.mjs'))
source_inventory=[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in source_files]
node=Path(config['nodeRuntime']);node_digest=sha(node.read_bytes());node_descriptor=json.loads(subprocess.check_output([node,'-p','JSON.stringify({version:process.version,uv:process.versions.uv,platform:process.platform,architecture:process.arch})']))
rows=[]
functional=[]
def save(status):
 record={'schemaVersion':'1.0.0','status':status,'commands':rows,'functionalEvidence':functional,'binaryDigest':binary_digest,'candidateEngine':engine,'sourceInventory':source_inventory,'scope':config['scope'],'reusedEvidence':[],'nodeRuntime':{'path':str(node),'digest':node_digest,**node_descriptor},'diagnosticOnlyPriorFailures':['docs/acceptance/parity/viability-signed-zero-functional-refresh-2026-10-13T20-39-08.658345+00-00/receipt.json','docs/acceptance/parity/viability-timeout-diagnostic-2026-10-13T21-31-04.553167+00-00/receipt.json','docs/acceptance/parity/viability-node-timeout-probe-2026-10-13T21-39-00.654866+00-00/receipt.json'],'driverDigest':sha(Path(__file__).read_bytes())}
 (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
save('running')
for case in config['commands']:
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
