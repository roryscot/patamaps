"""Bounded real-kernel qualification for the fixed native inspection primitive."""
from pathlib import Path
import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import signal
import socket
import stat
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_inspection import (KIND, PROFILE, LOCK_KIND, LOCK_PROFILE, launch,
                               launch_strict, owned_directory, owned_driver_lock)

ROOT = Path(__file__).resolve().parents[1]
DENIALS = {errno.EPERM, errno.EACCES}

def need(value, reason):
    if not value:
        raise RuntimeError(reason)

def mach_lookup(service):
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    bootstrap = ctypes.c_uint32.in_dll(library, "bootstrap_port").value
    task = ctypes.c_uint32.in_dll(library, "mach_task_self_").value
    library.bootstrap_look_up.argtypes = [ctypes.c_uint32, ctypes.c_char_p,
                                        ctypes.POINTER(ctypes.c_uint32)]
    library.bootstrap_look_up.restype = ctypes.c_int32
    library.mach_port_deallocate.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    library.mach_port_deallocate.restype = ctypes.c_int32
    port = ctypes.c_uint32()
    code = library.bootstrap_look_up(bootstrap, service.encode(), ctypes.byref(port))
    if code == 0 and port.value:
        library.mach_port_deallocate(task, port)
    return int(code)

def denied(action):
    try:
        action()
    except OSError as error:
        return error.errno in DENIALS
    return False

