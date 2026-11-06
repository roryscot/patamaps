"""CI-only unprivileged network/ownership prerequisite; no Cargo closure claim."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from project_watch import stop

ROOT = Path(__file__).resolve().parent.parent
PROBE = r'''
import errno,json,os,socket
assert [name for _,name in socket.if_nameindex()]==['lo']
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as external:
 try:external.connect(('192.0.2.1',9))
 except OSError as error:assert error.errno==errno.ENETUNREACH
 else:raise AssertionError('External route unexpectedly present')
with socket.socket() as server:
 server.bind(('127.0.0.1',0));server.listen(1)
 with socket.create_connection(server.getsockname(),timeout=2) as client:
  peer,_=server.accept()
  with peer:
   client.sendall(b'namespace-loopback');assert peer.recv(64)==b'namespace-loopback'
print(json.dumps(dict(interfaces=['lo'],externalRouteAbsent=True,loopbackTcpPassed=True,
 namespaceUid=os.geteuid(),uidMap=open('/proc/self/uid_map').read().split(),
 networkNamespace=os.readlink('/proc/self/ns/net'))))
'''
HOLD = r'''
import json,os,socket,sys,time
from pathlib import Path
assert [name for _,name in socket.if_nameindex()]==['lo']
server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1)
Path(sys.argv[1]).write_text(json.dumps(dict(pid=os.getpid(),group=os.getpgrp(),
 namespaceUid=os.geteuid(),uidMap=Path('/proc/self/uid_map').read_text().split())))
while True:time.sleep(.1)
'''
OWNER = r'''
import json,os,subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-B',sys.argv[1],'__guard',*sys.argv[3:]],start_new_session=True)
Path(sys.argv[2]).write_text(json.dumps(dict(owner=os.getpid(),guardian=child.pid)))
while True:time.sleep(.1)
'''


def identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        uid = next(line for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('Uid:')).split()[1]
        return dict(pid=pid, state=fields[0], parent=int(fields[1]), group=int(fields[2]), startTicks=int(fields[19]), hostUid=int(uid))
    except FileNotFoundError:
        return None


def running(pid):
    observed = identity(pid)
    return observed is not None and observed['state'] != 'Z'


def group_absent(group):
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Linux' and os.environ.get('GITHUB_ACTIONS') == 'true', 'Dedicated Linux CI required'
    out = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix='cargo-registry-network-', dir=os.environ['RUNNER_TEMP']))
    began = time.monotonic()
    baseline = shutil.disk_usage(ROOT).used
    report = dict(status='running', controls=[], sourceRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  applicationBuildRun=False, cargoRegistryClosureEstablished=False, completeDependencyClosure=False,
                  ownerTestContextClosed=False, parallelActivation=False, filesDeleted=0,
                  maximumGrowthBytes=33554432, minimumFreeBytes=500000000, maximumElapsedSeconds=60,
                  pythonVersion=sys.version,preflightScriptDigest='sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    owned = []
    streams = []
    live = []
    stage = 'tools'
    env = {k: os.environ[k] for k in ['PATH','LANG','TZ'] if k in os.environ}
    env.update(HOME=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')

    def save():
        (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')

    def capacity():
        disk = shutil.disk_usage(ROOT)
        assert disk.free >= 500000000 and disk.used-baseline <= 33554432, 'Preflight storage boundary'
        assert time.monotonic()-began < 60, 'Preflight deadline'
        assert all(handle.tell() < 65536 for handle in streams), 'Preflight log bound'

    def launch(label, argv):
        capacity()
        stdout, stderr = (work/(label+'.stdout')).open('xb'), (work/(label+'.stderr')).open('xb')
        streams.extend([stdout,stderr])
        child = subprocess.Popen(argv,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
        owned.append(child)
        return child

    def wait_for(predicate):
        deadline = time.monotonic()+10
        while not predicate():
            capacity()
            assert time.monotonic() < deadline, 'Owned process readiness/stop deadline'
            time.sleep(.05)

    def check_native(ready, guardian):
        data=json.loads(ready.read_text());observed=identity(data['pid'])
        assert observed and running(data['pid']) and observed['parent']==guardian
        assert observed['hostUid']==os.geteuid() and observed['group']==data['group']==data['pid']
        assert data['namespaceUid']==0 and list(map(int,data['uidMap']))==[0,os.geteuid(),1]
        assert os.readlink(f"/proc/{data['pid']}/ns/net")!=os.readlink('/proc/self/ns/net')
        live.append(observed)
        return data,observed

    def pass_control(name, **facts):
        report['controls'].append(dict(name=name,passed=True,**facts));save()

    save()
    try:
        assert os.geteuid() != 0, 'Host root is not an unprivileged ownership test'
        unshare, ip = shutil.which('unshare'), shutil.which('ip')
        assert unshare and ip, 'Required namespace tools unavailable'
        import shlex
        prefix=[unshare,'--user','--map-root-user','--net','/bin/sh','-ec',shlex.quote(ip)+' link set lo up; exec "$@"','cargo-registry-network']
        guardian=ROOT/'scripts/project_watch.py'
        report['tools']={str(path):'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in [unshare,ip,guardian]}
        report['hostUid']=os.geteuid()
        stage='network-and-loopback'
        child=launch('network-probe',[sys.executable,'-B',guardian,'__guard',*prefix,sys.executable,'-B','-c',PROBE])
        wait_for(lambda:child.poll() is not None)
        if child.returncode != 0:
            report['namespaceRefusal']=(work/'network-probe.stderr').read_text(errors='replace')[-2048:]
            raise RuntimeError('Unprivileged namespace probe refused')
        stop(child)
        facts=json.loads((work/'network-probe.stdout').read_text())
        assert facts['namespaceUid']==0 and list(map(int,facts['uidMap']))==[0,os.geteuid(),1]
        assert facts['networkNamespace']!=os.readlink('/proc/self/ns/net')
        pass_control(stage,**facts)

        stage='namespace-cancellation'
        ready=work/'cancel-ready.json'
        child=launch('cancel-owner',[sys.executable,'-B',guardian,'__guard',*prefix,sys.executable,'-B','-c',HOLD,ready])
        wait_for(ready.exists)
        data,observed=check_native(ready,child.pid)
        stop(child)
        wait_for(lambda:not running(data['pid']) and group_absent(data['group']))
        pass_control(stage,observedLive=observed,guardianExit=child.returncode,nativeProcessStopped=True,nativeGroupAbsent=True)

        stage='namespace-owner-sigkill'
        ready,owner_state=work/'crash-ready.json',work/'owner-state.json'
        child=launch('crash-owner',[sys.executable,'-B','-c',OWNER,guardian,owner_state,*prefix,sys.executable,'-B','-c',HOLD,ready])
        wait_for(lambda:ready.exists() and owner_state.exists())
        owner=json.loads(owner_state.read_text());assert owner['owner']==child.pid
        observed_guardian=identity(owner['guardian']);assert observed_guardian and observed_guardian['parent']==child.pid and observed_guardian['hostUid']==os.geteuid()
        data,observed=check_native(ready,owner['guardian'])
        child.kill();child.wait(timeout=5)
        wait_for(lambda:not running(data['pid']) and group_absent(data['group']) and not running(owner['guardian']))
        pass_control(stage,ownerExit=child.returncode,observedLive=observed,observedGuardian=observed_guardian,nativeProcessStopped=True,nativeGroupAbsent=True,guardianStopped=True)
        report['status']='passed-unprivileged-registry-network-preflight'
    except BaseException as error:
        report.update(status='failed',failedStage=stage,errorClass=type(error).__name__,error=str(error)[:512])
        raise
    finally:
        stopped=True
        for child in reversed(owned):
            try:
                if child.poll() is None:stop(child)
                elif not group_absent(child.pid):stopped=False
            except BaseException:stopped=False
        for process in live:
            current=identity(process['pid'])
            if current and current['state']!='Z':
                # Do not signal a PID whose original owner/identity is uncertain.
                stopped=False
            if not group_absent(process['group']):stopped=False
        for handle in streams:handle.close()
        report.update(ownedGuardiansStopped=stopped,ownedWorkloadStopped=stopped if live else None,elapsedMs=round((time.monotonic()-began)*1000),registryContextBuildAcceptance='not-run')
        save()
        assert stopped,'Owned namespace workload needs review'
    print(json.dumps(dict(status=report['status'],controls=len(report['controls']),cargoRegistryClosureEstablished=False)))


if __name__=='__main__':main()
