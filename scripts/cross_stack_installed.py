"""Run the mixed workflow from an exact retained package installation."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--mode", choices=["image", "preview"], required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (platform.system() == "Linux" and os.environ.get("GITHUB_ACTIONS") == "true"):
        # Validate the real caller's registered project and live lease. Never
        # impersonate a consumer directory as the supervisor's project root.
        guard_path = Path(os.environ.get("LOCAL_STORAGE_PROJECT", "/unavailable")) / "scripts/parity/storage_guard.py"
        spec = importlib.util.spec_from_file_location("installed_outer_storage_guard", guard_path)
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        if not guard.live_parent():
            raise RuntimeError("A live existing storage-supervisor lease is required")
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(root / "examples/cross-stack"))
    import build
    import dev
    fixture = root / "examples/cross-stack"
    env = dict(os.environ, PATAMAPS_DEV_NODE=str(args.node.resolve()), CARGO_INCREMENTAL="0", CARGO_BUILD_JOBS="2", RUST_TEST_THREADS="1",
               NEXT_TELEMETRY_DISABLED="1", NODE_OPTIONS="--max-old-space-size=2048")
    receipt = {"status": "running", "mode": args.mode, "sourceRoot": str(root), "compiler": str(args.compiler),
               "startedUtc": datetime.now(timezone.utc).isoformat(), "commands": [], "fullReleaseAccepted": False, "deleted": []}
    def save():
        (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    def run(label, argv, cwd=root, timeout=300, input_bytes=None, expected_success=True):
        entry = {"label": label, "argv": [str(v) for v in argv], "cwd": str(cwd), "expectedSuccess": expected_success}
        receipt["commands"].append(entry)
        save()
        start = time.monotonic()
        with (work / (label + ".stdout.log")).open("xb") as out, (work / (label + ".stderr.log")).open("xb") as err:
            process = subprocess.Popen(entry["argv"], cwd=cwd, env=env, stdout=out, stderr=err,
                stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL, start_new_session=True)
            entry["pid"] = process.pid
            save()
            try:
                process.communicate(input=input_bytes, timeout=timeout)
            finally:
                dev.stop(process)
                entry.update(exitCode=process.returncode, seconds=round(time.monotonic() - start, 3))
                save()
        if expected_success is not None and (process.returncode == 0) != expected_success:
            raise RuntimeError(label + " failed; candidate and command logs retained")
        return (work / (label + ".stdout.log")).read_bytes()
    inventory = json.loads((root / "source-inventory.json").read_bytes())
    def source_unchanged():
        return all("sha256:" + hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["digest"] for item in inventory)
    try:
        assert source_unchanged()
        sys.path.insert(0, str(root / "scripts/parity"))
        from identity import identities
        engine = json.loads(run("installed-engine", [args.compiler, "engine"]))
        assert engine == {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(root)}
        for label, folder in [("web", fixture / "web"), ("browser", fixture / "acceptance/browser")]:
            assert not (folder / "node_modules").exists(), "Refusing npm ci over retained dependencies"
            run("installed-" + label + "-dependencies", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=folder)
        if args.mode == "image":
            from cross_stack_release import verify
            result = verify(root, work, env, run, compiler_override=args.compiler.resolve())
            receipt["mixedWorkflow"] = result
            candidate = work / "release-candidate"
            executable = work / "image-contents/catalog-service"
            client = work / "client-js/operations.js"
        else:
            cargo = Path(run("installed-cargo", ["rustup", "which", "cargo"]).decode().strip()).resolve()
            rustc = Path(run("installed-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
            state = work / "preview-state"
            result = dev.update(argparse.Namespace(source=fixture, state=state, repository=root,
                compiler=args.compiler.resolve(), cargo=cargo, rustc=rustc, node=args.node.resolve()))
            pointer = json.loads((state / "selected.json").read_bytes())
            candidate = Path(pointer["candidate"])
            executable = candidate.parent / "catalog-service.native-preview"
            client = candidate.parent / "client-js/operations.js"
            receipt["mixedWorkflow"] = result
        # The package itself remains retained and recoverable. Rename only this
        # test installation's compiler, then exercise already-built consumers.
        unavailable = args.compiler.with_name(args.compiler.name + ".unavailable-after-generation")
        assert not unavailable.exists()
        args.compiler.rename(unavailable)
        logs = work / "runtime-without-compilers"
        logs.mkdir()
        runtime_env = dict(env, PATH=str(work / "unavailable-tools"), PATAMAPS_EXECUTABLE=str(args.compiler),
                           METAMAP_REFERENCE=str(work / "unavailable-metamap"))
        with dev.servers(candidate, executable, args.node.resolve(), runtime_env, logs) as (frontend, backend):
            wire = json.loads(run("installed-runtime-without-compilers", [args.node.resolve(), fixture / "acceptance/check-runtime.cjs", client, frontend, backend]))
            assert wire["realNextRustRoundTrip"] is True
        generated_rust = (candidate / "app/service/src/generated.rs").read_text()
        generated_ts = (candidate / "app/web/generated/operations.ts").read_text()
        assert "use patamaps" not in generated_rust and 'from "patamaps' not in generated_ts and 'from "@roryscot/metamap' not in generated_ts
        assert source_unchanged()
        receipt.update(status="passed-installed-consumer-scope", engine=engine, inventoryFilesVerified=len(inventory),
            configuredCompilerUnavailable=True, compilerRetainedAs=str(unavailable), graphCompilersOnRequestPath=False,
            runtimeAfterRename={"mode": "native-host run of inspected image ELF" if args.mode == "image" else "native preview", **wire},
            sourceInventoryUnchanged=True, activation="not-performed")
    except BaseException as error:
        receipt.update(status="failed", failure=str(error), traceback=traceback.format_exc())
        raise
    finally:
        receipt["finishedUtc"] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
