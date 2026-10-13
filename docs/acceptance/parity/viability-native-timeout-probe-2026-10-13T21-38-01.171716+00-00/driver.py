import pathlib,json,subprocess,time,hashlib,os
root=pathlib.Path('/Users/admin/dev/patamaps/patamaps'); out=pathlib.Path(__file__).parent; prior=root/'docs/acceptance/parity/viability-timeout-diagnostic-2026-10-13T21-31-04.553167+00-00'
command=json.loads((prior/'failed-native-command.json').read_text()); raw=(prior/'failed-native-input.json').read_bytes(); rows=[]
for mode in ['pipe','file']:
 start=time.monotonic()
 if mode=='file':
  stream=(prior/'failed-native-input.json').open('rb')
 else: stream=subprocess.PIPE
 child=subprocess.Popen(command,stdin=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={})
 (out/'live.json').write_text(json.dumps({'mode':mode,'pid':child.pid,'startedAt':time.time()}))
 try:
  stdout,stderr=child.communicate(raw if mode=='pipe' else None,timeout=65); status='completed'
 except subprocess.TimeoutExpired:
  child.terminate(); stdout,stderr=child.communicate(timeout=15); status='timed-out'
 if mode=='file': stream.close()
 (out/(mode+'.stdout')).write_bytes(stdout); (out/(mode+'.stderr')).write_bytes(stderr)
 row={'mode':mode,'status':status,'exitCode':child.returncode,'elapsedSeconds':time.monotonic()-start,'stdoutBytes':len(stdout),'stderrBytes':len(stderr)}; rows.append(row); print(json.dumps(row),flush=True)
receipt={'scope':'Exact previously timed-out input; diagnostic pipe/file transport comparison only','command':command,'inputDigest':'sha256:'+hashlib.sha256(raw).hexdigest(),'inputBytes':len(raw),'binaryDigest':'sha256:'+hashlib.sha256(pathlib.Path(command[0]).read_bytes()).hexdigest(),'rows':rows}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps({'receipt':str(out/'receipt.json')}),flush=True)
raise SystemExit(0 if all(r['status']=='completed' and r['exitCode']==0 for r in rows) else 1)
