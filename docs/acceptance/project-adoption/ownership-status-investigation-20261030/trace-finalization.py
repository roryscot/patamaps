from pathlib import Path
import subprocess,json,time
B=Path(__file__).resolve().parent
start=time.monotonic()
try:
 p=subprocess.run(["/Users/admin/.nvm/versions/node/v22.23.3/bin/node",str(B/"trace-finalization.mjs")],capture_output=True,text=True,timeout=30)
 (B/"finalization.stdout.private").write_text(p.stdout);(B/"finalization.stderr.private").write_text(p.stderr)
 code=p.returncode;timed=False
except subprocess.TimeoutExpired as e:
 (B/"finalization.stdout.private").write_bytes(e.stdout or b"");(B/"finalization.stderr.private").write_bytes(e.stderr or b"")
 code=None;timed=True
rows=[json.loads(x)for x in(B/"finalization.stdout.private").read_text().splitlines()]
result=dict(readOnly=True,applicationExecuted=False,timeout=timed,exitCode=code,elapsedSeconds=time.monotonic()-start,stages=rows)
(B/"finalization-result.json").write_text(json.dumps(result,indent=2));print(json.dumps(result))
