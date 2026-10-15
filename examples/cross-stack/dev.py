"""Foreground development preview with retained candidates and atomic selection.

A selected preview passed source admission, native-host compilation, Next build
and real generated-client HTTP checks. Linux image/browser release acceptance is
a separate required lane. No registry publication or activation occurs here.
"""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
import os
import platform
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import build
import workspace

EXCLUDED = {"node_modules", ".next", "target", "runs", ".patamaps", "generated", "__pycache__", ".git"}
GENERATED = {"generated.rs", "next-env.d.ts", "tsconfig.tsbuildinfo"}


def declared_source(args):
    raw = (args.source / "contracts/operations.json").read_bytes()
    if len(raw) > 65536:
        raise build.BuildError("OWNER_MANIFEST_LIMIT")
    checked = subprocess.run([str(args.compiler), "json", "parse"], input=raw, capture_output=True, timeout=10, check=True)
    if json.loads(checked.stdout).get("nonsecretInputs") is not True:
        raise build.BuildError("CROSS_STACK_NONSECRET_DECLARATION_REQUIRED")


def programs(args):
    paths = {"compiler": args.compiler, "cargo": args.cargo, "rustc": args.rustc, "node": args.node,
             "next": args.source / "web/node_modules/next/dist/bin/next", "typescript": args.source / "web/node_modules/typescript/lib/typescript.js",
             "rustfmt": args.rustc.resolve().parent / "rustfmt"}
    for folder in [args.repository / "adapters", args.repository / "sdk/typescript"]:
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in {".js", ".mjs", ".json"}:
                paths["repository:" + path.relative_to(args.repository).as_posix()] = path
    for path in [Path(__file__).resolve(), Path(build.__file__).resolve(), Path(workspace.__file__).resolve()]:
        paths["driver:" + path.name] = path
    return paths


def inventory(root):
    result = {}
    total = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(v for v in dirs if v not in EXCLUDED)
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise build.BuildError("SOURCE_DIRECTORY_SYMLINK")
        for name in sorted(names):
            if name in GENERATED:
                continue
            path = Path(directory) / name
            if path.is_symlink() or name == ".env" or name.startswith(".env."):
                raise build.BuildError("SOURCE_INPUT_UNAVAILABLE: " + str(path.relative_to(root)))
            raw = path.read_bytes()
            total += len(raw)
            if total > 16777216:
                raise build.BuildError("SOURCE_INPUT_LIMIT")
            result[path.relative_to(root).as_posix()] = build.digest(raw)
    return result


def copy_tree(source, destination):
    source = Path(source).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if platform.system() == "Darwin":
        subprocess.run(["/bin/cp", "-cR", str(source), str(destination)], check=True)
    else:
        shutil.copytree(source, destination)


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


