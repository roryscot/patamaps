"""CI-only managed network/quotas/ownership prerequisite; no Cargo build claim."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from deployment_miniserve_image import stop_owned
from project_watch import stop
from project_watch_guard_controls import verify, verify_exits

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'busybox@sha256:dc88b80842580654294472735332ec7c7789a4010ec9a68b69f9b88c19abede6'
PROBE = r'''
set -eu
test "$(ls /sys/class/net)" = lo
if ip route get 192.0.2.1 >/dev/null 2>&1; then exit 71; fi
test "$(cat /sys/fs/cgroup/cpu.max)" = '50000 100000'
test "$(cat /sys/fs/cgroup/memory.max)" = 67108864
test "$(cat /sys/fs/cgroup/memory.swap.max)" = 0
test "$(cat /sys/fs/cgroup/pids.max)" = 32
test "$(id -u):$(id -g)" = 65532:65532
printf 'patamaps-loopback\n' >/tmp/index.html
httpd -f -p 127.0.0.1:19090 -h /tmp &
server=$!
trap 'kill "$server"; wait "$server" || true' EXIT
for attempt in 1 2 3 4 5; do
 if wget -q -T 1 -O /tmp/observed http://127.0.0.1:19090/; then break; fi
 sleep .1
done
test "$(cat /tmp/observed)" = patamaps-loopback
kill "$server"; wait "$server" || true
trap - EXIT
if dd if=/dev/zero of=/tmp/quota bs=65536 count=32 2>/tmp/quota-error; then exit 72; fi
bytes=$(stat -c %s /tmp/quota)
test "$bytes" -gt 0; test "$bytes" -lt 2097152
test "$(df -k /tmp | tail -1 | awk '{print $2}')" = 1024
printf 'LOOPBACK_AND_LIMITS_PASSED\nQUOTA_BYTES=%s\n' "$bytes"
'''
HOLD = "trap '' TERM INT HUP; echo OWNED_READY; while :; do sleep 1; done"
OWNER = r'''
import json,os,subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-B',sys.argv[1],'__guard-container',sys.argv[3]],start_new_session=True)
Path(sys.argv[2]).write_text(json.dumps(dict(owner=os.getpid(),guardian=child.pid)))
while True:time.sleep(.1)
'''


def identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        return dict(pid=pid, state=fields[0], parent=int(fields[1]),
                    group=int(fields[2]), startTicks=int(fields[19]))
    except FileNotFoundError:
        return None


def running(pid):
    value = identity(pid)
    return value is not None and value['state'] != 'Z'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Linux' and os.environ.get('GITHUB_ACTIONS') == 'true', 'Dedicated Linux CI required'
    out = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix='cargo-registry-container-', dir=os.environ['RUNNER_TEMP']))
    began, baseline = time.monotonic(), shutil.disk_usage(ROOT).used
    report = dict(status='running', controls=[],
                  sourceRevision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  applicationBuildRun=False, cargoRegistryClosureEstablished=False, completeDependencyClosure=False,
                  ownerTestContextClosed=False, parallelActivation=False, filesDeleted=0,
                  maximumGrowthBytes=33554432, minimumFreeBytes=500000000, maximumElapsedSeconds=60,
                  image=IMAGE, pythonVersion=sys.version)
    report['sourceDigests'] = {str(p.relative_to(ROOT)): 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [Path(__file__), ROOT/'scripts/project_watch.py',
                                        ROOT/'scripts/project_watch_guard_controls.py',
                                        ROOT/'scripts/deployment_miniserve_image.py']}
    token = uuid.uuid4().hex
    owned = dict(token=token, containers=[], filesDeleted=0)
    owned_path = out/'owned.json'
    processes, streams = [], []
    stage = 'tools'
    env = {key: os.environ[key] for key in ['PATH', 'LANG', 'TZ'] if key in os.environ}
    env.update(HOME=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    guardian = ROOT/'scripts/project_watch.py'

    def write(path, value):
        path.write_text(json.dumps(value, indent=2)+'\n')

    def save():
        write(out/'receipt.json', report)

    def capacity():
        disk = shutil.disk_usage(ROOT)
        assert disk.free >= 500000000 and disk.used-baseline <= 33554432, 'Preflight storage boundary'
        assert time.monotonic()-began < 60, 'Preflight deadline'
        assert all(p.stat().st_size < 65536 for p in work.glob('*.log')), 'Preflight log bound'

    def run(argv, timeout=10):
        capacity()
        result = subprocess.run([str(x) for x in argv], cwd=work, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        assert len(result.stdout) < 65536 and len(result.stderr) < 65536, 'Command output bound'
        if result.returncode:
            raise RuntimeError('Command refused: '+str(argv[:3])+' '+result.stderr[-1024:])
        return result.stdout

    def inspect(container):
        return json.loads(run(['docker', 'inspect', container]))[0]

    def wait_for(predicate):
        deadline = time.monotonic()+10
        while not predicate():
            capacity()
            assert time.monotonic() < deadline, 'Owned readiness/stop deadline'
            time.sleep(.05)

    def launch(label, argv):
        capacity()
        stdout, stderr = (work/(label+'.stdout.log')).open('xb'), (work/(label+'.stderr.log')).open('xb')
        streams.extend([stdout, stderr])
        child = subprocess.Popen([str(x) for x in argv], cwd=work, env=env, stdin=subprocess.DEVNULL,
                                 stdout=stdout, stderr=stderr, start_new_session=True)
        processes.append(child)
        return child

    def create(label, command):
        container = run(['docker', 'create', '--name', 'patamaps-registry-'+token+'-'+label,
                         '--label', 'org.patamaps.qualification-owner='+token, '--platform', 'linux/amd64',
                         '--network', 'none', '--read-only', '--user', '65532:65532',
                         '--cpus', '.5', '--memory', '67108864', '--memory-swap', '67108864',
                         '--pids-limit', '32', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                         '--shm-size', '1048576', '--tmpfs', '/tmp:rw,noexec,nosuid,size=1048576,mode=1777',
                         '--entrypoint', '/bin/sh', image_id, '-ec', command]).strip()
        assert re.fullmatch('[0-9a-f]{64}', container)
        owned['containers'].append(dict(id=container, label=label, confirmedStopped=False))
        write(owned_path, owned)
        info = inspect(container)
        host, config, state = info['HostConfig'], info['Config'], info['State']
        assert info['Image'] == image_id and config['User'] == '65532:65532'
        assert config['Labels']['org.patamaps.qualification-owner'] == token
        assert config['Entrypoint'] == ['/bin/sh'] and config['Cmd'] == ['-ec', command]
        assert host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] and not host['Binds']
        assert host['NanoCpus'] == 500000000 and host['Memory'] == host['MemorySwap'] == 67108864
        assert host['PidsLimit'] == 32 and host['ShmSize'] == 1048576
        assert host['CapDrop'] == ['ALL'] and not host['CapAdd'] and not host['Privileged']
        assert host['SecurityOpt'] == ['no-new-privileges']
        assert host['Tmpfs'] == {'/tmp': 'rw,noexec,nosuid,size=1048576,mode=1777'}
        assert not state['Running'] and state['Status'] == 'created' and state['StartedAt'].startswith('0001-')
        assert not [mount for mount in info['Mounts'] if mount['Type'] == 'bind']
        path = work/(label+'-owned.json')
        write(path, dict(token=token, containers=[dict(id=container)]))
        return container, path

    def stopped(container, path=None):
        state = inspect(container)['State']
        if state['Running'] or state['Pid'] != 0:
            return False
        return path is None or json.loads(path.read_text())['containers'][0].get('confirmedStopped') is True

    def ready(container, label):
        state = inspect(container)['State']
        return state['Running'] and state['Pid'] > 0 and 'OWNED_READY' in (work/(label+'.stdout.log')).read_text()

    def passed(name, **facts):
        report['controls'].append(dict(name=name, passed=True, **facts))
        save()

    write(owned_path, owned)
    save()
    try:
        assert shutil.which('docker'), 'Docker unavailable'
        stage = 'ordinary-guardian-regressions'
        groups = verify(guardian, work/'ordinary-groups')
        exits = verify_exits(guardian, work/'ordinary-exits')
        passed(stage, groupControl=groups, exitControl=exits)
        stage = 'immutable-image'
        run(['docker', 'pull', '--platform', 'linux/amd64', IMAGE], timeout=20)
        image = json.loads(run(['docker', 'image', 'inspect', IMAGE]))[0]
        image_id = image['Id']
        assert IMAGE in image['RepoDigests'] and (image['Os'], image['Architecture']) == ('linux', 'amd64')
        assert image['Size'] < 10000000
        report.update(imageId=image_id, imageBytes=image['Size'])
        passed(stage, repoDigests=image['RepoDigests'])
        stage = 'network-kernel-limits-and-write-quota'
        container, path = create('limits', PROBE)
        child = launch('limits', [sys.executable, '-B', guardian, '__guard-container', path])
        wait_for(lambda: child.poll() is not None)
        assert child.returncode == 0, (work/'limits.stderr.log').read_text()[-1024:]
        stop(child)
        output = (work/'limits.stdout.log').read_text()
        match = re.search(r'^QUOTA_BYTES=(\d+)$', output, re.M)
        assert 'LOOPBACK_AND_LIMITS_PASSED' in output and match and 0 < int(match[1]) < 2097152
        assert stopped(container, path) and inspect(container)['State']['ExitCode'] == 0
        passed(stage, containerId=container, cpuMax='50000 100000', memoryMax=67108864,
               memorySwapMax=0, pidsMax=32, loopbackHttp=True, externalRouteAbsent=True,
               writableTmpfsBytes=1048576, attemptedWriteBytes=2097152, actualWriteBytes=int(match[1]),
               stopped=True, ownershipConfirmed=True)
        stage = 'wrong-token-before-start'
        container, path = create('wrong-token', HOLD)
        wrong = json.loads(path.read_text()); wrong['token'] = uuid.uuid4().hex; write(path, wrong)
        child = launch('wrong-token', [sys.executable, '-B', guardian, '__guard-container', path])
        wait_for(lambda: child.poll() is not None)
        assert child.returncode != 0 and 'CONTAINER_OWNERSHIP_LABEL' in (work/'wrong-token.stdout.log').read_text()
        assert stopped(container) and inspect(container)['State']['StartedAt'].startswith('0001-')
        passed(stage, containerId=container, refusedBeforeStart=True)
        stage = 'owned-container-cancellation'
        container, path = create('cancel', HOLD)
        child = launch('cancel', [sys.executable, '-B', guardian, '__guard-container', path])
        wait_for(lambda: ready(container, 'cancel'))
        observed = inspect(container)['State']
        child.send_signal(signal.SIGTERM)
        wait_for(lambda: child.poll() is not None and stopped(container, path))
        assert child.returncode == 130
        passed(stage, containerId=container, observedLivePid=observed['Pid'], guardianExit=child.returncode,
               terminationIgnoredByWorkload=True, stopped=True, ownershipConfirmed=True)
        stage = 'changed-ownership-refusal-and-survivor-recovery'
        container, path = create('changed', HOLD)
        child = launch('changed', [sys.executable, '-B', guardian, '__guard-container', path])
        wait_for(lambda: ready(container, 'changed'))
        changed = json.loads(path.read_text()); changed['token'] = uuid.uuid4().hex; write(path, changed)
        child.send_signal(signal.SIGTERM)
        child.wait(timeout=15)
        assert child.returncode != 0
        assert 'CONTAINER_OWNERSHIP_CHANGED' in (work/'changed.stdout.log').read_text()
        survivor = inspect(container)['State']
        assert survivor['Running'] and survivor['Pid'] > 0, 'Ownership uncertainty must not authorize a stop'
        # The separately retained master record still matches the real live label.
        # Recover only that confirmed owned survivor, without changing its bad record.
        recovery = work/'confirmed-survivor.json'
        write(recovery, dict(token=token, containers=[dict(id=container)]))
        stop_owned(recovery)
        assert stopped(container, recovery) and path.read_bytes() != recovery.read_bytes()
        passed(stage, containerId=container, changedOwnershipRefused=True,
               observedSurvivingPid=survivor['Pid'], recoveredFromIndependentOwnedRecord=True, stopped=True)
        stage = 'owned-container-owner-sigkill'
        container, path = create('crash', HOLD)
        owner_state = work/'owner-state.json'
        owner = launch('crash', [sys.executable, '-B', '-c', OWNER, guardian, owner_state, path])
        wait_for(lambda: owner_state.exists() and ready(container, 'crash'))
        owner_info = json.loads(owner_state.read_text())
        live_guard = identity(owner_info['guardian'])
        assert owner_info['owner'] == owner.pid and live_guard and live_guard['parent'] == owner.pid
        observed = inspect(container)['State']
        owner.kill(); owner.wait(timeout=3)
        wait_for(lambda: not running(owner_info['guardian']) and stopped(container, path))
        passed(stage, containerId=container, observedLivePid=observed['Pid'], observedGuardian=live_guard,
               ownerExit=owner.returncode, terminationIgnoredByWorkload=True,
               stopped=True, ownershipConfirmed=True, guardianStopped=True)
        capacity()
        report['status'] = 'passed-managed-registry-container-preflight'
    except BaseException as error:
        report.update(status='failed', failedStage=stage, errorClass=type(error).__name__, error=str(error)[:1024])
        raise
    finally:
        # Docker API cleanup must precede stopping attach/owner groups.
        try:
            stop_owned(owned_path)
            report['allOwnedContainersStopped'] = all(stopped(item['id']) for item in owned['containers'])
            assert report['allOwnedContainersStopped']
        except BaseException as error:
            report.update(status='failed', cleanupError=type(error).__name__+': '+str(error)[:512])
            raise
        finally:
            for child in reversed(processes):
                stop(child)
            for stream in streams:
                stream.close()
            report['allOwnedProcessesStopped'] = all(child.poll() is not None for child in processes)
            report['elapsedMs'] = round((time.monotonic()-began)*1000)
            report['observedDiskGrowthBytes'] = shutil.disk_usage(ROOT).used-baseline
            report['registryContextBuildAcceptance'] = 'not-run'
            try:
                capacity()
            except AssertionError as error:
                report.update(status='failed', cleanupBudgetError=str(error))
                raise
            finally:
                save()
        assert report['allOwnedContainersStopped'] and report['allOwnedProcessesStopped']
        capacity()
    print(json.dumps(dict(status=report['status'], controls=len(report['controls']), evidence=str(out))))


if __name__ == '__main__':
    main()
