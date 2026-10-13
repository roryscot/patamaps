from pathlib import Path
import subprocess,sys,json,hashlib,os
root=Path.cwd();out=Path(__file__).resolve().parent
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node'
commands=[('clippy',['/Users/admin/.cargo/bin/cargo','clippy','--workspace','--all-targets','--locked','--','-D','warnings']),('native',[sys.executable,'-B','scripts/parity/native.py']),('installed-sdk',[sys.executable,'-B','scripts/parity/sdk_consumer.py']),('pack-controls',[node,'scripts/parity/pack_contracts.mjs']),('frozen-validation',[node,'scripts/parity/legacy_validation.mjs'])]+[(name,[node,'scripts/parity/original.mjs']+args) for name,args in [('original-canonical',[]),('original-sssom',['--sssom']),('original-discovery',['--discovery']),('original-sssom-adapter',['--sssom-adapter']),('original-validation',['--validation']),('original-packs',['--packs'])]]+[('discovery-api',[sys.executable,'-B','scripts/parity/discovery_api.py']),('scientific-bounds',[sys.executable,'-B','scripts/parity/scientific_bounds.py'])]
rows=[]
for name,command in commands:
 with (out/(name+'.stdout.log')).open('w') as stdout,(out/(name+'.stderr.log')).open('w') as stderr:
  r=subprocess.run(command,stdout=stdout,stderr=stderr)
 rows.append({'name':name,'command':command,'exitCode':r.returncode});print(name,r.returncode,flush=True)
 (out/'receipt.json').write_text(json.dumps({'schemaVersion':'1.0.0','status':'in-progress' if r.returncode==0 else 'verification-failed','commands':rows,'scope':'Current supervised portable/installed/components and exact original case evidence; no complete parity gate closes.'},indent=2)+'\n')
 if r.returncode:
  print((out/(name+'.stdout.log')).read_text()[-4000:]);print((out/(name+'.stderr.log')).read_text()[-4000:]);sys.exit(r.returncode)
for name in ['original-canonical','original-sssom','original-discovery','original-sssom-adapter','original-validation','original-packs']:
 raw=(out/(name+'.stdout.log')).read_text(); start=raw.find('{');d=json.loads(raw[start:]); receipt=root/d['receipt'];command=[sys.executable,'-B','scripts/parity/verify.py','--record',str(receipt)]
 r=subprocess.run(command,capture_output=True,text=True);(out/(name+'.attachment.stdout.log')).write_text(r.stdout);(out/(name+'.attachment.stderr.log')).write_text(r.stderr);report=json.loads(r.stdout);(out/(name+'.attachment.json')).write_text(json.dumps({'command':command,'exitCode':r.returncode,'report':report},indent=2)+'\n');print(name,'attached',report['currentVerifiedEquivalent'],'invalid',len(report['invalidEvidence']),flush=True)
 assert all(row['error']=='Candidate evidence is stale' for row in report['invalidEvidence']),report
assert report['currentVerifiedEquivalent']==87 and not report['invalidEvidence'],report
record=json.loads((out/'receipt.json').read_text());record.update({'status':'component-checks-passed','binaryDigest':'sha256:'+hashlib.sha256((root/'target/debug/patamaps').read_bytes()).hexdigest(),'ledger':report});(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
