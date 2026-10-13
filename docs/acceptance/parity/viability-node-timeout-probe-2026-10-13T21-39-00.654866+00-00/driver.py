import pathlib,subprocess,json,sys
out=pathlib.Path(__file__).parent; rows=[]
for label,node in [('node22','/Users/admin/.nvm/versions/node/v22.16.0/bin/node'),('node24','/Users/admin/.nvm/versions/node/v24.21.0/bin/node')]:
 result=subprocess.run([node,str(out/'probe.mjs'),label]);rows.append({'label':label,'exitCode':result.returncode})
(out/'receipt.json').write_text(json.dumps({'scope':'Exact-input runtime/process diagnostic only; unchanged timeout/buffer limits','commands':rows},indent=2)+'\n'); print(str(out/'receipt.json'),flush=True)
raise SystemExit(any(r['exitCode'] for r in rows))
