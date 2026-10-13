import hashlib,json,os,re,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4];out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts/parity'));from storage_guard import ensure_guarded
ensure_guarded()
config=json.loads((out/'config.json').read_text());env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest();binary=root/'target/debug/patamaps';engine=json.loads(subprocess.check_output([binary,'engine']))
primary=root/config['reusedPrimaryCli'];p=json.loads(primary.read_text());assert p['status']=='matched' and p['candidate']['binaryDigest']==sha(binary.read_bytes()) and p['candidate']['engine']==engine
for item in p['candidate']['sourceInventory']:assert item['digest']==sha((root/item['path']).read_bytes()),item['path']
rows=[{'label':'build','command':['/Users/admin/.cargo/bin/cargo','build','--locked','-p','patamaps-cli'],'exitCode':0,'reusedGuardRecord':config['reusedBuildGuardRecord']},{'label':'cli-controls','exitCode':0,'reusedReceipt':config['reusedPrimaryCli']}]
functional=[{'path':config['reusedPrimaryCli'],'digest':sha(primary.read_bytes())}]
def save(status):
 record={'schemaVersion':'1.0.0','status':status,'commands':rows,'functionalEvidence':functional,'binaryDigest':sha(binary.read_bytes()),'candidateEngine':engine,'scope':'Current native and installed SDK/provider checks, unchanged original callback assertions, source-catalog migration and seven CLI workflows. Complete accepted-domain/package/platform parity remains unresolved.'}
 (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
for case in config['commands']:
 label,command=case['label'],case['command']
 with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr:result=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 row={'label':label,'command':command,'exitCode':result.returncode};rows.append(row);print(label,result.returncode,flush=True)
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
   with (out/(label+'.attachment.stdout.log')).open('w') as stdout,(out/(label+'.attachment.stderr.log')).open('w') as stderr:attached=subprocess.run(['/opt/homebrew/bin/python3','-B','scripts/parity/verify.py','--record',str(receipt)],cwd=root,env=env,stdout=stdout,stderr=stderr)
   row['attachmentExitCode']=attached.returncode
   ledger=json.loads((out/(label+'.attachment.stdout.log')).read_text());ids={v['id'] for v in json.loads(receipt.read_text())['obligations']};row['attachedObligationsVerified']=not any(v['id'] in ids for v in ledger['invalidEvidence']);assert row['attachedObligationsVerified'],label
 save('running' if not result.returncode else 'failed')
 if result.returncode:print(out/'receipt.json',flush=True);raise SystemExit(result.returncode)
save('passed');print(out/'receipt.json',flush=True)
