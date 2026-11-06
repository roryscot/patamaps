from pathlib import Path
import subprocess,json,os
b=Path(__file__).resolve().parent
with (b/'driver.stdout').open('xb') as out,(b/'driver.stderr').open('xb') as err:
 p=subprocess.Popen(['/Users/admin/.nvm/versions/node/v22.23.3/bin/node',str(b/'pilot.mjs')],env=dict(os.environ),stdout=out,stderr=err,start_new_session=True)
 record=b/'owner-process.staged.json'
 with record.open('x') as output:json.dump(dict(ownerPid=os.getpid(),ownerParentPid=os.getppid(),childPid=p.pid,childGroup=os.getpgid(p.pid)),output)
 assert not (b/'owner-process.json').exists()
 record.rename(b/'owner-process.json')
 raise SystemExit(p.wait())
