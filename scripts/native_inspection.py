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

STRICT_KIND = "darwin-single-process-inspection-v2"
LOCK_KIND = "darwin-single-process-locked-inspection-v2"
STRICT_PROFILE = """(version 1)
(deny default file-link)
(deny process-info* (target others))
(allow file-read*)
(allow file-map-executable)
(allow process-exec)
(allow process-info-pidinfo (target self))
(allow sysctl-read)
(allow signal (target self))
(allow file-write* (subpath (param "WORK")))
"""
LOCK_PROFILE = STRICT_PROFILE + '(allow file-write-data (literal (param "LOCK")))\n'


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
    """Legacy fixed profile, preserved for existing callers."""
    return _launch_fixed(program, arguments, workspace=workspace,
                         allowed_root=allowed_root, environment=environment,
                         profile=PROFILE, kind=KIND, parameters={})


def owned_driver_lock(path, workspace):
    """An existing empty single-link private lock, disjoint from all work."""
    path, workspace = Path(path), Path(workspace)
    if (not path.is_absolute() or path.resolve(strict=True) != path
            or path.name != "driver.lock"):
        raise ValueError("Inspection lock must be a canonical driver.lock")
    info = path.lstat()
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise ValueError("Inspection lock state must be private and user-owned")
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_nlink != 1 or info.st_size != 0
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise ValueError("Inspection lock must be private, empty and singly linked")
    if path.parent == workspace or path.parent in workspace.parents or workspace in path.parent.parents:
        raise ValueError("Inspection lock state and writable work must be disjoint")
    return [info.st_dev, info.st_ino]


def launch_strict(program, arguments, *, workspace, allowed_root,
                  driver_lock=None, environment=None):
    """Strict fresh-work mode; optional grant permits only lock data access."""
    if sys.platform != "darwin" or not SANDBOX_EXEC.is_file():
        raise RuntimeError("Darwin inspection isolation is unavailable")
    root, _ = owned_directory(workspace, allowed_root)
    if any(root.iterdir()):
        raise ValueError("Strict inspection workspace must be fresh and empty")
    parameters = {}
    lock_identity = None
    if driver_lock is not None:
        lock_identity = owned_driver_lock(driver_lock, root)
        parameters["LOCK"] = str(driver_lock)
    child, requested = _launch_fixed(program, arguments, workspace=root,
        allowed_root=allowed_root, environment=environment,
        profile=LOCK_PROFILE if driver_lock is not None else STRICT_PROFILE,
        kind=LOCK_KIND if driver_lock is not None else STRICT_KIND, parameters=parameters)
    requested["driverLockIdentity"] = lock_identity
    return child, requested


def _launch_fixed(program, arguments, *, workspace, allowed_root, environment,
                  profile, kind, parameters):
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
    command = [str(SANDBOX_EXEC), "-p", profile, "-D", "WORK=" + str(root)]
    for name, value in parameters.items():
        command.extend(["-D", name + "=" + value])
    command.extend([str(executable), *map(str, arguments)])
    # No connected inherited stdin or extra descriptors enter the restricted
    # payload. The new session leader cannot detach without creating a process;
    # the fixed profile does not permit fork/posix_spawn.
    child = subprocess.Popen(command, cwd=root, env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, close_fds=True,
                             start_new_session=True)
    requested = {"kind": kind, "profileSha256": hashlib.sha256(profile.encode()).hexdigest(),
                 "workspaceIdentity": list(identity), "pid": child.pid,
                 "stdinTransport": "pipe", "extraDescriptorsPassed": False,
                 "nativeCpuMemoryLimitsClaimed": False,
                 "automaticReservationReleaseQualified": False}
    return child, requested
