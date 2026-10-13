import json,pathlib,subprocess,time,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts/parity'));from storage_guard import ensure_guarded
ensure_guarded()
command=[str(root/'target/debug/patamaps'),'legacy','workspace','json'];start=time.monotonic()
try:
 r=subprocess.run(command,input=(out/'timed-out-request.json').read_bytes(),capture_output=True,timeout=65,env={})
 (out/'replay.stdout.log').write_bytes(r.stdout);(out/'replay.stderr.log').write_bytes(r.stderr)
 result={'command':command,'exitCode':r.returncode,'durationSeconds':time.monotonic()-start,'stdoutBytes':len(r.stdout),'stderrBytes':len(r.stderr)}
except subprocess.TimeoutExpired as e:
 (out/'replay.stdout.log').write_bytes(e.stdout or b'');(out/'replay.stderr.log').write_bytes(e.stderr or b'')
 result={'command':command,'timedOut':True,'durationSeconds':time.monotonic()-start}
(out/'replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
