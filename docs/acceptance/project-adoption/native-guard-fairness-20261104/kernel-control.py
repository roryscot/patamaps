from pathlib import Path
import sys,json,signal,os,time
E=Path('/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-candidate-parent-watch-20261104/engine')
sys.path.insert(0,str(E))
import native_inspection_guard as k
op=sys.argv[1];values=json.loads(sys.argv[2])
if op=='probe':
 print(json.dumps(dict(identities={str(p):k.process_identity(p)for p in values},groupsStopped={str(p):not k.group_live(p)for p in values})))
elif op=='stop':
 rows=[]
 for v in values:
  stopped=k.stop_registered(v,.2)
  rows.append(dict(pid=v['pid'],stopped=bool(stopped),groupStopped=not k.group_live(v['pid'])))
 print(json.dumps(rows))
else:raise RuntimeError('UNKNOWN_KERNEL_OPERATION')
