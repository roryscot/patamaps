from pathlib import Path
import os,stat,json,time
B=Path(__file__).resolve().parent;root=Path("/Users/admin/Documents/Codex/.storage-control/heavy-builds/scheduler/requests");start=time.monotonic()
rows=[e.stat(follow_symlinks=False)for e in os.scandir(root)if e.name.endswith(".json")]
result=dict(requestFiles=len(rows),logicalBytes=sum(s.st_size for s in rows),nonregular=sum(not stat.S_ISREG(s.st_mode)for s in rows),elapsedSeconds=time.monotonic()-start,readOnly=True)
(B/"request-metadata.json").write_text(json.dumps(result,indent=2));print(json.dumps(result))