def connect(family, address):
    with socket.socket(family, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect(address)

def process_path_available(pid):
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    library.proc_pidpath.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(4096)
    return library.proc_pidpath(pid, buffer, len(buffer)) > 0


def open_lock(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    return True


def payload(data, after_exec=False):
    checks = dict(data.get("checks", {}))
    root, outside = Path(data["workspace"]), Path(data["outside"])
    prefix = "afterExec" if after_exec else "initial"
    checks[prefix + "Tcp4Denied"] = denied(lambda: connect(socket.AF_INET, ("127.0.0.1", data["tcp4"])))
    checks[prefix + "Tcp6Denied"] = denied(lambda: connect(socket.AF_INET6, ("::1", data["tcp6"])))
    checks[prefix + "UnixDenied"] = denied(lambda: connect(socket.AF_UNIX, data["unix"]))
    checks[prefix + "MachLookupDenied"] = mach_lookup(data["machService"]) != 0
    if after_exec:
        if data.get("strictLock"):
            checks["afterExecProtectedHardlinkDenied"] = denied(
                lambda: os.link(outside, root / "after-exec-hardlink"))
            checks["afterExecLockOpenAllowed"] = open_lock(data["driverLock"])
        checks["execPreservedPid"] = data["initialPid"] == os.getpid()
        print(json.dumps({"status": "completed-kernel-probe", "checks": checks,
                          "pid": os.getpid()}), flush=True)
        return
    checks["sessionLeader"] = os.getsid(0) == os.getpid()
    checks["sessionCannotDetach"] = denied(os.setsid)
    checks["canReadSelectedFixture"] = outside.read_bytes() == b"unchanged-fixture"
    (root / "allowed-output").write_bytes(b"owned-output")
    checks["ownedWriteAllowed"] = (root / "allowed-output").read_bytes() == b"owned-output"
    if data.get("strictLock"):
        (root / "escape").symlink_to(outside.parent, target_is_directory=True)
        checks["protectedHardlinkDenied"] = denied(lambda: os.link(outside, root / "hardlink"))
        checks["lockHardlinkDenied"] = denied(lambda: os.link(data["driverLock"], root / "lock-link"))
        checks["ownedHardlinkDenied"] = denied(lambda: os.link(root / "allowed-output", root / "owned-link"))
        checks["lockOpenAndFlockAllowed"] = open_lock(data["driverLock"])
        checks["lockParentWriteDenied"] = denied(
            lambda: (Path(data["driverLock"]).parent / "unexpected-output").write_bytes(b"bad"))
        checks["selfProcessPathAllowed"] = process_path_available(os.getpid())
        checks["externalProcessPathDenied"] = not process_path_available(data["parentPid"])
    checks["outsideWriteDenied"] = denied(lambda: outside.write_bytes(b"bad-write"))
    checks["symlinkWriteDenied"] = denied(lambda: (root / "escape" / outside.name).write_bytes(b"bad-link"))
    checks["externalSignalDenied"] = denied(lambda: os.kill(data["parentPid"], signal.SIGUSR1))
    try:
        info = os.fstat(data["inheritableFd"])
        checks["extraFdClosed"] = [info.st_dev, info.st_ino] != data["outsideIdentity"]
    except OSError as error:
        checks["extraFdClosed"] = error.errno == errno.EBADF
    checks["stdinIsPipe"] = stat.S_ISFIFO(os.fstat(0).st_mode)
    try:
        pid = os.fork()
    except OSError as error:
        checks["forkDenied"] = error.errno in DENIALS
    else:
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        checks["forkDenied"] = False
    try:
        pid = os.posix_spawn("/usr/bin/true", ["/usr/bin/true"], dict(os.environ))
    except OSError as error:
        checks["posixSpawnDenied"] = error.errno in DENIALS
    else:
        os.waitpid(pid, 0)
        checks["posixSpawnDenied"] = False
    data.update(checks=checks, initialPid=os.getpid())
    os.execv(sys.executable, [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                             "__after_exec", json.dumps(data)])

def main():
    from parity.storage_guard import ensure_guarded
    ensure_guarded()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--strict-lock", action="store_true")
    args = parser.parse_args()
    work = args.work
    need(work.is_absolute() and not work.exists(), "Fresh absolute work directory required")
    work.mkdir(parents=True, mode=0o700)
    selected_profile = LOCK_PROFILE if args.strict_lock else PROFILE
    report = {"status": "started-native-inspection-kernel-qualification",
              "kind": LOCK_KIND if args.strict_lock else KIND, "filesDeleted": 0, "servicesInterrupted": 0,
              "supervisorPolicyChanged": False, "parallelActivated": False,
              "automaticReservationReleaseQualified": False}
    sources = {"qualifier": Path(__file__), "helper": Path(__file__).parent / "native_inspection.py"}
    source_hashes = {}
    for label, path in sources.items():
        content = path.read_bytes()
        source_hashes[label] = hashlib.sha256(content).hexdigest()
        (work / (label + ".executed.py")).write_bytes(content)
    report["sourceHashesBefore"] = source_hashes
    child = None
    servers = []
    descriptor = None
    old_stdin = None
    signal_hits = []
    old_handler = signal.signal(signal.SIGUSR1, lambda *_: signal_hits.append(True))
    def interrupted(*_):
        raise InterruptedError("Native inspection qualifier interrupted")
    old_signals = {name: signal.signal(name, interrupted)
                   for name in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]}
    try:
        fixture = Path("/private/tmp") / ("patamaps-ni-" + uuid.uuid4().hex[:10])
        fixture.mkdir(mode=0o700)
        workspace, supervisor = fixture / "job", fixture / "supervisor"
        workspace.mkdir(mode=0o700)
        supervisor.mkdir(mode=0o700)
        outside = supervisor / "sentinel"
        outside.write_bytes(b"unchanged-fixture")
        if not args.strict_lock:
            (workspace / "escape").symlink_to(supervisor, target_is_directory=True)
        (fixture / "alias").symlink_to(workspace, target_is_directory=True)
        report["retainedFixture"] = str(fixture)
        refused = []
        for label, candidate, base in [
            ("relative", Path("job"), fixture),
            ("whole-owner-root", fixture, fixture),
            ("alias", fixture / "alias", fixture),
            ("outside-owner-root", work, fixture)]:
            try:
                owned_directory(candidate, base)
            except (ValueError, OSError):
                refused.append(label)
        need(len(refused) == 4, "Unsafe root declaration accepted")
        report["rootRefusals"] = refused
        driver_lock = None
        if args.strict_lock:
            driver_lock = supervisor / "driver.lock"
            driver_lock.touch(mode=0o600)
            lock_identity = owned_driver_lock(driver_lock, workspace)
            open_lock(driver_lock)
            need(process_path_available(os.getpid()), "No positive process-path baseline")
            report["strictPositiveBaselines"] = ["lock-open-and-flock", "own-process-path"]
            rejected = []
            candidates = {}
            for label in ["symlink", "shared", "nonempty", "worldreadable", "directory", "missing"]:
                parent = fixture / ("bad-" + label)
                parent.mkdir(mode=0o700)
                candidate = parent / "driver.lock"
                if label == "symlink":
                    candidate.symlink_to(driver_lock)
                elif label == "directory":
                    candidate.mkdir(mode=0o600)
                elif label != "missing":
                    candidate.touch(mode=0o600)
                    if label == "shared":
                        os.link(candidate, parent / "peer")
                    elif label == "nonempty":
                        candidate.write_bytes(b"x")
                    elif label == "worldreadable":
                        candidate.chmod(0o644)
                candidates[label] = (candidate, workspace)
            alias = fixture / "state-alias"
            alias.symlink_to(supervisor, target_is_directory=True)
            candidates["alias"] = (alias / "driver.lock", workspace)
            candidates["relative"] = (Path("driver.lock"), workspace)
            wrong = fixture / "wrong-name"
            wrong.touch(mode=0o600)
            candidates["wrongname"] = (wrong, workspace)
            overlap = fixture / "overlap"
            overlap.mkdir(mode=0o700)
            (overlap / "driver.lock").touch(mode=0o600)
            candidates["overlap"] = (overlap / "driver.lock", overlap)
            for label, (candidate, tree) in candidates.items():
                try:
                    owned_driver_lock(candidate, tree)
                except (OSError, ValueError):
                    rejected.append(label)
            need(len(rejected) == 10, "Unsafe lock declaration accepted")
            seeded = fixture / "seeded"
            seeded.mkdir(mode=0o700)
            os.link(outside, seeded / "preexisting-link")
            try:
                unexpected, _ = launch_strict(sys.executable, ["-c", "pass"],
                    workspace=seeded, allowed_root=fixture, driver_lock=driver_lock)
            except ValueError:
                rejected.append("preseeded-workspace")
            else:
                os.killpg(unexpected.pid, signal.SIGKILL)
                unexpected.wait(timeout=5)
                raise RuntimeError("Preseeded writable tree admitted")
            report["lockRefusals"] = rejected
            report["originalLockIdentity"] = lock_identity
        for family, address in [(socket.AF_INET, ("127.0.0.1", 0)),
                                (socket.AF_INET6, ("::1", 0)),
                                (socket.AF_UNIX, str(supervisor / "socket"))]:
            server = socket.socket(family, socket.SOCK_STREAM)
            server.bind(address)
            server.listen(8)
            servers.append(server)
            connect(family, server.getsockname())
        services = ["com.apple.cfprefsd.agent", "com.apple.cfprefsd.daemon", "com.apple.lsd.mapdb"]
        baseline = {name: mach_lookup(name) for name in services}
        service = next((name for name in services if baseline[name] == 0), None)
        need(service is not None, "No available positive Mach lookup baseline")
        report["unsandboxedBaselinesPassed"] = ["tcp4", "tcp6", "unix", "mach"]
        descriptor = os.open(outside, os.O_RDWR)
        os.set_inheritable(descriptor, True)
        info = os.fstat(descriptor)
        data = {"workspace": str(workspace), "outside": str(outside),
                "tcp4": servers[0].getsockname()[1], "tcp6": servers[1].getsockname()[1],
                "unix": str(supervisor / "socket"), "parentPid": os.getpid(),
                "inheritableFd": descriptor, "outsideIdentity": [info.st_dev, info.st_ino],
                "machService": service, "strictLock": args.strict_lock,
                "driverLock": str(driver_lock) if driver_lock is not None else None}
        a, b = socket.socketpair()
        old_stdin = os.dup(0)
        try:
            os.dup2(a.fileno(), 0)
            chosen_launch = launch_strict if args.strict_lock else launch
            options = {"driver_lock": driver_lock} if args.strict_lock else {}
            child, requested = chosen_launch(sys.executable, ["-I", "-S", "-B", str(Path(__file__).resolve()), "__payload"],
                                      workspace=workspace, allowed_root=fixture, **options)
        finally:
            os.dup2(old_stdin, 0)
            os.close(old_stdin)
            old_stdin = None
            a.close()
            b.close()
        report["requestedProfile"] = requested
        try:
            out, err = child.communicate(json.dumps(data).encode(), timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate(timeout=5)
            raise RuntimeError("Isolated probe exceeded15seconds")
        (work / "payload.stdout").write_bytes(out)
        (work / "payload.stderr").write_bytes(err)
        report.update(payloadExitCode=child.returncode, stdoutBytes=len(out), stderrBytes=len(err))
        need(len(out) <= 65536 and len(err) <= 65536, "Probe output bound exceeded")
        need(child.returncode == 0, "Isolated probe failed")
        result = json.loads(out)
        checks = result["checks"]
        expected = {
            "initialTcp4Denied", "initialTcp6Denied", "initialUnixDenied", "initialMachLookupDenied",
            "sessionLeader", "sessionCannotDetach", "canReadSelectedFixture", "ownedWriteAllowed",
            "outsideWriteDenied", "symlinkWriteDenied", "externalSignalDenied", "extraFdClosed",
            "stdinIsPipe", "forkDenied", "posixSpawnDenied", "afterExecTcp4Denied",
            "afterExecTcp6Denied", "afterExecUnixDenied", "afterExecMachLookupDenied", "execPreservedPid"
        }
        if args.strict_lock:
            expected |= {"protectedHardlinkDenied", "lockHardlinkDenied", "ownedHardlinkDenied",
                         "lockOpenAndFlockAllowed", "lockParentWriteDenied",
                         "selfProcessPathAllowed", "externalProcessPathDenied",
                         "afterExecProtectedHardlinkDenied", "afterExecLockOpenAllowed"}
            need(owned_driver_lock(driver_lock, workspace) == lock_identity, "Driver lock changed")
            report["driverLockUnchanged"] = True
        report.update(checks=checks, checkCount=len(checks))
        need(set(checks) == expected and all(checks.values()), "Kernel denial/positive controls failed")
        need(outside.read_bytes() == b"unchanged-fixture" and not signal_hits,
             "Restricted payload affected supervisor")
        current = workspace.stat()
        need([current.st_dev, current.st_ino] == requested["workspaceIdentity"],
             "Owned workspace identity changed")
        need(all(hashlib.sha256(path.read_bytes()).hexdigest() == source_hashes[label]
                 for label, path in sources.items()), "Qualification source changed")
        report.update(status="passed-native-inspection-kernel-qualification",
                      checks=checks, checkCount=len(checks), sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      helperSha256=hashlib.sha256((Path(__file__).parent / "native_inspection.py").read_bytes()).hexdigest(),
                      profileSha256=hashlib.sha256(selected_profile.encode()).hexdigest(),
                      supervisorSentinelUnchanged=True, unrelatedSignalHits=0,
                      childStopped=child.poll() is not None,
                      platform=subprocess.check_output(["/usr/bin/sw_vers", "-productVersion"], text=True).strip())
    except BaseException as error:
        report.update(status="failed-native-inspection-kernel-qualification",
                      failureType=type(error).__name__, failure=str(error))
        raise
    finally:
        for name in old_signals:
            signal.signal(name, signal.SIG_IGN)
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
        if descriptor is not None:
            os.close(descriptor)
        for server in servers:
            server.close()
        signal.signal(signal.SIGUSR1, old_handler)
        for name, handler in old_signals.items():
            signal.signal(name, handler)
        (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k:v for k,v in report.items() if k not in
                          {"retainedFixture", "requestedProfile"}}), flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"__payload", "__after_exec"}:
        if sys.argv[1] == "__payload":
            data = json.loads(sys.stdin.buffer.read(16385))
            payload(data)
        else:
            payload(json.loads(sys.argv[2]), after_exec=True)
    else:
        main()
