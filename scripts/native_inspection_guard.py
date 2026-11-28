"""Proposed trusted adapter for bounded, single-process native inspections.

This preserves the existing watcher guardian. Its private lifecycle pipe is
separate from payload data, but is NOT an installed supervisor attestation.
The caller must still hold the ordinary exclusive reservation. No release
predicate, concurrency policy or arbitrary-build executor is installed here.
"""
from pathlib import Path
import argparse
import ctypes
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
MAX_RECORD_BYTES = 4096
OUTPUT_LIMIT = 1048576


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1048576):
            h.update(chunk)
    return h.hexdigest()


def load_sibling(name):
    spec = importlib.util.spec_from_file_location("patamaps_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_environment():
    # -I -S also prevents site/user startup; sanitize the dynamic loader before
    # Python itself starts. Do not forward arbitrary caller environment.
    return {"PATH": "/usr/bin:/bin", "LANG": "C", "PYTHONDONTWRITEBYTECODE": "1"}


def bindings(program):
    paths = [Path(__file__).resolve(), HERE / "native_inspection.py",
             HERE / "project_watch.py", Path(sys.executable).resolve(),
             Path("/usr/bin/sandbox-exec"), Path(program).resolve(strict=True)]
    return {str(p): digest(p) for p in paths}


def check_bindings(expected):
    return isinstance(expected, dict) and bool(expected) and all(
        Path(path).is_absolute() and digest(path) == value for path, value in expected.items())


def validate_prefix(records, run_id, guardian_pid):
    """Closed lifecycle grammar. Stdout is never an input to this parser."""
    common = {"runId", "guardianPid", "parentPid", "sequence", "event"}
    schemas = [common, common | {"pid", "pgid"},
               common | {"pid", "pgid", "returncode", "stdoutClosed", "stderrClosed",
                         "bindingsUnchanged"}]
    events = ["launch-pending", "payload-started", "payload-stopped"]
    if len(records) > 3:
        raise ValueError("INSPECTION_CONTROL_PROTOCOL")
    for index, row in enumerate(records):
        if (not isinstance(row, dict) or set(row) != schemas[index]
                or row["runId"] != run_id or row["guardianPid"] != guardian_pid
                or type(row["guardianPid"]) is not int or row["guardianPid"] <= 1
                or type(row["parentPid"]) is not int or row["parentPid"] <= 1
                or type(row["sequence"]) is not int or row["sequence"] != index
                or row["event"] != events[index]):
            raise ValueError("INSPECTION_CONTROL_PROTOCOL")
    if any(row["parentPid"] != records[0]["parentPid"] for row in records):
        raise ValueError("INSPECTION_CONTROL_PARENT_CHANGED")
    if len(records) < 2:
        return None
    start = records[1]
    if type(start["pid"]) is not int or start["pid"] <= 1 or type(start["pgid"]) is not int or start["pgid"] != start["pid"]:
        raise ValueError("INSPECTION_CONTROL_PROTOCOL")
    if len(records) < 3:
        return None
    end = records[2]
    if (type(start["pid"]) is not int or start["pid"] <= 1
            or type(start["pgid"]) is not int or start["pgid"] != start["pid"]
            or type(end["pid"]) is not int or type(end["pgid"]) is not int
            or end["pid"] != start["pid"] or end["pgid"] != start["pgid"]
            or type(end["returncode"]) is not int
            or any(type(end[k]) is not bool for k in
                   ["stdoutClosed", "stderrClosed", "bindingsUnchanged"])):
        raise ValueError("INSPECTION_STOP_UNCONFIRMED")
    return end


def validate_records(records, run_id, guardian_pid):
    if len(records) != 3:
        raise ValueError("INSPECTION_CONTROL_INCOMPLETE")
    end = validate_prefix(records, run_id, guardian_pid)
    if any(end[k] is not True for k in ["stdoutClosed", "stderrClosed", "bindingsUnchanged"]):
        raise ValueError("INSPECTION_STOP_UNCONFIRMED")
    return end


def inspection_mode(value, primitive, work):
    """Validate only closed fixed variants; never accept caller profile text."""
    if value["version"] == 1:
        return None
    item = value["inspection"]
    if (not isinstance(item, dict)
            or set(item) != {"kind", "driverLock", "lockIdentity"}):
        raise ValueError("INSPECTION_MODE_PROTOCOL")
    if item["kind"] == primitive.STRICT_KIND:
        if item["driverLock"] is not None or item["lockIdentity"] is not None:
            raise ValueError("INSPECTION_MODE_PROTOCOL")
    elif item["kind"] == primitive.LOCK_KIND:
        if (not isinstance(item["driverLock"], str)
                or not isinstance(item["lockIdentity"], list)
                or len(item["lockIdentity"]) != 2
                or any(type(v) is not int for v in item["lockIdentity"])
                or primitive.owned_driver_lock(item["driverLock"], work) != item["lockIdentity"]):
            raise ValueError("INSPECTION_LOCK_CHANGED")
    else:
        raise ValueError("INSPECTION_MODE_PROTOCOL")
    return item

class _BsdInfo(ctypes.Structure):
    # Local Apple SDK sys/proc_info.h, LP64 proc_bsdinfo (136 bytes).
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "flags", "status", "xstatus", "pid", "ppid", "uid", "gid",
        "ruid", "rgid", "svuid", "svgid", "reserved")] + [
        ("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32)] + [
        (name, ctypes.c_uint32) for name in ("nfiles", "pgid", "jobc", "tty", "tty_pgid")] + [
        ("nice", ctypes.c_int32), ("start_seconds", ctypes.c_uint64),
        ("start_microseconds", ctypes.c_uint64)]


def process_identity(pid):
    """Darwin kernel identity, not a caller-provided PID or second-granularity date."""
    if sys.platform != "darwin" or ctypes.sizeof(_BsdInfo) != 136:
        raise RuntimeError("Native process identity is unavailable")
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                    ctypes.c_void_p, ctypes.c_int]
    library.proc_pidinfo.restype = ctypes.c_int
    value = _BsdInfo()
    ctypes.set_errno(0)
    count = library.proc_pidinfo(pid, 3, 0, ctypes.byref(value), ctypes.sizeof(value))
    if count == 0 and ctypes.get_errno() == errno.ESRCH:
        return None
    if count != ctypes.sizeof(value) or value.pid != pid:
        raise OSError(ctypes.get_errno() or errno.EIO, "Native identity unconfirmed")
    return {"pid": int(value.pid), "parentPid": int(value.ppid), "pgid": int(value.pgid),
            "startSeconds": int(value.start_seconds), "startMicroseconds": int(value.start_microseconds)}


