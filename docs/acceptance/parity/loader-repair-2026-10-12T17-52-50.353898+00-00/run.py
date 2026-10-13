from pathlib import Path
import json,subprocess,sys,hashlib
root=Path.cwd();out=Path(__file__).resolve().parent
commands=[('build',['/Users/admin/.cargo/bin/cargo','build','--locked','-p','patamaps-cli']),('file-controls',['/Users/admin/.nvm/versions/node/v22.16.0/bin/node','scripts/parity/pack_contracts.mjs','--files'])]
rows=[]
for name,command in commands:
 r=subprocess.run(command,capture_output=True,text=True);(out/(name+'.stdout.log')).write_text(r.stdout);(out/(name+'.stderr.log')).write_text(r.stderr);rows.append({'name':name,'command':command,'exitCode':r.returncode});print(name,r.returncode,r.stdout[-2200:],r.stderr[-2200:] if r.returncode else '',flush=True);(out/'receipt.json').write_text(json.dumps({'schemaVersion':'1.0.0','status':'in-progress' if r.returncode==0 else 'verification-failed','commands':rows,'fullParityAcceptance':False},indent=2)+'\n')
 if r.returncode:sys.exit(r.returncode)
d=json.loads((out/'receipt.json').read_text());d.update({'status':'component-checks-passed','binaryDigest':'sha256:'+hashlib.sha256((root/'target/debug/patamaps').read_bytes()).hexdigest()});(out/'receipt.json').write_text(json.dumps(d,indent=2)+'\n')
