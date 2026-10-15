"""Retained development-selection controls over real native and Next builds."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from urllib.request import urlopen


def verify(root, work, env, run):
    fixture = root / "examples/cross-stack"
    sys.path.insert(0, str(fixture))
    import build
    import workspace
    spec = importlib.util.spec_from_file_location("development_driver", fixture / "dev.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    run("m5-preview-cli", ["cargo", "build", "-p", "patamaps-cli", "--release", "--locked", "--offline"], timeout=900)
    cli = root / "target/release/patamaps"
    cargo = Path(run("m5-preview-cargo", ["rustup", "which", "cargo"]).decode().strip()).resolve()
    rustc = Path(run("m5-preview-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
    node = Path(env["PATAMAPS_DEV_NODE"]).resolve()
    owner = work / "development-source"
    build.snapshot(fixture, owner)
    (owner / "web/node_modules").symlink_to(fixture / "web/node_modules", target_is_directory=True)
    state = work / "development-state"
    args = argparse.Namespace(source=owner, state=state, repository=root, compiler=cli, cargo=cargo, rustc=rustc, node=node)
    controls = []

    def selected():
        return (state / "selected.json").read_bytes()

    def attempt_count():
        return len(list((state / "attempts").glob("*")))

    def refusal(label, action):
        old = selected()
        try:
            action()
        except (build.BuildError, OSError, subprocess.SubprocessError) as error:
            assert selected() == old, label + " changed the selected generation"
            controls.append({"control": label, "result": "refused", "reason": str(error), "previousSelectionPreserved": True})
            return
        raise AssertionError(label + " unexpectedly selected a candidate")

    first = driver.update(args)
    assert first["status"] == "verified-native-preview" and first["fullReleaseAccepted"] is False
    baseline = selected()
    baseline_pointer = json.loads(baseline)
    controls.append({"control": "m5-real-preview", **first})
    attempts = attempt_count()
    unchanged = driver.update(args)
    assert unchanged["status"] == "unchanged" and unchanged["verification"] == "not-repeated" and unchanged["cacheHits"] == 0
    assert selected() == baseline and attempt_count() == attempts
    controls.append({"control": "m5-no-op", **unchanged})

    args.compiler = work / "missing-compiler"
    refusal("m5-missing-compiler", lambda: driver.update(args))
    args.compiler = cli
    request_schema = owner / "contracts/create-item.request.schema.json"
    original_schema = request_schema.read_bytes()
    request_schema.write_bytes(b'{"type":"object",' + original_schema.lstrip()[1:])
    refusal("m5-duplicate-schema-key", lambda: driver.update(args))
    request_schema.write_bytes(original_schema)

    original_snapshot = build.snapshot
    race_file = owner / "race-marker.txt"
    def racing_snapshot(source, destination):
        race_file.write_text("nonsecret transient source\n")
        result = original_snapshot(source, destination)
        race_file.rename(work / "race-marker.retained.txt")
        return result
    build.snapshot = racing_snapshot
    try:
        refusal("m5-snapshot-race", lambda: driver.update(args, force=True))
    finally:
        build.snapshot = original_snapshot

    handler = owner / "service/src/handlers/create_item.rs"
    original_handler = handler.read_text()
    assert "pub fn create_item(" in original_handler
    handler.write_text(original_handler.replace("pub fn create_item(", "pub fn missing_export("))
    refusal("m5-real-cargo-failure", lambda: driver.update(args))
    latest = sorted((state / "attempts").glob("*"))[-1]
    assert "E0425" in (latest / "logs/cargo-tests.stderr.log").read_text()
    handler.write_text(original_handler)

    # A failed update must leave a usable complete app, not just a valid pointer.
    candidate = Path(baseline_pointer["candidate"])
    old_logs = work / "prior-selection-runtime"
    old_logs.mkdir()
    with driver.servers(candidate, candidate.parent / "catalog-service.native-preview", node, dict(os.environ), old_logs) as (frontend, backend):
        result = json.loads(run("m5-prior-preview-still-usable", [node, fixture / "acceptance/check-runtime.cjs", candidate.parent / "client-js/operations.js", frontend, backend]))
        assert result["realNextRustRoundTrip"] is True
    controls.append({"control": "m5-prior-selection-still-usable", "result": "passed"})
    handler.write_text(original_handler + "\n// independently checked single edit\n")
    single = driver.update(args)
    assert single["status"] == "verified-native-preview" and selected() != baseline
    baseline = selected()
    controls.append({"control": "m5-single-edit", **single})

    # Watch uses periodic full reconciliation; no filesystem event is delivered
    # to the driver by this harness. A short burst must coalesce to one attempt.
    command = [str(env.get("PATAMAPS_DEV_PYTHON", sys.executable)), "-B", str(fixture / "dev.py"), "--watch", "--source", str(owner), "--repository", str(root),
               "--state", str(state), "--compiler", str(cli), "--cargo", str(cargo), "--rustc", str(rustc), "--node", str(node), "--debounce-ms", "600"]
    watch_env = dict(os.environ)
    watch_env.pop("PATAMAPS_DEV_SUPERVISOR", None)  # This bounded test already owns its host phase.
    watch_out = work / "watch.stdout.log"
    read_failures = []
    observed_pointers = set()
    reading = threading.Event()
    reading.set()
    def reader():
        while reading.is_set():
            try:
                raw = selected()
                pointer = json.loads(raw)
                if raw not in observed_pointers:
                    driver.pointer_valid(pointer)
                    observed_pointers.add(raw)
            except BaseException as error:
                read_failures.append(str(error))
            time.sleep(.02)
    observer = threading.Thread(target=reader)
    observer.start()
    with watch_out.open("xb") as out, (work / "watch.stderr.log").open("xb") as err:
        watching = subprocess.Popen(command, cwd=root, env=watch_env, stdout=out, stderr=err, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while '"status": "unchanged"' not in watch_out.read_text():
                assert watching.poll() is None
                if time.monotonic() >= deadline:
                    raise RuntimeError("Watch did not report its initial no-op")
                time.sleep(.05)
            count = attempt_count()
            for index in range(5):
                handler.write_text(original_handler + "\n// burst " + str(index) + "\n")
                time.sleep(.05)
            deadline = time.monotonic() + 600
            while selected() == baseline:
                assert watching.poll() is None
                if time.monotonic() >= deadline:
                    raise RuntimeError("Watch did not select the reconciled edit")
                time.sleep(.1)
            assert attempt_count() == count + 1
            updated = selected()
            controls.append({"control": "m5-batch-and-lost-event-reconciliation", "result": "selected-one-complete-candidate", "edits": 5, "eventChannel": "none"})
            generated = owner / "web/generated"
            generated.mkdir(exist_ok=True)
            (generated / "operations.ts").write_text("// generated feedback marker\n")
            time.sleep(2)
            assert selected() == updated and attempt_count() == count + 1
            controls.append({"control": "m5-generated-feedback", "result": "no-extra-attempt"})
        finally:
            driver.stop(watching)
            reading.clear()
            observer.join(timeout=5)
    assert not read_failures, read_failures
    assert len(observed_pointers) >= 2
    controls.append({"control": "m5-atomic-selection-readers", "result": "all-observed-pointers-complete", "generations": len(observed_pointers)})
    (owner / "web/app/items").rename(owner / "web/app/products")
    manifest_path = owner / "contracts/operations.json"
    manifest = json.loads(manifest_path.read_bytes())
    stable_ids = [op["id"] for op in manifest["operations"]]
    for view in manifest["views"]:
        if view["name"] == "item":
            view.update(file="web/app/products/[id]/page.tsx", path="/products/:id")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    renamed = driver.update(args)
    assert renamed["status"] == "verified-native-preview"
    pointer = json.loads(selected())
    candidate = Path(pointer["candidate"])
    assert json.loads((candidate / "app/.patamaps/generation.json").read_bytes())["operationIds"] == stable_ids
    route_logs = work / "renamed-page-runtime"
    route_logs.mkdir()
    with driver.servers(candidate, candidate.parent / "catalog-service.native-preview", node, dict(os.environ), route_logs) as (frontend, backend):
        with urlopen(frontend + "/products/item:widget", timeout=10) as response:
            assert response.status == 200
    controls.append({"control": "m5-route-rename", "result": "actual-renamed-page-served", "stableOperationIds": stable_ids})

    # Force a real nested metadata tool to remain live, cancel the driver and
    # check descendants before any manual fixture-process cleanup.
    from cross_stack_supervision import processes, running
    pid_file = work / "cancel-tool-pids.txt"
    fake_cargo = work / "cancel-cargo"
    fake_cargo.write_text('#!/bin/sh\nif [ "$1" = "metadata" ]; then\n/bin/sleep 60 & child=$!\nprintf "%s %s\\n" "$$" "$child" > ' + shlex.quote(str(pid_file)) + '\nwait "$child"\nelse\nexec ' + shlex.quote(str(cargo)) + ' "$@"\nfi\n')
    fake_cargo.chmod(0o755)
    cancel_command = [str(env.get("PATAMAPS_DEV_PYTHON", sys.executable)), "-B", str(fixture / "dev.py"), "--source", str(owner), "--repository", str(root),
                      "--state", str(state), "--compiler", str(cli), "--cargo", str(fake_cargo), "--rustc", str(rustc), "--node", str(node)]
    before_cancel = selected()
    groups = set()
    cancellation = {}
    with (work / "cancel.stdout.log").open("xb") as out, (work / "cancel.stderr.log").open("xb") as err:
        cancelling = subprocess.Popen(cancel_command, cwd=root, env=watch_env, stdout=out, stderr=err, start_new_session=True)
        groups.add(cancelling.pid)
        try:
            deadline = time.monotonic() + 45
            while not pid_file.exists():
                assert cancelling.poll() is None, (work / "cancel.stderr.log").read_text()
                if time.monotonic() >= deadline:
                    raise RuntimeError("Cancellation fixture did not reach nested Cargo")
                time.sleep(.02)
            table = processes()
            owned = {cancelling.pid}
            for _ in range(32):
                children = {pid for pid, info in table.items() if info["parent"] in owned}
                if children <= owned:
                    break
                owned.update(children)
            assert set(map(int, pid_file.read_text().split())) <= owned
            groups.update(table[pid]["group"] for pid in owned if pid in table)
            assert os.getpgrp() not in groups and min(groups) > 1
            started = time.monotonic()
            cancelling.send_signal(signal.SIGTERM)
            cancelling.wait(timeout=15)
            deadline = time.monotonic() + 8
            while True:
                table = processes()
                lingering = [pid for pid in owned if running(table, pid)]
                if not lingering or time.monotonic() >= deadline:
                    break
                time.sleep(.02)
            cancellation = {"control": "m5-cancelled-pipeline", "result": "stopped" if not lingering else "leaked",
                            "ownedPids": sorted(owned), "lingeringBeforeCleanup": lingering, "milliseconds": round((time.monotonic() - started) * 1000, 3)}
            assert selected() == before_cancel
            cancellation["previousSelectionPreserved"] = True
            assert not lingering, cancellation
        finally:
            table = processes()
            for group in groups:
                if group > 1 and group != os.getpgrp() and any(info["group"] == group and running(table, pid) for pid, info in table.items()):
                    try:
                        os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            if cancelling.poll() is None:
                cancelling.kill()
                cancelling.wait(timeout=5)
            (work / "cancellation-receipt.json").write_text(json.dumps(cancellation, indent=2) + "\n")
    controls.append(cancellation)
    expected = json.loads((fixture / "acceptance/m5-expected.json").read_bytes())
    assert {v["control"] for v in controls} == set(expected["controls"])
    return {"controls": controls, "count": len(controls), "fullReleaseAccepted": False,
            "scope": "native preview compilation, generated-client HTTP, retained selection and bounded foreground watch"}
