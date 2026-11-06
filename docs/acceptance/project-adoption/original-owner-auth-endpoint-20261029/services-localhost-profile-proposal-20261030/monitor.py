import subprocess,json,datetime,os
from pathlib import Path
w=Path(__file__).resolve().parent
config=json.loads((w/"launch-config.json").read_text())
env=dict(os.environ);env["PATH"]="/Users/admin/.nvm/versions/node/v22.23.3/bin:/Users/admin/.rustup/toolchains/1.99.0-x86_64-apple-darwin/bin:/usr/bin:/bin:/usr/sbin:/sbin"
with (w/"supervisor.stdout").open("xb") as out,(w/"supervisor.stderr").open("xb") as err:
 p=subprocess.Popen(config["argv"],cwd=config["cwd"],env=env,stdout=out,stderr=err)
 (w/"supervisor.json").write_text(json.dumps({"pid":p.pid,"startedAtUtc":datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 code=p.wait()
 (w/"supervisor-exit.json").write_text(json.dumps({"exitCode":code,"finishedAtUtc":datetime.datetime.now(datetime.timezone.utc).isoformat()}))