def same_process(before, after):
    return (isinstance(before, dict) and isinstance(after, dict)
            and all(before.get(k) == after.get(k) for k in
                    ["pid", "pgid", "startSeconds", "startMicroseconds"]))


def group_live(pgid):
    result = subprocess.run(["/bin/ps", "-axo", "pgid=,stat="], capture_output=True,
                            text=True, timeout=5, check=True)
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    if not rows or any(len(row) != 2 or not row[0].isdigit() for row in rows):
        raise ValueError("INSPECTION_GROUP_STATE_UNCONFIRMED")
    return any(int(group) == pgid and not state.startswith("Z") for group, state in rows)


def stop_registered(identity, grace):
    """Never signal a replacement PID, even if it uses the same group number."""
    if identity is None:
        return False
    pid = identity["pid"]
    for signum, budget in [(signal.SIGTERM, grace), (signal.SIGKILL, 2)]:
        current = process_identity(pid)
        if current is None:
            return not group_live(pid)
        if not same_process(identity, current):
            return False
        try:
            os.killpg(pid, signum)
        except (ProcessLookupError, PermissionError):
            return not group_live(pid)
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            current = process_identity(pid)
            if current is None:
                return not group_live(pid)
            if not same_process(identity, current):
                return False
            time.sleep(.02)
    return not group_live(pid)


