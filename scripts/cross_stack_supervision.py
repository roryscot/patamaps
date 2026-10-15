"""Actual process liveness controls; all fixtures and failed probes are retained."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import signal
import subprocess
import time


def digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def processes():
    output = subprocess.check_output(["/bin/ps", "-axo", "pid=,ppid=,pgid=,stat="], text=True)
    return {int(p): {"parent": int(parent), "group": int(group), "state": state}
            for p, parent, group, state in (line.split() for line in output.splitlines())}


def running(table, pid):
    return pid in table and not table[pid]["state"].startswith("Z")


def documents(owner, cli, source):
    workspace_id = "urn:patamaps:test:parent-death"
    policy = {"schemaVersion": "0.1.0", "documentType": "policy", "id": workspace_id + ":policy",
              "graph": {"id": workspace_id, "revision": "1"}, "mappings": [], "constraints": [], "evidence": []}
    projection = {"schemaVersion": "0.1.0", "documentType": "projection-spec", "id": workspace_id + ":projection", "select": {"kinds": ["probe:unselected"]}, "slots": []}
    config = {"schemaVersion": "0.1.0", "documentType": "workspace-config", "id": workspace_id, "namespace": "parent-death-test", "revision": "1",
              "sources": [source], "packs": [], "policy": "policy.json", "projections": [{"path": "projection.json", "emissions": [{"path": "generated.json", "language": "json"}]}],
              "context": {}, "evaluatedAt": "2026-10-15T00:00:00Z"}
    for name, value in [("policy.json", policy), ("projection.json", projection), ("workspace.json", config)]:
        with (owner / name).open("x") as out:
            out.write(json.dumps(value, indent=2) + "\n")
    return [str(cli), "generate", "workspace.json", "--root", str(owner)]


def probe(root, work, cli, rustc, nested, require_stopped=True):
    label = "nested-cargo-parent-death" if nested else "provider-parent-death"
    owner = work / label
    owner.mkdir()
    pid_file = owner / "tool-pids.txt"
    body = '/bin/sleep 60 & child=$!\nprintf "%s %s\\n" "$$" "$child" > ' + shlex.quote(str(pid_file)) + '\nwait "$child"\n'
    invocation = {"executable": "/bin/sh", "arguments": ["-c", body], "codeInputs": [],
                  "bounds": {"maximumElapsedMs": 60000, "maximumStdoutBytes": 1048576, "maximumStderrBytes": 65536}}
    config = {}
    inputs = ["nonsecret.txt"]
    (owner / "nonsecret.txt").write_text("nonsecret supervision fixture\n")
    if nested:
        tool = owner / "fixture-cargo"
        tool.write_text('#!/bin/sh\nif [ "$1" = "metadata" ]; then\n' + body + '\nelse\n  printf "cargo 1.99.0 (liveness fixture)\\n"\nfi\n')
        tool.chmod(0o755)
        (owner / "src").mkdir()
        (owner / "src/main.rs").write_text("fn main() {}\n")
        (owner / "Cargo.toml").write_text('[workspace]\nresolver="3"\n[package]\nname="supervision-fixture"\nversion="0.1.0"\nedition="2024"\n')
        (owner / "Cargo.lock").write_text('version=4\n[[package]]\nname="supervision-fixture"\nversion="0.1.0"\n')
        (owner / "rust-toolchain.toml").write_text('[toolchain]\nchannel="1.99.0"\nprofile="minimal"\n')
        cargo_home = owner / "cargo-home"
        cargo_home.mkdir()
        inputs = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "src/main.rs"]
        config = {"provider": "cargo", "nonsecretInputs": True, "manifest": "Cargo.toml", "workspaceManifest": "Cargo.toml", "lockfile": "Cargo.lock",
                  "cargo": str(tool), "cargoDigest": digest(tool), "rustc": str(rustc), "rustcDigest": digest(rustc), "cargoHome": str(cargo_home),
                  "platform": "x86_64-unknown-linux-gnu", "features": [], "defaultFeatures": True, "view": "resolved"}
        invocation["executable"] = str(cli)
        invocation["arguments"] = ["discover-native"]
    source = {"adapter": "process", "id": "urn:patamaps:test:provider", "invocation": invocation, "inputs": inputs, "config": config}
    argv = documents(owner, cli, source)
    outcome = {"control": label, "argv": argv, "compilerDigest": digest(cli), "expectedStopped": require_stopped, "manualCleanupRequired": False}
    group_ids = set()
    parent = None
    try:
        with (owner / "parent.stdout.log").open("xb") as out, (owner / "parent.stderr.log").open("xb") as err:
            parent = subprocess.Popen(argv, cwd=owner, stdout=out, stderr=err, start_new_session=True)
            group_ids.add(parent.pid)
            deadline = time.monotonic() + 30
            while not pid_file.exists():
                if parent.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(label + " did not start its owned test tools: " + (owner / "parent.stderr.log").read_text()[-3000:])
                time.sleep(.02)
            tool, descendant = map(int, pid_file.read_text().split())
            table = processes()
            lineage = [tool, descendant]
            cursor = tool
            for _ in range(32):
                if cursor == parent.pid:
                    break
                if cursor not in table:
                    raise RuntimeError("Owned process ancestry disappeared before cancellation")
                group_ids.add(table[cursor]["group"])
                cursor = table[cursor]["parent"]
                lineage.append(cursor)
            assert cursor == parent.pid, "Test PID file did not describe this parent's descendants"
            assert os.getpgrp() not in group_ids and min(group_ids) > 1
            outcome["observedOwnedPids"] = sorted(set(lineage))
            outcome["observedOwnedGroups"] = sorted(group_ids)
            cancelled = time.monotonic()
            parent.kill()  # SIGKILL: cleanup cannot rely on a handler in this parent.
            parent.wait(timeout=5)
            deadline = time.monotonic() + (8 if require_stopped else 1)
            while True:
                table = processes()
                live = [pid for pid in lineage if running(table, pid)]
                if not live or time.monotonic() >= deadline:
                    break
                time.sleep(.02)
            outcome.update(parentExit=parent.returncode, lingeringBeforeCleanup=sorted(set(live)),
                           observedMilliseconds=round((time.monotonic() - cancelled) * 1000, 3),
                           result="stopped" if not live else "observed-leak")
    finally:
        table = processes()
        for group in group_ids:
            if group > 1 and group != os.getpgrp() and any(v["group"] == group and running(table, pid) for pid, v in table.items()):
                outcome["manualCleanupRequired"] = True
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if parent is not None and parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        with (owner / "receipt.json").open("x") as out:
            out.write(json.dumps(outcome, indent=2) + "\n")
    if require_stopped:
        assert outcome.get("result") == "stopped", outcome
        assert not outcome["manualCleanupRequired"], outcome
    return outcome


def verify(root, work, env, run):
    cli = root / "target/release/patamaps"
    rustc = Path(run("supervision-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
    return {"controls": [probe(root, work, cli, rustc, nested) for nested in [False, True]],
            "scope": "ordinary Unix provider and nested Cargo groups after actual CLI parent SIGKILL; trusted tools, not an OS sandbox"}
