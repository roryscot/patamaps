from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
ensure_guarded()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return 'sha256:'+h.hexdigest()
previous=ROOT/'docs/acceptance/capabilities/compiler-2026-10-15T02-01-50.627814Z/receipt.json'
old=json.loads(previous.read_bytes());assert old['status']=='passed'
for command in old['commands']:
    assert command['exitCode']==0
    for stream in ['stdout','stderr']:
        assert sha(ROOT/command[stream]['path'])==command[stream]['digest']
changed='scripts/test_lifecycle_pure.py'
differences=[x for x in old['sourceInventory'] if sha(ROOT/x['path'])!=x['digest']]
assert [x['path'] for x in differences]==[changed]
pointer=ROOT/'.tools/capabilities/current.json';state=json.loads(pointer.read_bytes())
installed=ROOT/state['installedReceipt'];assert sha(installed)==state['installedReceiptDigest']
i=json.loads(installed.read_bytes());assert i['status']=='passed' and i['engines']==old['engines']
cli=ROOT/i['retainedWork']/'installation/bin/patamaps'
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('compiler-lifecycle-refresh-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes());(out/'verified-lifecycle-driver.py').write_bytes((ROOT/changed).read_bytes())
work=Path(tempfile.mkdtemp(prefix='lifecycle-refresh-',dir=ROOT/'.tools/capabilities'))
argv=[sys.executable,'-B',str(ROOT/'scripts/capabilities/retained_driver.py'),'--retain-in',str(work),str(ROOT/changed),'--cli',str(cli),'--output',str(out/'lifecycle.json')]
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
env['SDKROOT']=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
report={'status':'running','scope':'Only the Python lifecycle verification fixture changed. Re-run that stage, verify every other compiler input remains byte-identical, and retain nine prior successful stage records as inherited evidence. Production Rust algorithms/executor identities are unchanged.','previousMilestone':previous.relative_to(ROOT).as_posix(),'previousMilestoneDigest':sha(previous),'changedVerificationInput':{'path':changed,'beforeDigest':differences[0]['digest'],'afterDigest':sha(ROOT/changed)},'retainedWork':work.relative_to(ROOT).as_posix(),'engines':i['engines'],'deleted':[]}
def save():(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
save()
try:
    with (out/'lifecycle.stdout.log').open('wb') as stdout,(out/'lifecycle.stderr.log').open('wb') as stderr:
        r=subprocess.run(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
    assert r.returncode==0,'inspect retained lifecycle logs'
    result=json.loads((out/'lifecycle.json').read_bytes())
    assert result['engines']==i['engines'] and result['originalCaptureUnchanged'] is True
    assert result['repairedNativeConsumption']=='Hello, Ada!' and result['repairedNativePath']=='/greet/42'
    assert result['repairedRuntimeNodeInPath'] is False
    for name in ['capture','repairedCapture']:
        p=out/(name+'.json');p.write_text(json.dumps(result[name],indent=2)+'\n')
        reply=subprocess.run([cli,'replay',p],env=env,capture_output=True)
        (out/(name+'.replay.stdout.log')).write_bytes(reply.stdout)
        (out/(name+'.replay.stderr.log')).write_bytes(reply.stderr)
        assert reply.returncode==0 and json.loads(reply.stdout)['status']=='verified'
    assert sha(ROOT/changed)==report['changedVerificationInput']['afterDigest']
    inventory=[{**x,'digest':sha(ROOT/x['path'])} for x in old['sourceInventory']]
    for a,b in zip(old['sourceInventory'],inventory,strict=True):
        assert a==b or a['path']==changed
    commands=[]
    for command in old['commands']:
        if command['label']=='lifecycle':
            commands.append({'label':'lifecycle','argv':argv,'exitCode':r.returncode,'execution':'fresh',**{stream:{'path':(out/('lifecycle.'+stream+'.log')).relative_to(ROOT).as_posix(),'digest':sha(out/('lifecycle.'+stream+'.log'))} for stream in ['stdout','stderr']}})
        else:
            commands.append({**command,'execution':'inherited-unchanged-inputs','fromMilestone':previous.relative_to(ROOT).as_posix()})
    report.update(status='passed',commands=commands,sourceInventory=inventory,sourceUnchanged=True,originalCaptureReplays=True,repairedCaptureReplays=True,repairedNativeConsumption='Hello, Ada!',repairedNativePath='/greet/42',completedAtUtc=datetime.now(timezone.utc).isoformat())
    save()
    backup=pointer.with_name('current.before-lifecycle-refresh-'+out.name+'.json')
    with backup.open('xb') as f:f.write(pointer.read_bytes())
    state.update(compilerReceipt=(out/'receipt.json').relative_to(ROOT).as_posix(),compilerReceiptDigest=sha(out/'receipt.json'),
        workingSource='Checked-tree emitter and test-only lifecycle evidence repair. All production package inputs remain unchanged; one Python verification fixture was strengthened after package installation.',
        postInstallationVerificationChanges=[report['changedVerificationInput']],previousPointer=backup.relative_to(ROOT).as_posix())
    pointer.write_text(json.dumps(state,indent=2)+'\n')
except BaseException as e:
    report.update(status='failed',error=type(e).__name__+': '+str(e));raise
finally:
    save();print(json.dumps({'status':report['status'],'receipt':str(out/'receipt.json')}),flush=True)
