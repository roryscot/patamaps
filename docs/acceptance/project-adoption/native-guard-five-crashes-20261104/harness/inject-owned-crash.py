import sys,json,os,signal
assert len(sys.argv)==3
sys.path.insert(0,sys.argv[1])
import native_inspection_guard as guard
identity=json.loads(sys.argv[2])
assert isinstance(identity,dict) and set(identity)=={'pid','parentPid','pgid','startSeconds','startMicroseconds'}
assert identity['pid']==identity['pgid'] and identity['pid']>1
assert guard.process_identity(identity['pid'])==identity,'OWNED_CRASH_IDENTITY_CHANGED'
os.kill(identity['pid'],signal.SIGKILL)
print(json.dumps(dict(ownedCrashIssued=True,signal='SIGKILL',pid=identity['pid'])))