@contextmanager
def servers(candidate, executable, node, env, logs):
    out_path = logs / "service.stdout.log"
    with out_path.open("xb") as out, (logs / "service.stderr.log").open("xb") as err:
        service = subprocess.Popen([str(executable), str(candidate / "app/config/service.toml"), "127.0.0.1:0"],
                                   cwd=candidate, env=env, stdout=out, stderr=err, start_new_session=True)
        frontend = None
        try:
            deadline = time.monotonic() + 20
            backend = None
            while time.monotonic() < deadline:
                backend = next(("http://" + line.removeprefix("LISTEN ") for line in out_path.read_text().splitlines() if line.startswith("LISTEN 127.0.0.1:")), None)
                if backend:
                    break
                if service.poll() is not None:
                    raise build.BuildError("SERVICE_START_FAILED")
                time.sleep(.05)
            if backend is None:
                raise build.BuildError("SERVICE_START_TIMEOUT")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            with (logs / "next.stdout.log").open("xb") as next_out, (logs / "next.stderr.log").open("xb") as next_err:
                web = candidate / "app/web"
                frontend = subprocess.Popen([str(node), str(web / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(port)],
                                            cwd=web, env=dict(env, CATALOG_SERVICE_URL=backend), stdout=next_out, stderr=next_err, start_new_session=True)
                base = "http://127.0.0.1:" + str(port)
                deadline = time.monotonic() + 20
                while True:
                    try:
                        with urlopen(base, timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    if frontend.poll() is not None or time.monotonic() >= deadline:
                        raise build.BuildError("NEXT_START_FAILED")
                    time.sleep(.05)
                yield base, backend
        finally:
            if frontend is not None:
                stop(frontend)
            stop(service)


def pointer_valid(pointer):
    if build.digest(Path(pointer["receipt"]).read_bytes()) != pointer["receiptDigest"]:
        raise build.BuildError("SELECTED_VERIFICATION_RECEIPT_CHANGED")
    for path, expected in pointer["outputs"].items():
        if build.digest(Path(path).read_bytes()) != expected:
            raise build.BuildError("SELECTED_OUTPUT_CHANGED: " + path)


def update(args, force=False):
    source = args.source.resolve()
    state = args.state.resolve()
    if state.is_relative_to(source):
        raise build.BuildError("DEVELOPMENT_STATE_MUST_BE_OUTSIDE_SOURCE")
    state.mkdir(parents=True, exist_ok=True)
    with (state / "driver.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise build.BuildError("DEVELOPMENT_DRIVER_ALREADY_RUNNING")
        declared_source(args)
        before = inventory(source)
        paths = programs(args)
        for name in ["compiler", "cargo", "rustc", "node", "rustfmt"]:
            if not os.access(paths[name], os.X_OK):
                raise build.BuildError("TOOL_UNAVAILABLE: " + name)
        tools = {name: build.digest(path.resolve(strict=True).read_bytes()) for name, path in paths.items()}
        context_keys = ["PATH", "RUSTUP_TOOLCHAIN", "DEVELOPER_DIR", "CARGO_HOME", "RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS"]
        context_digest = build.digest(json.dumps({name: os.environ.get(name) for name in context_keys}, sort_keys=True).encode())
        key = build.digest(json.dumps({"inputs": before, "tools": tools, "contextDigest": context_digest, "mode": "native-preview-1"}, sort_keys=True, separators=(",", ":")).encode())
        selected = state / "selected.json"
        if selected.exists() and not force:
            pointer = json.loads(selected.read_bytes())
            pointer_valid(pointer)
            if pointer["inputKey"] == key:
                return {"status": "unchanged", "verification": "not-repeated", "cacheHits": 0, "selected": str(selected), "fullReleaseAccepted": False}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        attempt = state / "attempts" / stamp
        attempt.mkdir(parents=True, exist_ok=False)
        logs = attempt / "logs"
        logs.mkdir()
        began = time.monotonic()
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        commands = []
        env = dict(os.environ, CARGO_INCREMENTAL="0", CARGO_BUILD_JOBS="2", RUST_TEST_THREADS="1", NEXT_TELEMETRY_DISABLED="1",
                   RUSTC=str(args.rustc), CARGO_PROFILE_DEV_DEBUG="0", CARGO_PROFILE_TEST_DEBUG="0",
                   CARGO_TARGET_DIR=str(state / "cargo-target"), NODE_OPTIONS="--max-old-space-size=2048")
        receipt = {"status": "running", "inputKey": key, "tools": tools, "contextDigest": context_digest, "commands": commands,
                   "completeExecutableDependencyClosureEstablished": False, "fullReleaseAccepted": False, "activation": "not-performed"}
        published = False

        def save():
            (attempt / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

        def run(label, argv, cwd=attempt, input_bytes=None, timeout=300):
            save()
            command = {"label": label, "argv": [str(v) for v in argv], "status": "running"}
            commands.append(command)
            with (logs / (label + ".stdout.log")).open("xb") as out, (logs / (label + ".stderr.log")).open("xb") as err:
                process = subprocess.Popen([str(v) for v in argv], cwd=cwd, env=env, stdout=out, stderr=err,
                                           stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL, start_new_session=True)
                start = time.monotonic()
                command["pid"] = process.pid
                save()
                try:
                    process.communicate(input=input_bytes, timeout=timeout)
                finally:
                    stop(process)
                    command.update(status="finished", exitCode=process.returncode, seconds=round(time.monotonic() - start, 3))
                    save()
            command.update(stdoutDigest=build.digest((logs / (label + ".stdout.log")).read_bytes()),
                           stderrDigest=build.digest((logs / (label + ".stderr.log")).read_bytes()))
            save()
            if process.returncode:
                raise build.BuildError(label + " failed; retained logs: " + str(logs))
            return (logs / (label + ".stdout.log")).read_bytes()

        try:
            candidate = attempt / "candidate"
            owner, config, policy, generated = workspace.prepare(args.repository, source, candidate, args.compiler, args.node, args.cargo, args.rustc, run)
            captured = inventory(candidate / "app")
            if captured != before or inventory(source) != before:
                raise build.BuildError("SOURCE_CHANGED_DURING_SNAPSHOT")
            workspace.bind(candidate, args.compiler, owner, config, policy, run)
            copy_tree(source / "web/node_modules", candidate / "app/web/node_modules")
            service = candidate / "app/service/Cargo.toml"
            run("cargo-tests", [args.cargo, "test", "--manifest-path", service, "--locked", "--offline"])
            run("cargo-build", [args.cargo, "build", "--manifest-path", service, "--bin", owner["operations"][0]["cargo"]["target"], "--locked", "--offline"])
            executable = attempt / "catalog-service.native-preview"
            shutil.copy2(state / "cargo-target/debug/catalog-service", executable)
            web = candidate / "app/web"
            run("next-build", [args.node, web / "node_modules/next/dist/bin/next", "build", "--webpack"], cwd=web)
            run("next-typecheck", [args.node, web / "node_modules/typescript/lib/tsc.js", "--noEmit"], cwd=web)
            run("client-compile", [args.node, web / "node_modules/typescript/lib/tsc.js", "--target", "ES2022", "--module", "commonjs", "--lib", "ES2022,DOM", "--strict", "--skipLibCheck", "--outDir", attempt / "client-js", web / "generated/operations.ts"])
            with servers(candidate, executable, args.node, env, logs) as (frontend, backend):
                wire = json.loads(run("runtime-contract", [args.node, candidate / "app/acceptance/check-runtime.cjs", attempt / "client-js/operations.js", frontend, backend]))
            if inventory(source) != before or inventory(candidate / "app") != before:
                raise build.BuildError("SOURCE_CHANGED_BEFORE_SELECTION")
            if build.digest(json.dumps({name: os.environ.get(name) for name in context_keys}, sort_keys=True).encode()) != context_digest:
                raise build.BuildError("TOOL_CONTEXT_CHANGED_BEFORE_SELECTION")
            if any(build.digest(path.resolve(strict=True).read_bytes()) != tools[name] for name, path in paths.items()):
                raise build.BuildError("TOOL_CHANGED_BEFORE_SELECTION")
            output_paths = [candidate / "app/service/src/generated.rs", candidate / "app/web/generated/operations.ts", candidate / "generated/operations.json"]
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            receipt.update(status="verified-native-preview", runtime=wire, seconds=round(time.monotonic() - began, 3),
                           resource={"childCpuUserSeconds": usage.ru_utime - usage_before.ru_utime,
                                     "childCpuSystemSeconds": usage.ru_stime - usage_before.ru_stime,
                                     "childMaxRss": usage.ru_maxrss, "rssUnits": "bytes" if platform.system() == "Darwin" else "KiB",
                                     "rssScope": "reported child high-water mark for driver lifetime; not whole-tree peak"},
                           compilation={"hostSystem": platform.system(), "hostMachine": platform.machine(), "profile": "dev", "linuxTargetEstablished": False},
                           linuxImage="not-evaluated", browser="not-evaluated")
            save()
            pointer = {"profile": "patamaps-development-preview-1", "inputKey": key, "candidate": str(candidate), "receipt": str(attempt / "receipt.json"),
                       "receiptDigest": build.digest((attempt / "receipt.json").read_bytes()),
                       "outputs": {str(p): build.digest(p.read_bytes()) for p in [*output_paths, executable, web / ".next/BUILD_ID"]},
                       "fullReleaseAccepted": False, "selectedUtc": datetime.now(timezone.utc).isoformat()}
            history = state / "selection-history"
            history.mkdir(exist_ok=True)
            if selected.exists():
                shutil.copyfile(selected, history / (stamp + ".previous.json"))
            temporary = state / ("selected-" + stamp + ".candidate.json")
            with temporary.open("x") as out:
                out.write(json.dumps(pointer, indent=2) + "\n")
                out.flush()
                os.fsync(out.fileno())
            previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            try:
                os.replace(temporary, selected)
                published = True
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            directory_fd = os.open(state, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return {"status": receipt["status"], "selected": str(selected), "candidate": str(candidate), "seconds": receipt["seconds"], "fullReleaseAccepted": False}
        except BaseException as error:
            if published:
                with (attempt / "post-selection-event.json").open("x") as out:
                    out.write(json.dumps({"event": type(error).__name__, "reason": str(error), "selection": "complete-verified-candidate", "publicationDurability": "unconfirmed-after-event"}, indent=2) + "\n")
            else:
                receipt.update(status="cancelled" if isinstance(error, KeyboardInterrupt) else "refused", reason=str(error), seconds=round(time.monotonic() - began, 3))
                save()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--state", type=Path, required=True)
    for name in ["compiler", "cargo", "rustc", "node"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--debounce-ms", type=int, default=500)
    parser.add_argument("--runner", nargs=argparse.REMAINDER, help="Optional per-update supervisor command; put this option last")
    args = parser.parse_args()
    if not 50 <= args.debounce_ms <= 10000:
        parser.error("--debounce-ms must be between 50 and 10000")
    for name in ["compiler", "cargo", "rustc", "node", "source", "repository", "state"]:
        setattr(args, name, getattr(args, name).absolute())
    driver_files = [Path(__file__).resolve(), Path(build.__file__).resolve(), Path(workspace.__file__).resolve()]
    driver_bytes = [p.read_bytes() for p in driver_files]
    previous = None
    pending_since = None
    last_problem = None
    if args.watch and os.environ.get("PATAMAPS_DEV_SUPERVISOR"):
        sys.path.insert(0, str(args.repository / "scripts/parity"))
        from storage_guard import live_parent
        if live_parent():
            raise build.BuildError("START_WATCH_OUTSIDE_HEAVY_LEASE: each update acquires its own lease")
        if not args.runner:
            args.runner = [os.environ["PATAMAPS_DEV_NODE"], os.environ["PATAMAPS_DEV_SUPERVISOR"], "patamaps", "--"]
    while True:
        def file_state(path):
            try:
                stat = path.stat()
                return [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_mode]
            except FileNotFoundError:
                return None
        try:
            declared_source(args)
            observed = {"source": inventory(args.source), "tools": {str(path): file_state(path) for path in programs(args).values()}}
        except (build.BuildError, OSError, subprocess.SubprocessError) as error:
            problem = str(error)
            if problem != last_problem:
                print(json.dumps({"status": "unavailable-input", "reason": problem, "verification": "not-performed"}), flush=True)
                last_problem = problem
            if not args.watch:
                raise SystemExit(1)
            time.sleep(.2)
            continue
        last_problem = None
        if any(p.read_bytes() != raw for p, raw in zip(driver_files, driver_bytes)):
            raise build.BuildError("DRIVER_CHANGED_RESTART_REQUIRED")
        if observed != previous:
            previous = observed
            pending_since = time.monotonic()
        if not args.watch or pending_since is not None and time.monotonic() - pending_since >= args.debounce_ms / 1000:
            try:
                selection_file = args.state / "selected.json"
                previous_selection = selection_file.read_bytes() if selection_file.exists() else None
                if args.runner:
                    command = [*args.runner, sys.executable, str(Path(__file__).resolve())]
                    for name in ["source", "repository", "state", "compiler", "cargo", "rustc", "node"]:
                        command += ["--" + name, str(getattr(args, name))]
                    if args.force:
                        command.append("--force")
                    process = subprocess.Popen(command, start_new_session=True)
                    try:
                        result = process.wait()
                    finally:
                        stop(process)
                    if result == 75 and args.watch:
                        pending_since = time.monotonic()
                        time.sleep(1)
                        continue
                    if result:
                        raise build.BuildError("SUPERVISED_UPDATE_REFUSED: " + str(result))
                else:
                    print(json.dumps(update(args, args.force)), flush=True)
            except (build.BuildError, OSError, subprocess.SubprocessError) as error:
                now_selection = selection_file.read_bytes() if selection_file.exists() else None
                print(json.dumps({"status": "refused", "reason": str(error), "previousSelectionPreserved": now_selection == previous_selection}), flush=True)
                if not args.watch:
                    raise SystemExit(1)
            pending_since = None
            if not args.watch:
                return
        time.sleep(.2)


if __name__ == "__main__":
    def interrupted(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled"}), flush=True)
        raise SystemExit(130)
    except (build.BuildError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "refused", "reason": str(error)}), flush=True)
        raise SystemExit(1)
