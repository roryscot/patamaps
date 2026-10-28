"""Proposed trusted adapter for bounded, single-process native inspections.

This preserves the existing watcher guardian. Its private lifecycle pipe is
separate from payload data, but is NOT an installed supervisor attestation.
The caller must still hold the ordinary exclusive reservation. No release
predicate, concurrency policy or arbitrary-build executor is installed here.
"""
from pathlib import Path
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import selectors
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


def validate_records(records, run_id, guardian_pid):
    """Closed lifecycle grammar. Stdout is never an input to this parser."""
    common = {"runId", "guardianPid", "parentPid", "sequence", "event"}
    schemas = [common, common | {"pid", "pgid"},
               common | {"pid", "pgid", "returncode", "stdoutClosed", "stderrClosed",
                         "bindingsUnchanged"}]
    events = ["launch-pending", "payload-started", "payload-stopped"]
    if len(records) != 3:
        raise ValueError("INSPECTION_CONTROL_INCOMPLETE")
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
    start, end = records[1:]
    if (type(start["pid"]) is not int or start["pid"] <= 1
            or type(start["pgid"]) is not int or start["pgid"] != start["pid"]
            or type(end["pid"]) is not int or type(end["pgid"]) is not int
            or end["pid"] != start["pid"] or end["pgid"] != start["pgid"]
            or type(end["returncode"]) is not int
            or any(end[k] is not True for k in
                   ["stdoutClosed", "stderrClosed", "bindingsUnchanged"])):
        raise ValueError("INSPECTION_STOP_UNCONFIRMED")
    return end


class InspectionRunner:
    """subprocess.run-shaped adapter for existing read-only watcher functions.

    Each invocation retains its descriptor, raw data and control records.
    The descriptor hashes are caller bindings, not registry authorization.
    """
    def __init__(self, root, allowed_root, *, stop_grace=2):
        primitive = load_sibling("native_inspection")
        self.root, _ = primitive.owned_directory(root, allowed_root)
        self.allowed_root = Path(allowed_root)
        if not .05 <= stop_grace <= 10:
            raise ValueError("INSPECTION_STOP_GRACE")
        self.stop_grace = stop_grace
        self.calls = []

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
        read_fd, write_fd = os.pipe()
        expected_sha = digest(path)
        child = None
        out = err = b""
        records = []
        try:
            child = self.spawn(path, descriptor, write_fd)
        finally:
            os.close(write_fd)
            if child is None:
                os.close(read_fd)
        try:
            try:
                out, err = child.communicate(timeout=timeout + self.stop_grace + 10)
            except BaseException:
                # The guardian handles the actual parent, but orderly caller
                # cancellation first gives it time to stop its separate group.
                watch = load_sibling("project_watch")
                watch.stop(child, grace=self.stop_grace + 2)
                raise
            os.set_blocking(read_fd, False)
            raw = bytearray()
            eof = False
            while True:
                try:
                    chunk = os.read(read_fd, MAX_RECORD_BYTES)
                except BlockingIOError:
                    break
                if not chunk:
                    eof = True
                    break
                raw.extend(chunk)
                if len(raw) > 3 * MAX_RECORD_BYTES:
                    raise ValueError("INSPECTION_CONTROL_OUTPUT_LIMIT")
            if not eof:
                raise ValueError("INSPECTION_CONTROL_STILL_OPEN")
            records = [json.loads(line) for line in raw.splitlines()]
            end = validate_records(records, descriptor["runId"], child.pid)
            if not check_bindings(descriptor["bindings"]) or digest(path) != expected_sha:
                raise ValueError("INSPECTION_BINDINGS_CHANGED")
            # A guardian cancellation/failure is never converted to payload success.
            code = child.returncode
            expected_code = (end["returncode"] if end["returncode"] >= 0
                             else 128 - end["returncode"])
            if code not in (expected_code, 130):
                raise ValueError("INSPECTION_GUARDIAN_REFUSED")
            if code == 0 and end["returncode"] != 0:
                raise ValueError("INSPECTION_EXIT_PROTOCOL")
            return subprocess.CompletedProcess(argv, code, out, err)
        finally:
            os.close(read_fd)
            (path.parent / "stdout").write_bytes(out)
            (path.parent / "stderr").write_bytes(err)
            receipt = {"guardianPid": child.pid, "guardianExitCode": child.returncode,
                       "records": records, "automaticReservationReleaseQualified": False}
            (path.parent / "control.json").write_text(json.dumps(receipt, indent=2) + "\n")
            self.calls.append(receipt)


def run_guardian(path, expected_sha, control_fd, expected_parent):
    """Internal closed guardian entrypoint; only the native payload is untrusted."""
    path = Path(path)
    if (not path.is_absolute() or path.resolve(strict=True) != path or path.is_symlink()
            or digest(path) != expected_sha or os.getppid() != expected_parent):
        raise ValueError("INSPECTION_DESCRIPTOR_OR_PARENT_CHANGED")
    value = json.loads(path.read_text())
    if (not isinstance(value, dict)
            or set(value) != {"version", "runId", "argv", "workspace", "allowedRoot",
                             "timeout", "stopGrace", "bindings"}
            or value["version"] != 1 or type(value["version"]) is not int
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
        current, _ = primitive.launch(argv[0], argv[1:], workspace=work,
                                      allowed_root=value["allowedRoot"])
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
            unchanged = (digest(path) == expected_sha and check_bindings(value["bindings"])
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
