"""Fixed Darwin single-process inspection profile; not a reservation-release proof.

Callers provide trusted owned roots. This primitive does not install a supervisor
policy, admit concurrency, or authorize arbitrary application builds.
"""
from pathlib import Path
import hashlib
import os
import stat
import subprocess
import sys

KIND = "darwin-single-process-inspection-v1"
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
PROFILE = """(version 1)
(deny default)
(allow file-read*)
(allow file-map-executable)
(allow process-exec)
(allow process-info*)
(allow sysctl-read)
(allow signal (target self))
(allow file-write* (subpath (param "WORK")))
"""

def owned_directory(directory, allowed_root):
    directory, allowed_root = Path(directory), Path(allowed_root)
    if not directory.is_absolute() or not allowed_root.is_absolute():
        raise ValueError("Inspection roots must be absolute")
    actual, base = directory.resolve(strict=True), allowed_root.resolve(strict=True)
    if actual != directory or base != allowed_root or not actual.is_dir() or not base.is_dir():
        raise ValueError("Inspection roots must be canonical directories")
    if actual == base or base not in actual.parents or len(base.parts) < 3:
        raise ValueError("Inspection writes must stay in a strict owned subtree")
    info = actual.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("Inspection write directory must be private and user-owned")
    return actual, (info.st_dev, info.st_ino)

def launch(program, arguments, *, workspace, allowed_root, environment=None):
    if sys.platform != "darwin" or not SANDBOX_EXEC.is_file():
        raise RuntimeError("Darwin inspection isolation is unavailable")
    root, identity = owned_directory(workspace, allowed_root)
    executable = Path(program)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("Inspection program must be an existing absolute file")
    executable = executable.resolve(strict=True)
    supplied = dict(environment or {})
    if any(k.startswith(("DYLD_", "LD_", "PYTHON")) or
           k in {"BASH_ENV", "ENV", "ZDOTDIR"} for k in supplied):
        raise ValueError("Runtime injection variables are not accepted")
    env = {"PATH": "/usr/bin:/bin", "LANG": "C", **supplied,
           "TMPDIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    command = [str(SANDBOX_EXEC), "-p", PROFILE, "-D", "WORK=" + str(root),
               str(executable), *map(str, arguments)]
    # No connected inherited stdin or extra descriptors enter the restricted
    # payload. The new session leader cannot detach without creating a process;
    # the fixed profile does not permit fork/posix_spawn.
    child = subprocess.Popen(command, cwd=root, env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, close_fds=True,
                             start_new_session=True)
    requested = {"kind": KIND, "profileSha256": hashlib.sha256(PROFILE.encode()).hexdigest(),
                 "workspaceIdentity": list(identity), "pid": child.pid,
                 "stdinTransport": "pipe", "extraDescriptorsPassed": False,
                 "nativeCpuMemoryLimitsClaimed": False,
                 "automaticReservationReleaseQualified": False}
    return child, requested
