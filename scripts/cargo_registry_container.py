"""Bounded CI owner command: real Cargo build/tests in the qualified managed backend."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from pathlib import Path

from deployment_miniserve_image import stop_owned
from project_watch import stop

IMAGE = 'busybox@sha256:dc88b80842580654294472735332ec7c7789a4010ec9a68b69f9b88c19abede6'
MEMORY = 6 * 1024**3
WORK_BYTES = 3 * 1024**3
MAXIMUM_BINARY = 32 * 1024**2


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()



def failure_summary(stdout, stderr):
    """Only fixed categories/identifiers; never assertion or source payloads."""
    text = stdout + "\n" + stderr
    categories = {"disk-full": "No space left on device", "memory-allocation": "Cannot allocate memory",
                  "permission": "Permission denied", "read-only": "Read-only file system",
                  "open-files": "Too many open files", "resources": "Resource temporarily unavailable"}
    return dict(categories=[key for key, token in categories.items() if token in text],
                rustcErrorCodes=sorted(set(re.findall(r"error\[(E[0-9]{4})\]", text)))[:64],
                compileFailures=sorted(set(re.findall(r"error: could not compile `([A-Za-z0-9_-]+)`", text)))[:64],
                failedTests=sorted(set(re.findall(r"^test ([A-Za-z0-9_:]+) \.\.\. FAILED$", text, re.M)))[:400],
                testSummaries=re.findall(r"test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored", text)[:64],
                osErrors=sorted(set(re.findall(r"Os \{ code: ([0-9]+), kind: ([A-Za-z]+)", text)))[:64],
                signals=sorted(set(re.findall(r"signal: ([0-9]+), SIG([A-Z0-9]+)", text)))[:64],
                missingLibraries=sorted(set(re.findall(r"(?:cannot find|unable to find library) -l([A-Za-z0-9_+.-]+)", text)))[:64],
                panicLocations=sorted(set(re.findall(r"panicked at (tests/[A-Za-z0-9_./-]+[.]rs:[0-9]+:[0-9]+)", text)))[:64])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    bundle = Path('bundle')
    if args.verify:
        receipt = json.loads((bundle/'registry-execution.json').read_text())
        assert receipt['status'] == 'passed-real-cargo-registry-execution'
        assert receipt['binaryDigest'] == sha(bundle/'miniserve')
        assert receipt['defaultTestsPassed'] == 325 and receipt['containerStopped'] and receipt['allOwnedContainersStopped']
        print(json.dumps(dict(status='verified-real-cargo-registry-execution', binaryDigest=receipt['binaryDigest'])))
        return
    available = int(next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')).split()[1])*1024
    source = Path.cwd().resolve()
    cargo = Path(spec['cargo']).resolve(strict=True)
    toolchain = cargo.parent.parent
    tests = Path(spec['ownerTestSource']).resolve(strict=True)
    logs = Path(spec['privateLogs'])
    logs.mkdir(parents=True, exist_ok=False)
    host_home = logs/'host-home'
    host_home.mkdir()
    os.environ['HOME'] = str(host_home)
    os.environ['DOCKER_CONFIG'] = str(host_home/'.docker')
    bundle.mkdir(exist_ok=False)
    report = dict(status='running', image=IMAGE, originalConfiguredCacheMounted=False,
                  cargoHome='/work/cargo-home', workFilesystemBytes=WORK_BYTES,
                  cpuAllowance=2, memoryAllowance=MEMORY, memorySwapAllowance=0, pidsAllowance=512,
                  toolchainClosed=False, ownerTestFixturesClosed=False, filesDeleted=0)
    report['capacityObservation'] = dict(uid=os.geteuid(), cpuCount=os.cpu_count(), availableMemoryBytes=available,
                                       requiredMemoryBytes=MEMORY+33554432+500000000)
    assert all(sha(path)==digest for path,digest in spec['toolIdentities'].items()), 'Configured executor bytes changed'
    report['executorIdentities'] = spec['toolIdentities']
    record_path = logs/'owned.json'
    owned = dict(token=uuid.uuid4().hex, containers=[], filesDeleted=0)
    record_path.write_text(json.dumps(owned))
    child = None
    started = time.monotonic()

    def run(argv, expected=0):
        value = subprocess.run(list(map(str, argv)), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        assert len(value.stdout)<65536 and len(value.stderr)<65536, 'Docker control output bound'
        assert value.returncode == expected, value.stderr[-2048:]
        return value.stdout

    def inspect():
        return json.loads(run(['docker', 'inspect', container]))[0]

    def copy_file(remote, destination, maximum):
        # Read exactly one regular tar member under a byte bound; never extract
        # names, links, directories or a daemon-supplied archive to disk.
        process = subprocess.Popen(['docker', 'exec', container, '/usr/bin/tar', '-C', str(Path(remote).parent), '-cf', '-', Path(remote).name],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                item = archive.next()
                assert item is not None and item.isfile() and item.name == Path(remote).name
                assert 0 <= item.size <= maximum, 'Copied artifact byte limit'
                with destination.open('xb') as target, archive.extractfile(item) as incoming:
                    shutil.copyfileobj(incoming, target, length=65536)
                assert destination.stat().st_size == item.size
                assert archive.next() is None, 'Unexpected Docker archive member'
            tail = process.stdout.read(16385)
            assert len(tail)<=16384 and not tail.strip(b'\0'), 'Docker archive trailer bound'
            process.stdout.close()
            assert process.wait(timeout=10) == 0
        finally:
            if process.stdout and not process.stdout.closed:
                process.stdout.close()
            stop(process)

    try:
        assert os.geteuid() != 0 and (os.cpu_count() or 0) >= 4, 'Dedicated nonroot CI capacity required'
        assert available >= MEMORY+33554432+500000000, 'Container memory reservation plus reserve unavailable'
        image = json.loads(run(['docker', 'image', 'inspect', IMAGE]))[0]
        assert IMAGE in image['RepoDigests'] and (image['Os'], image['Architecture']) == ('linux', 'amd64')
        mounts = [(source, '/source'), (source/'.cargo-home/registry', '/registry'),
                  (source/'network-nsswitch.conf','/etc/nsswitch.conf'),
                  (source/'network-hosts.conf','/etc/hosts'),
                  (source/'network-host.conf','/etc/host.conf'),
                  (tests, '/test-source'), (toolchain, str(toolchain))]
        for name in ['/usr', '/bin', '/lib', '/lib64', '/etc/alternatives']:
            if Path(name).exists():
                mounts.append((Path(name), name))
        mounts = [(host.resolve(strict=True), dest) for host, dest in mounts]
        assert all(not any(c in str(host)+dest for c in ',\n\r') for host, dest in mounts)
        user = str(os.geteuid())+':'+str(os.getegid())
        argv = ['docker', 'create', '--label', 'org.patamaps.qualification-owner='+owned['token'],
                '--platform', 'linux/amd64', '--network', 'none', '--read-only', '--user', user,
                '--cpus', '2', '--memory', str(MEMORY), '--memory-swap', str(MEMORY), '--pids-limit', '512',
                '--shm-size', '1048576', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--tmpfs', '/work:rw,exec,nosuid,nodev,size='+str(WORK_BYTES)+',mode=1777',
                '--workdir', '/source/application', '--entrypoint', '/bin/bash']
        for host, dest in mounts:
            argv += ['--mount', 'type=bind,src='+str(host)+',dst='+dest+',readonly']
        environment = dict(PATH=str(cargo.parent)+':/usr/bin:/bin', HOME='/work/home', TMPDIR='/work/tmp',
                           CARGO_HOME='/work/cargo-home', CARGO_TARGET_DIR='/work/target', RUSTC=str(cargo.with_name('rustc')),
                           CARGO=str(cargo), CARGO_BUILD_JOBS='2', RUST_TEST_THREADS='1', CARGO_NET_OFFLINE='true',
                           CARGO_INCREMENTAL='0', CARGO_CACHE_AUTO_CLEAN_FREQUENCY='never',
                           CARGO_PROFILE_DEV_DEBUG='0', CARGO_PROFILE_TEST_DEBUG='0',
                           CARGO_TERM_COLOR='never', CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER='/usr/bin/gcc',
                           CC='/usr/bin/gcc', CXX='/usr/bin/g++', LANG='C.UTF-8')
        for key, value in environment.items():
            argv += ['--env', key+'='+value]
        argv += [image['Id'], '/source/registry-build.sh']
        container = run(argv).strip()
        assert re.fullmatch('[0-9a-f]{64}', container)
        owned['containers'].append(dict(id=container, confirmedStopped=False))
        record_path.write_text(json.dumps(owned))
        guard_record = logs/'guardian-owned.json'
        guard_record.write_bytes(record_path.read_bytes())
        info = inspect(); host = info['HostConfig']
        assert not info['State']['Running'] and info['State']['StartedAt'].startswith('0001-')
        assert info['Image'] == image['Id'] and info['Config']['User'] == user
        assert host['NanoCpus'] == 2000000000 and host['Memory'] == host['MemorySwap'] == MEMORY
        assert host['PidsLimit'] == 512 and host['NetworkMode'] == 'none' and host['ReadonlyRootfs']
        assert host['Tmpfs'] == {'/work': 'rw,exec,nosuid,nodev,size='+str(WORK_BYTES)+',mode=1777'}
        assert host['ShmSize'] == 1048576 and host['CapDrop'] == ['ALL'] and not host['CapAdd'] and not host['Privileged']
        assert host['SecurityOpt'] == ['no-new-privileges']
        actual_mounts = {(m['Source'], m['Destination']) for m in info['Mounts'] if m['Type'] == 'bind'}
        assert actual_mounts == {(str(a.resolve()), b) for a, b in mounts} and all(not m['RW'] for m in info['Mounts'] if m['Type']=='bind')
        report.update(containerId=container, imageId=image['Id'], readOnlyMounts=[dict(source=str(a), destination=b) for a,b in mounts],
                      hostConfigurationVerifiedBeforeStart=True, hostUser=user, explicitLocalhostAddresses=['127.0.0.1','::1'],
                      networkConfigurationDigests={name:sha(source/name) for name in ['network-hosts.conf','network-nsswitch.conf','network-host.conf']})
        with (logs/'guardian.stdout').open('xb') as stdout, (logs/'guardian.stderr').open('xb') as stderr:
            child = subprocess.Popen([sys.executable, '-B', str(source/'project_watch.py'), '__guard-container', guard_record],
                                     stdout=stdout, stderr=stderr, start_new_session=True)
            # A non-loopback URL is required by the unchanged QR test. Give
            # lo one host-local /32; never create a bridge, peer or gateway.
            ready_deadline = time.monotonic()+10
            while not inspect()['State']['Running']:
                assert child.poll() is None, (logs/'guardian.stderr').read_text()[-2048:]
                assert time.monotonic()<ready_deadline
                time.sleep(.05)
            network_identity = run(['docker','exec',container,'/usr/bin/readlink','/proc/self/ns/net']).strip()
            setup_command = "test \"$(id -u)\" = 0; test \"$(awk '/^CapEff:/ {print $2}' /proc/self/status)\" = 0000000000001000; readlink /proc/self/ns/net; ip addr add 192.0.2.2/32 dev lo; ip -4 addr show dev lo | grep -q '192.0.2.2/32'; echo OWNED_LOCAL_ADDRESS_READY"
            setup_id = run(['docker','create','--label','org.patamaps.qualification-owner='+owned['token'],
                '--network','container:'+container,'--read-only','--user','0:0','--cpus','.1',
                '--memory','33554432','--memory-swap','33554432','--pids-limit','16','--shm-size','1048576',
                '--cap-drop','ALL','--cap-add','NET_ADMIN','--security-opt','no-new-privileges',
                '--entrypoint','/bin/sh',image['Id'],'-ec',setup_command]).strip()
            assert re.fullmatch('[0-9a-f]{64}',setup_id)
            owned['containers'].append(dict(id=setup_id,role='local-network-setup',confirmedStopped=False))
            record_path.write_text(json.dumps(owned))
            setup_info = json.loads(run(['docker','inspect',setup_id]))[0]
            shost = setup_info['HostConfig']
            assert setup_info['Image']==image['Id'] and setup_info['Config']['User']=='0:0'
            assert shost['NetworkMode']=='container:'+container and shost['ReadonlyRootfs'] and not shost['Privileged']
            assert shost['CapDrop']==['ALL'] and shost['CapAdd']==['NET_ADMIN'] and shost['SecurityOpt']==['no-new-privileges']
            assert shost['NanoCpus']==100000000 and shost['Memory']==shost['MemorySwap']==33554432
            assert shost['PidsLimit']==16 and shost['ShmSize']==1048576 and not setup_info['Mounts']
            setup_owned = logs/'network-setup-owned.json'
            setup_owned.write_text(json.dumps(dict(token=owned['token'],containers=[dict(id=setup_id)])))
            setup_output = run([sys.executable,'-B',source/'project_watch.py','__guard-container',setup_owned])
            assert network_identity in setup_output.splitlines() and 'OWNED_LOCAL_ADDRESS_READY' in setup_output.splitlines()
            setup_final = json.loads(run(['docker','inspect',setup_id]))[0]['State']
            assert not setup_final['Running'] and setup_final['Pid']==0 and setup_final['ExitCode']==0
            assert json.loads(setup_owned.read_text())['containers'][0]['confirmedStopped']
            report['localAddressProvision'] = dict(address='192.0.2.2/32',interface='lo',networkNamespace=network_identity,
                helperId=setup_id,helperStoppedBeforeCargo=True,effectiveCapability='NET_ADMIN only',
                workloadCapabilitiesDropped=True,bridgeOrExternalNetworkCreated=False,
                helperCpuAllowance=.1,helperMemoryAllowance=33554432,helperPidsAllowance=16)
            run(['docker','exec',container,'/usr/bin/touch','/work/network.ready'])
            copied = False
            while True:
                assert time.monotonic()-started < 2400, 'Cargo execution deadline'
                assert child.poll() is None, (logs/'guardian.stderr').read_text()[-2048:]
                assert stdout.tell()<65536 and stderr.tell()<65536, 'Guardian output bound'
                state = inspect()['State']
                if not state['Running']:
                    time.sleep(.1)
                    continue
                status = run(['docker', 'exec', container, '/bin/bash', '-c',
                              'for f in /work/build.ready /work/done /work/exit; do if test -f "$f"; then printf "%s=" "$f"; cat "$f"; echo; fi; done; '
                              'find /work/logs -type f -printf "LOG_BYTES=%s\\n" 2>/dev/null || true'])
                for length in re.findall(r'^LOG_BYTES=(\d+)$', status, re.M):
                    assert int(length)<=1048576, 'Application log byte limit'
                if '/work/build.ready=' in status and not copied:
                    expected = run(['docker', 'exec', container, '/usr/bin/sha256sum', '/work/export/miniserve']).split()[0]
                    report['releaseBuildObserved'] = True
                    report['producedBinaryDigest'] = 'sha256:'+expected
                    copy_file('/work/export/miniserve', bundle/'miniserve', MAXIMUM_BINARY)
                    (bundle/'miniserve').chmod(0o755)
                    assert sha(bundle/'miniserve') == 'sha256:'+expected
                    report['binaryDigest'] = sha(bundle/'miniserve')
                    report['binaryBytes'] = (bundle/'miniserve').stat().st_size
                    report['binaryCopiedBeforeOwnerTests'] = True
                    run(['docker', 'exec', container, '/usr/bin/touch', '/work/build.accepted'])
                    copied = True
                if '/work/done=' in status:
                    match = re.search(r'^/work/exit=(\d+)$', status, re.M)
                    assert match, status
                    for name in ['limits.txt', 'build.stdout', 'build.stderr', 'test.stdout', 'test.stderr']:
                        copy_file('/work/logs/'+name, logs/name, 1048576)
                    report['cargoExitCode'] = int(match[1])
                    report['cargoDiagnostics'] = failure_summary((logs/'build.stdout').read_text()+'\n'+(logs/'test.stdout').read_text(),
                                                                (logs/'build.stderr').read_text()+'\n'+(logs/'test.stderr').read_text())
                    facts = run(['docker','exec',container,'/bin/bash','-c',
                                 'df -B1 /work | tail -1; cat /sys/fs/cgroup/memory.events'])
                    report['workFilesystemObservation'] = facts.splitlines()[0].split()[1:5]
                    report['memoryEvents'] = dict(line.split() for line in facts.splitlines()[1:])
                    assert match[1] == '0', 'Original Cargo build/test failed; bounded private logs retained'
                    break
                time.sleep(1)
        assert copied
        summaries = re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored', (logs/'test.stdout').read_text())
        assert summaries and all(f=='0' for p,f,i in summaries) and sum(int(p) for p,f,i in summaries)==325
        assert (logs/'limits.txt').read_text().splitlines() == ['200000 100000', str(MEMORY), '0', '512', '3221225472', '65536', '1024', 'lo', 'external-route-absent', 'ipv6-loopback-passed', 'ipv6-external-route-absent']
        assert sha(bundle/'miniserve') == report['binaryDigest']
        assert all(sha(path)==digest for path,digest in spec['toolIdentities'].items()), 'Configured executor bytes changed'
        report.update(status='passed-real-cargo-registry-execution', defaultTestsPassed=325, testSummaries=summaries,
                      kernelLimitsVerified=True, externalRouteAbsent=True, loopbackAvailableForOwnerTests=True, ipv6LoopbackVerified=True, ipv6ExternalRouteAbsent=True,
                      retainedArchiveIndexReadOnly=True,
                      logDigests={name:sha(logs/name) for name in ['limits.txt','build.stdout','build.stderr','test.stdout','test.stderr']})
    except BaseException as error:
        report.update(status='failed', errorClass=type(error).__name__, error=str(error)[:1024])
        if owned['containers']:
            state = inspect()['State']
            report['failureContainerState'] = {k:state[k] for k in ['Status','Running','Pid','ExitCode','Error','OOMKilled']}
            startup = subprocess.run(['docker','logs','--tail','20',container],capture_output=True,text=True,timeout=10)
            report['startupDiagnostics'] = dict(exitCode=startup.returncode,stdout=startup.stdout[-4096:],stderr=startup.stderr[-4096:])
        raise
    finally:
        try:
            # Signal the guardian, whose own cleanup stops Docker before its
            # attach group. The independent master stays available for fallback.
            try:
                if child is not None and child.poll() is None:
                    # Do not group-signal its in-flight Docker cleanup clients.
                    child.terminate()
                    child.wait(timeout=45)
            finally:
                stop_owned(record_path)
            if owned['containers']:
                final = inspect()['State']
                assert not final['Running'] and final['Pid']==0
                report['containerStopped'] = True
                stopped_states = [json.loads(run(['docker','inspect',item['id']]))[0]['State'] for item in owned['containers']]
                report['allOwnedContainersStopped'] = all(not state['Running'] and state['Pid']==0 for state in stopped_states)
                assert report['allOwnedContainersStopped']
                if child is not None:
                    report['guardianCleanupConfirmed'] = json.loads(guard_record.read_text())['containers'][0].get('confirmedStopped') is True
                    assert report['guardianCleanupConfirmed']
        except BaseException as error:
            report.update(status='failed', cleanupError=type(error).__name__+': '+str(error)[:512])
            raise
        finally:
            stop(child)
            report['guardianExit'] = None if child is None else child.returncode
            report['guardianDiagnostics'] = {name:(logs/name).read_text(errors='replace')[-4096:]
                                             for name in ['guardian.stdout','guardian.stderr'] if (logs/name).exists()}
            report['elapsedMs'] = round((time.monotonic()-started)*1000)
            (bundle/'registry-execution.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], defaultTestsPassed=325, binaryDigest=report['binaryDigest'])))


if __name__ == '__main__':
    main()
