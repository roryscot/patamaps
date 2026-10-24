#!/usr/bin/env python3
"""Foreground retained builds. Rust owns capture, admission, execution and selection."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time


def event(status, **fields):
    print(json.dumps(dict(status=status, **fields), separators=(",", ":")), flush=True)


def signal_group(pid, signum):
    """Darwin may return EPERM after the owned group has already disappeared."""
    try:
        os.killpg(pid, signum)
    except ProcessLookupError:
        pass
    except PermissionError:
        if sys.platform != "darwin":
            raise
        result = subprocess.run(["/bin/ps", "-axo", "pgid=,stat="],
                                check=True, capture_output=True, text=True, timeout=5)
        rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
        if not rows or any(len(row) != 2 for row in rows):
            raise
        if any(int(group) == pid and not state.startswith("Z") for group, state in rows):
            raise


def stop(child, grace=10):
    """Stop only our child's ordinary process group; preserve all outputs."""
    if child is None:
        return
    signal_group(child.pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(.05)
    # The leader can have exited while ordinary descendants remain.
    signal_group(child.pid, signal.SIGKILL)
    child.wait()


def guard(argv, cleanup=None):
    """Watch the actual spawning parent, including after its SIGKILL.

    Used around the policy runner and inside it around the native CLI. The
    second instance handles a runner that exits without stopping its child.
    """
    parent = os.getppid()
    # The policy runner need not detach its child. Keep this guardian outside
    # its group so outer cleanup cannot kill it before it stops the build.
    if os.getpgrp() != os.getpid():
        os.setsid()
    cancelled = False

    def cancel(signum, frame):
        nonlocal cancelled
        cancelled = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, cancel)
    child = None
    try:
        if parent == 1:
            return 130
        child = subprocess.Popen(argv, start_new_session=True)
        while True:
            if cancelled or os.getppid() != parent:
                event("cancelled-project-watch-update", parentExited=os.getppid() != parent)
                return 130
            code = child.poll()
            if code is not None:
                return code if code >= 0 else 128 - code
            time.sleep(.05)
    finally:
        # Docker workloads outlive their attach CLI. Stop the owned container
        # before group cleanup can terminate the guardian or attach process.
        try:
            if cleanup is not None:
                cleanup()
        finally:
            stop(child)


def container_guard(path):
    """Internal opt-in managed-container attachment; never remove owned objects."""
    from deployment_miniserve_image import stop_owned
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("CONTAINER_OWNERSHIP_FILE")
    frozen = path.read_bytes()
    owned = json.loads(frozen)
    token = owned.get("token")
    items = owned.get("containers")
    if not isinstance(token, str) or not re.fullmatch("[0-9a-f]{32}", token):
        raise ValueError("CONTAINER_OWNERSHIP_TOKEN")
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("CONTAINER_OWNERSHIP_SINGLE_ID")
    identity = items[0].get("id")
    if not isinstance(identity, str) or not re.fullmatch("[0-9a-f]{64}", identity):
        raise ValueError("CONTAINER_OWNERSHIP_ID")
    info = json.loads(subprocess.check_output(["docker", "inspect", identity], timeout=15))[0]
    if info["Config"].get("Labels", {}).get("org.patamaps.qualification-owner") != token:
        raise ValueError("CONTAINER_OWNERSHIP_LABEL")
    state = info["State"]
    if state["Running"] or state["Status"] != "created" or not state["StartedAt"].startswith("0001-"):
        raise ValueError("CONTAINER_ALREADY_STARTED")

    def cleanup():
        if path.is_symlink() or path.read_bytes() != frozen:
            raise ValueError("CONTAINER_OWNERSHIP_CHANGED")
        # Rechecks the immutable ID and live Docker owner label before stopping.
        stop_owned(path)

    return guard(["docker", "start", "--attach", identity], cleanup=cleanup)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--context", type=Path, help="Explicit sealed context binding for each native update")
    parser.add_argument("--preparation", type=Path, help="Explicit owner preparation contract for each update")
    parser.add_argument("--poll-ms", type=int, default=1000)
    parser.add_argument("--debounce-ms", type=int, default=300)
    parser.add_argument("--inspection-timeout-ms", type=int, default=30000,
                        help="Per native input/selection inspection budget (1000..3600000; default 30000)")
    parser.add_argument("--runner", nargs=argparse.REMAINDER,
                        help="Explicit policy command prefix; place last, including its -- separator")
    argv = sys.argv[1:]
    runner = None
    if "--runner" in argv:
        split = argv.index("--runner")
        runner, argv = argv[split + 1:], argv[:split]
        if not runner:
            parser.error("--runner requires an executable")
    args = parser.parse_args(argv)
    args.runner = runner
    if not 50 <= args.poll_ms <= 60000 or not 0 <= args.debounce_ms <= 60000:
        parser.error("poll-ms must be 50..60000 and debounce-ms 0..60000")
    if not 1000 <= args.inspection_timeout_ms <= 3600000:
        parser.error("inspection-timeout-ms must be 1000..3600000")
    for name in ("plan", "source", "state", "compiler"):
        setattr(args, name, getattr(args, name).absolute())
    if args.context is not None:
        args.context = args.context.absolute()
    if args.preparation is not None:
        args.preparation = args.preparation.absolute()
    if not args.runner:
        node, supervisor = os.environ.get("PATAMAPS_DEV_NODE"), os.environ.get("PATAMAPS_DEV_SUPERVISOR")
        if node and supervisor:
            args.runner = [node, supervisor, "patamaps", "--"]
        else:
            parser.error("an explicit storage/policy runner is required")
    if not Path(args.runner[0]).is_absolute():
        parser.error("runner executable must be absolute")
    # A watch started inside an allocating lease would monopolize the slot.
    if os.environ.get("WARGAME_STORAGE_RUN_TOKEN"):
        parser.error("START_WATCH_OUTSIDE_HEAVY_LEASE: each update acquires its own lease")
    return args


