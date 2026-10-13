from pathlib import Path
import os,json,subprocess,sys,hashlib
root=Path.cwd(); out=Path(__file__).resolve().parent
commands=[('build',['/Users/admin/.cargo/bin/cargo','build','--locked','-p','patamaps-cli']),('focused-native',['/Users/admin/.cargo/bin/cargo','test','--locked','-p','patamaps-core','--test','legacy_pack']),('nested-controls',['/Users/admin/.nvm/versions/node/v22.16.0/bin/node','scripts/parity/pack_contracts.mjs','--nested'])]
rows=[]
for name,command in commands:
 r=subprocess.run(command,capture_output=True,text=True); (out/(name+'.stdout.log')).write_text(r.stdout);(out/(name+'.stderr.log')).write_text(r.stderr);rows.append({'name':name,'command':command,'exitCode':r.returncode});print(name,r.returncode,r.stdout[-1400:] if r.returncode else r.stdout[-650:],r.stderr[-1000:] if r.returncode else '',flush=True)
 (out/'receipt.json').write_text(json.dumps({'schemaVersion':'1.0.0','status':'in-progress' if r.returncode==0 else 'verification-failed','commands':rows,'scope':'Supervised native build and original frozen nested pack comparison; full parity remains open.'},indent=2)+'\n')
 if r.returncode: sys.exit(r.returncode)
record=json.loads((out/'receipt.json').read_text());record['status']='component-checks-passed';record['binaryDigest']='sha256:'+hashlib.sha256((root/'target/debug/patamaps').read_bytes()).hexdigest();(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
