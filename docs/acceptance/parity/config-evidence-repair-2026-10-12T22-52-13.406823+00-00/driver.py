import pathlib,subprocess,json,hashlib
r=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
entry=json.loads((out/'input.json').read_text());command=['/opt/homebrew/bin/python3','-B','scripts/parity/verify.py','--record',str(r/entry['path'])]
result=subprocess.run(command,cwd=r,text=True,capture_output=True);(out/'stdout.log').write_text(result.stdout);(out/'stderr.log').write_text(result.stderr)
record={'schemaVersion':'1.0.0','status':'passed' if result.returncode==0 else 'failed','command':command,'exitCode':result.returncode,'component':entry,'failedVerifierDigest':'sha256:'+hashlib.sha256((out/'failed-verifier.py').read_bytes()).hexdigest(),'repairedVerifierDigest':'sha256:'+hashlib.sha256((r/'scripts/parity/verify.py').read_bytes()).hexdigest(),'reason':'Correct observation cardinality: each of the three unchanged config callbacks invokes the parser twice. The new verifier accidentally asserted one after correcting nonzero refusal exit codes from 2 to 1. Original tests, inputs, expectations and implementation are unchanged.'}
(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2));raise SystemExit(result.returncode)