def private_observer(fd):
    if type(fd) is not int or fd < 3:
        raise ValueError("INSPECTION_OBSERVER_DESCRIPTOR")
    info = os.fstat(fd)
    access = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
    if stat.S_ISFIFO(info.st_mode):
        if access != os.O_WRONLY:
            raise ValueError("INSPECTION_OBSERVER_DIRECTION")
    elif stat.S_ISSOCK(info.st_mode):
        # Node's extra stdio pipes are anonymous Unix socket pairs.
        peer = socket.socket(fileno=fd)
        try:
            if (peer.family != socket.AF_UNIX or peer.type != socket.SOCK_STREAM
                    or peer.getsockname() not in ("", b"") or peer.getpeername() not in ("", b"")):
                raise ValueError("INSPECTION_OBSERVER_NOT_PRIVATE")
        finally:
            peer.detach()
    else:
        raise ValueError("INSPECTION_OBSERVER_NOT_PRIVATE")
    os.set_inheritable(fd, False)
    os.set_blocking(fd, False)
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def append_record(path, value):
    with path.open("ab") as stream:
        stream.write(json.dumps(value, separators=(",", ":")).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def save_live(path, value):
    temporary = path.with_name("live-" + uuid.uuid4().hex + ".staging")
    with temporary.open("x") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class InspectionRunner:
    """subprocess.run-shaped adapter for existing read-only watcher functions.

    Each invocation retains its descriptor, raw data and control records.
    The descriptor hashes are caller bindings, not registry authorization.
    """
    def __init__(self, root, allowed_root, *, stop_grace=2, strict=False, driver_lock=None, lifecycle_fd=None):
        primitive = load_sibling("native_inspection")
        if type(strict) is not bool:
            raise ValueError("INSPECTION_MODE_PROTOCOL")
        self.strict = strict or driver_lock is not None
        self.driver_lock = Path(driver_lock) if driver_lock is not None else None
        if self.strict and (sys.platform != "darwin" or not primitive.SANDBOX_EXEC.is_file()):
            raise RuntimeError("Darwin inspection isolation is unavailable")
        self.root, _ = primitive.owned_directory(root, allowed_root)
        self.allowed_root = Path(allowed_root)
        if not .05 <= stop_grace <= 10:
            raise ValueError("INSPECTION_STOP_GRACE")
        self.stop_grace = stop_grace
        self.calls = []
        self.lifecycle_fd = lifecycle_fd
        self.observer_identity = private_observer(lifecycle_fd) if lifecycle_fd is not None else None

    def prepare(self, argv, timeout):
        if (not isinstance(argv, (list, tuple)) or not argv
                or not all(isinstance(v, str) for v in argv)
                or not Path(argv[0]).is_absolute()
                or isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not .05 <= timeout <= 3600):
            raise ValueError("INSPECTION_INVOCATION")
        job = self.root / uuid.uuid4().hex
        job.mkdir(mode=0o700)
        work = job / "work"
        work.mkdir(mode=0o700)
        registered = bindings(argv[0])
        # The source/payload/descriptor are outside every writable tree.
        if any(work == Path(p) or work in Path(p).parents for p in registered):
            raise ValueError("INSPECTION_TRUSTED_INPUT_WRITABLE")
        descriptor = {"version": 1, "runId": job.name, "argv": list(argv),
                      "workspace": str(work), "allowedRoot": str(self.root),
                      "timeout": timeout, "stopGrace": self.stop_grace,
                      "bindings": registered}
        if self.strict:
            primitive = load_sibling("native_inspection")
            descriptor["version"] = 2
            descriptor["inspection"] = {
                "kind": primitive.LOCK_KIND if self.driver_lock is not None else primitive.STRICT_KIND,
                "driverLock": str(self.driver_lock) if self.driver_lock is not None else None,
                "lockIdentity": primitive.owned_driver_lock(self.driver_lock, work)
                                if self.driver_lock is not None else None}
        path = job / "descriptor.json"
        with path.open("x") as stream:
            json.dump(descriptor, stream, sort_keys=True)
        path.chmod(0o600)
        return path, descriptor

    @staticmethod
    def spawn(path, descriptor, control_write, *, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        if json.loads(Path(path).read_text()) != descriptor:
            raise ValueError("INSPECTION_DESCRIPTOR_CHANGED")
        command = [str(Path(sys.executable).resolve()), "-I", "-S", "-B", str(Path(__file__).resolve()),
                   "--descriptor", str(path), "--descriptor-sha", digest(path),
                   "--control-fd", str(control_write), "--expected-parent", str(os.getpid())]
        return subprocess.Popen(command, cwd=HERE, env=minimal_environment(),
                                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                close_fds=True, pass_fds=(control_write,), start_new_session=True)

    def __call__(self, argv, *, stdout, stderr, timeout, check=False):
        if stdout != subprocess.PIPE or stderr != subprocess.PIPE or check is not False:
            raise ValueError("INSPECTION_CAPTURE_CONTRACT")
        path, descriptor = self.prepare(argv, timeout)
        expected_sha = digest(path)
        read_fd, write_fd = os.pipe()
        child = None
        outputs = {"stdout": bytearray(), "stderr": bytearray()}
        records, buffer = [], bytearray()
        closed = set()
        native_identity = None
        guardian_identity = None
        native_already_stopped = False
        root_sequence = 0
        succeeded = False
        error_text = None
        cleanup = {"confirmed": False, "reason": "launch-unsealed"}
        registration_known = False
        deadline = time.monotonic() + timeout + self.stop_grace + 10

        def state(phase):
            save_live(path.parent / "live.json", {
                "runId": descriptor["runId"], "phase": phase,
                "controllerPid": os.getpid(), "guardianPid": child.pid if child else None,
                "guardianIdentity": guardian_identity, "nativeIdentity": native_identity, "registrationKnown": registration_known,
                "nativeAlreadyStopped": native_already_stopped, "acceptedRecordCount": len(records),
                "controlClosed": "control" in closed, "cleanup": cleanup,
                "error": error_text, "automaticReservationReleaseQualified": False})

        def forward(event, **fields):
            nonlocal root_sequence
            if self.lifecycle_fd is None:
                return
            if private_observer(self.lifecycle_fd) != self.observer_identity:
                raise ValueError("INSPECTION_OBSERVER_CHANGED")
            frame = {"event": event, "runId": descriptor["runId"], "controllerPid": os.getpid(),
                     "sequence": root_sequence, **fields}
            raw = json.dumps(frame, separators=(",", ":")).encode() + b"\n"
            if len(raw) > MAX_RECORD_BYTES or os.write(self.lifecycle_fd, raw) != len(raw):
                raise ValueError("INSPECTION_OBSERVER_WRITE_UNCONFIRMED")
            root_sequence += 1

        def accept(row):
            nonlocal native_identity, native_already_stopped, registration_known
            validate_prefix([*records, row], descriptor["runId"], child.pid)
            if row["parentPid"] != os.getpid():
                raise ValueError("INSPECTION_CONTROL_PARENT_CHANGED")
            if len(records) == 1:
                observed = process_identity(row["pid"])
                if observed is None:
                    if group_live(row["pgid"]):
                        raise ValueError("INSPECTION_REGISTRATION_IDENTITY_UNCONFIRMED")
                    native_already_stopped = True
                elif observed["parentPid"] != child.pid or observed["pgid"] != row["pgid"]:
                    raise ValueError("INSPECTION_REGISTRATION_IDENTITY_MISMATCH")
                else:
                    native_identity = observed
                registration_known = True
            records.append(row)
            append_record(path.parent / "lifecycle.jsonl", row)
            state(row["event"])
            forward("guardian-record", record=row, nativeIdentity=native_identity,
                    registrationKnown=registration_known, nativeAlreadyStopped=native_already_stopped)

        def read_ready(poll, budget):
            for key, _ in poll.select(budget):
                chunk = os.read(key.fd, 65536)
                name = key.data
                if not chunk:
                    poll.unregister(key.fileobj)
                    closed.add(name)
                    if name == "control" and buffer:
                        raise ValueError("INSPECTION_CONTROL_PARTIAL_RECORD")
                    continue
                if name == "control":
                    raw_file = path.parent / "control.raw"
                    # Never persist an unbounded control producer.
                    previous = raw_file.stat().st_size if raw_file.exists() else 0
                    with raw_file.open("ab") as stream:
                        stream.write(chunk[:max(0, 3 * MAX_RECORD_BYTES - previous)])
                    if previous + len(chunk) > 3 * MAX_RECORD_BYTES:
                        raise ValueError("INSPECTION_CONTROL_OUTPUT_LIMIT")
                    buffer.extend(chunk)
                    while b"\n" in buffer:
                        line, _, tail = buffer.partition(b"\n")
                        buffer[:] = tail
                        if len(line) > MAX_RECORD_BYTES:
                            raise ValueError("INSPECTION_CONTROL_RECORD_LIMIT")
                        accept(json.loads(line))
                    if len(buffer) > MAX_RECORD_BYTES:
                        raise ValueError("INSPECTION_CONTROL_RECORD_LIMIT")
                else:
                    outputs[name].extend(chunk)
                    if len(outputs[name]) > OUTPUT_LIMIT + 65536:
                        raise ValueError("INSPECTION_GUARDIAN_OUTPUT_LIMIT")

        poll = selectors.DefaultSelector()
        original_parent = os.getppid()
        try:
            state("guardian-launch-pending")
            # This reaches the outer collector before any guardian/native spawn.
            forward("guardian-launch-pending", descriptorDigest=expected_sha)
            child = self.spawn(path, descriptor, write_fd)
            os.close(write_fd)
            write_fd = None
            guardian_identity = process_identity(child.pid)
            if guardian_identity is not None and guardian_identity["parentPid"] != os.getpid():
                raise ValueError("INSPECTION_GUARDIAN_IDENTITY_MISMATCH")
            forward("guardian-started", guardianPid=child.pid, guardianIdentity=guardian_identity)
            for name, stream in [("control", read_fd), ("stdout", child.stdout), ("stderr", child.stderr)]:
                os.set_blocking(stream if isinstance(stream, int) else stream.fileno(), False)
                poll.register(stream, selectors.EVENT_READ, name)
            while poll.get_map() or child.poll() is None:
                if os.getppid() != original_parent:
                    raise InterruptedError("Inspection controller parent exited")
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(argv, timeout + self.stop_grace + 10)
                read_ready(poll, .05)
            child.wait()
            end = validate_records(records, descriptor["runId"], child.pid)
            if closed != {"control", "stdout", "stderr"}:
                raise ValueError("INSPECTION_STREAMS_UNCONFIRMED")
            if not check_bindings(descriptor["bindings"]) or digest(path) != expected_sha:
                raise ValueError("INSPECTION_BINDINGS_CHANGED")
            expected_code = end["returncode"] if end["returncode"] >= 0 else 128 - end["returncode"]
            if child.returncode not in (expected_code, 130):
                raise ValueError("INSPECTION_GUARDIAN_REFUSED")
            if child.returncode == 0 and end["returncode"] != 0:
                raise ValueError("INSPECTION_EXIT_PROTOCOL")
            cleanup = {"confirmed": registration_known and not group_live(end["pgid"]), "reason": "completed"}
            if cleanup["confirmed"] is not True:
                raise ValueError("INSPECTION_GROUP_STOP_UNCONFIRMED")
            succeeded = True
            state("complete")
            return subprocess.CompletedProcess(argv, child.returncode,
                                               bytes(outputs["stdout"]), bytes(outputs["stderr"]))
        except BaseException as error:
            error_text = type(error).__name__ + ": " + str(error)
            # Stop only our still-live guardian; it normally stops/reaps native.
            # A killed guardian's separate native group needs its verified kernel identity.
            try:
                if child is not None and child.poll() is None:
                    load_sibling("project_watch").stop(child, grace=self.stop_grace + 2)
                if registration_known:
                    confirmed = (not group_live(records[1]["pgid"]) if native_already_stopped else
                                 stop_registered(native_identity, self.stop_grace))
                    cleanup = {"confirmed": confirmed, "reason": "registered-owned-processes"}
                else:
                    cleanup = {"confirmed": False, "reason": "launch-unsealed"}
            except (OSError, ValueError, subprocess.SubprocessError) as cleanup_error:
                cleanup = {"confirmed": False, "reason": str(cleanup_error)}
            # Retain bytes already captured. Missing/invalid proof stays a failure,
            # even when independently stopping a registered group succeeds.
            state("refused")
            raise
        finally:
            if write_fd is not None:
                os.close(write_fd)
            poll.close()
            os.close(read_fd)
            if child is not None:
                for stream in [child.stdout, child.stderr]:
                    if stream is not None:
                        stream.close()
            (path.parent / "stdout").write_bytes(outputs["stdout"])
            (path.parent / "stderr").write_bytes(outputs["stderr"])
            receipt = {"guardianPid": child.pid if child else None,
                       "guardianExitCode": child.returncode if child else None,
                       "records": records, "cleanup": cleanup, "controlComplete": succeeded,
                       "automaticReservationReleaseQualified": False}
            (path.parent / "control.json").write_text(json.dumps(receipt, indent=2) + "\n")
            self.calls.append(receipt)
            try:
                forward("inspection-finished", guardianPid=child.pid if child else None,
                        controlComplete=succeeded, cleanup=cleanup)
            except (OSError, ValueError):
                # An unavailable observer is never evidence of release.
                receipt["observerComplete"] = False
                receipt["controlComplete"] = False
                (path.parent / "control.json").write_text(json.dumps(receipt, indent=2) + "\n")
                state("observer-refused")
                if succeeded:
                    raise


def run_guardian(path, expected_sha, control_fd, expected_parent):
    """Internal closed guardian entrypoint; only the native payload is untrusted."""
    path = Path(path)
    if (not path.is_absolute() or path.resolve(strict=True) != path or path.is_symlink()
            or digest(path) != expected_sha or os.getppid() != expected_parent):
        raise ValueError("INSPECTION_DESCRIPTOR_OR_PARENT_CHANGED")
    value = json.loads(path.read_text())
    if (not isinstance(value, dict)
            or type(value.get("version")) is not int or value["version"] not in (1, 2)
            or set(value) != ({"version", "runId", "argv", "workspace", "allowedRoot",
                              "timeout", "stopGrace", "bindings"}
                             | ({"inspection"} if value["version"] == 2 else set()))
            or not isinstance(value["runId"], str)
            or len(value["runId"]) != 32
            or any(c not in "0123456789abcdef" for c in value["runId"])
            or not isinstance(value["argv"], list) or not value["argv"]
            or not all(isinstance(v, str) for v in value["argv"])
            or not Path(value["argv"][0]).is_absolute()
            or type(value["timeout"]) not in (int, float)
            or not .05 <= value["timeout"] <= 3600
            or type(value["stopGrace"]) not in (int, float)
            or not .05 <= value["stopGrace"] <= 10):
        raise ValueError("INSPECTION_DESCRIPTOR_PROTOCOL")
    if (not isinstance(value["bindings"], dict)
            or value["bindings"] != bindings(value["argv"][0])):
        raise ValueError("INSPECTION_BINDINGS_CHANGED")
    primitive, watch = load_sibling("native_inspection"), load_sibling("project_watch")
    work, identity = primitive.owned_directory(value["workspace"], value["allowedRoot"])
    if list(work.iterdir()) or work == path or work in path.parents:
        raise ValueError("INSPECTION_WORKSPACE_NOT_EMPTY_OR_DESCRIPTOR_WRITABLE")
    if any(work == Path(p) or work in Path(p).parents for p in value["bindings"]):
        raise ValueError("INSPECTION_TRUSTED_INPUT_WRITABLE")
    inspection = inspection_mode(value, primitive, work)
    pipe_stat = os.fstat(control_fd)
    if (control_fd < 3 or not stat.S_ISFIFO(pipe_stat.st_mode)
            or fcntl.fcntl(control_fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_WRONLY):
        raise ValueError("INSPECTION_CONTROL_PIPE_REQUIRED")
    os.set_inheritable(control_fd, False)
    poll = selectors.DefaultSelector()
    counts = {"stdout": 0, "stderr": 0}
    closed = {"stdout": False, "stderr": False}
    current = None
    started = time.monotonic()

    def emit(event, sequence, **fields):
        row = {"runId": value["runId"], "guardianPid": os.getpid(),
               "parentPid": expected_parent, "sequence": sequence, "event": event, **fields}
        raw = json.dumps(row, separators=(",", ":")).encode() + b"\n"
        if len(raw) > MAX_RECORD_BYTES:
            raise ValueError("INSPECTION_CONTROL_RECORD_LIMIT")
        if os.write(control_fd, raw) != len(raw):
            raise ValueError("INSPECTION_CONTROL_SHORT_WRITE")

    def start(argv):
        nonlocal current
        emit("launch-pending", 0)
        # Pending is emitted BEFORE any native spawn. A crash here leaves an
        # incomplete lifecycle and must retain the reservation in any consumer.
        if digest(path) != expected_sha or not check_bindings(value["bindings"]):
            raise ValueError("INSPECTION_BINDINGS_CHANGED")
        launch = primitive.launch_strict if inspection is not None else primitive.launch
        options = {"driver_lock": inspection["driverLock"]} if inspection is not None else {}
        current, _ = launch(argv[0], argv[1:], workspace=work,
                            allowed_root=value["allowedRoot"], **options)
        try:
            current.stdin.close()
            for name in ("stdout", "stderr"):
                stream = getattr(current, name)
                os.set_blocking(stream.fileno(), False)
                poll.register(stream, selectors.EVENT_READ, name)
            group = os.getpgid(current.pid)
            if group != current.pid:
                raise ValueError("INSPECTION_PAYLOAD_GROUP")
            emit("payload-started", 1, pid=current.pid, pgid=group)
            return current
        except BaseException:
            watch.stop(current, grace=value["stopGrace"])
            raise

    def drain(child):
        for key, _ in poll.select(0):
            chunk = os.read(key.fd, 65536)
            name = key.data
            if not chunk:
                poll.unregister(key.fileobj)
                key.fileobj.close()
                closed[name] = True
                continue
            counts[name] += len(chunk)
            if counts[name] > OUTPUT_LIMIT:
                raise ValueError("INSPECTION_DATA_OUTPUT_LIMIT")
            getattr(sys, name).buffer.write(chunk)
            getattr(sys, name).buffer.flush()
        # Closing data streams early is not process completion.
        if time.monotonic() - started > value["timeout"]:
            raise subprocess.TimeoutExpired(value["argv"], value["timeout"])

    def finish(child):
        try:
            child = child if child is not None else current
            if child is None:
                return
            if child.poll() is None:
                raise ValueError("INSPECTION_PAYLOAD_STOP_UNCONFIRMED")
            # No fork is permitted; after reaping this process, no ordinary
            # descendant can keep a stream open. Refuse rather than wait forever.
            while poll.get_map():
                before = len(poll.get_map())
                drain(child)
                if len(poll.get_map()) == before and not poll.select(.05):
                    raise ValueError("INSPECTION_DATA_STREAM_UNCONFIRMED")
            try:
                mode_unchanged = inspection_mode(value, primitive, work) == inspection
            except (OSError, ValueError):
                mode_unchanged = False
            unchanged = (mode_unchanged and digest(path) == expected_sha and check_bindings(value["bindings"])
                         and primitive.owned_directory(work, value["allowedRoot"])[1] == identity)
            emit("payload-stopped", 2, pid=child.pid, pgid=child.pid,
                 returncode=child.returncode, stdoutClosed=closed["stdout"],
                 stderrClosed=closed["stderr"], bindingsUnchanged=unchanged)
        finally:
            poll.close()
            os.close(control_fd)

    return watch.guard(value["argv"], child_factory=start, tick=drain,
                       finished=finish, expected_parent=expected_parent,
                       stop_grace=value["stopGrace"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", required=True)
    parser.add_argument("--descriptor-sha", required=True)
    parser.add_argument("--control-fd", required=True, type=int)
    parser.add_argument("--expected-parent", required=True, type=int)
    args = parser.parse_args()
    try:
        return run_guardian(args.descriptor, args.descriptor_sha,
                            args.control_fd, args.expected_parent)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("refused-native-inspection: " + str(error), file=sys.stderr, flush=True)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