def observe(args):
    argv = [str(args.compiler), "project-build-input-key", str(args.plan), "--source", str(args.source)]
    if args.context is not None:
        argv.extend(["--context", str(args.context)])
    if args.preparation is not None:
        argv.extend(["--preparation", str(args.preparation)])
    result = subprocess.run(
        argv,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.inspection_timeout_ms / 1000, check=False)
    if len(result.stdout) > 1048576 or len(result.stderr) > 65536:
        raise ValueError("BUILD_INPUT_OBSERVATION_OUTPUT_LIMIT")
    if result.returncode:
        raise ValueError("BUILD_INPUT_OBSERVATION_REFUSED: " + result.stderr.decode("utf-8", errors="replace")[:2000])
    value = json.loads(result.stdout)
    if value.get("status") != "observed-project-build-inputs" or value.get("commandsExecuted") is not False:
        raise ValueError("BUILD_INPUT_OBSERVATION_PROTOCOL")
    key = value.get("inputKey")
    if not isinstance(key, str) or not key.startswith("sha256:") or len(key) != 71:
        raise ValueError("BUILD_INPUT_OBSERVATION_KEY")
    return key


def verified_selection(args):
    result = subprocess.run(
        [str(args.compiler), "project-build-verify", str(args.state)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.inspection_timeout_ms / 1000, check=False)
    if result.returncode or len(result.stdout) > 1048576 or len(result.stderr) > 65536:
        raise ValueError("WATCH_SELECTED_BINDINGS_REFUSED")
    value = json.loads(result.stdout)
    if value.get("status") != "verified-selected-build-bindings" or value.get("inputKey") != observe(args):
        raise ValueError("WATCH_SELECTION_DOES_NOT_MATCH_CURRENT_INPUTS")
    return value


def selection(state):
    try:
        return (state / "selected.json").read_bytes()
    except FileNotFoundError:
        return None


def main():
    args = arguments()
    script = Path(__file__).resolve()
    driver = hashlib.sha256(script.read_bytes()).digest()
    parent = os.getppid()
    observed = attempted = problem = None
    since = None
    child = None

    def cancel(signum, frame):
        raise KeyboardInterrupt()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, cancel)
    event("watching-project-build", source=str(args.source), state=str(args.state),
          idleLeaseHeld=False, failedKeysRetried=False)
    try:
        while True:
            if parent == 1 or os.getppid() != parent:
                raise KeyboardInterrupt()
            if hashlib.sha256(script.read_bytes()).digest() != driver:
                raise ValueError("WATCH_DRIVER_CHANGED_RESTART_REQUIRED")
            try:
                key = observe(args)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                detail = str(error)
                if detail != problem:
                    event("unavailable-project-build-inputs", reason=detail, verification="not-performed")
                    problem = detail
                # Invalidate debounce; restoring a previously attempted key does not retry it.
                observed, since = None, None
                time.sleep(args.poll_ms / 1000)
                continue
            problem = None
            if key != observed:
                observed, since = key, time.monotonic()
                event("observed-project-build-change", inputKey=key)
            if key != attempted and since is not None and time.monotonic() - since >= args.debounce_ms / 1000:
                if os.getppid() != parent:
                    raise KeyboardInterrupt()
                attempted = key
                before = selection(args.state)
                # Guard both sides of policy runner. Neither wrapper replaces Rust validation.
                native = [str(args.compiler), "project-build", str(args.plan),
                          "--source", str(args.source), "--state", str(args.state)]
                if args.context is not None:
                    native.extend(["--context", str(args.context)])
                if args.preparation is not None:
                    native.extend(["--preparation", str(args.preparation)])
                inner = [sys.executable, str(script), "__guard", *native]
                argv = [sys.executable, str(script), "__guard", *args.runner, *inner]
                event("starting-project-build-update", inputKey=key)
                try:
                    child = subprocess.Popen(argv, start_new_session=True)
                    while child.poll() is None:
                        if os.getppid() != parent:
                            raise KeyboardInterrupt()
                        time.sleep(.05)
                    code = child.returncode
                finally:
                    stop(child)
                    child = None
                if code:
                    event("refused-project-build-update", inputKey=key, exitCode=code,
                          previousSelectionPreserved=selection(args.state) == before,
                          retry="after-input-change-or-explicit-restart")
                else:
                    try:
                        checked = verified_selection(args)
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        event("refused-project-build-update", inputKey=key, exitCode=1,
                              reason=str(error), previousSelectionPreserved=selection(args.state) == before,
                              retry="after-input-change-or-explicit-restart")
                    else:
                        event("completed-project-build-update", inputKey=checked["inputKey"],
                              observedInputKey=key, selectedBindings="verified",
                              runtime="only-native-build-report-establishes-command-execution",
                              readiness="only-owner-declared-verification")
                since = None
            time.sleep(args.poll_ms / 1000)
    finally:
        stop(child)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "__guard":
        if len(sys.argv) < 3:
            raise SystemExit(2)
        raise SystemExit(guard(sys.argv[2:]))
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "__guard-container":
            if len(sys.argv) != 3:
                raise SystemExit(2)
            raise SystemExit(container_guard(sys.argv[2]))
        main()
    except KeyboardInterrupt:
        event("cancelled-project-watch")
        raise SystemExit(130)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        event("refused-project-watch", reason=str(error))
        raise SystemExit(1)
