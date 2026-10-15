"""Installed portable workspace and read-only inspection, with Node absent."""

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from storage_guard import ensure_guarded


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    ensure_guarded()
    pointer = json.loads((ROOT / ".tools/capabilities/current.json").read_bytes())
    installed_path = ROOT / pointer["installedReceipt"]
    assert digest(installed_path.read_bytes()) == pointer["installedReceiptDigest"]
    installed = json.loads(installed_path.read_bytes())
    assert installed["status"] == "passed"
    cli = ROOT / installed["retainedWork"] / "installation/bin/patamaps"
    env = {"PATH": "/usr/bin:/bin"}
    assert shutil.which("node", path=env["PATH"]) is None
    output = ROOT / "docs/acceptance/capabilities" / datetime.now(timezone.utc).strftime("workspace-%Y-%m-%dT%H-%M-%S.%fZ")
    output.mkdir()
    (output / "driver.py").write_bytes(Path(__file__).read_bytes())
    work = Path(tempfile.mkdtemp(prefix="workspace-", dir=ROOT / ".tools/capabilities"))
    graph = json.loads((ROOT / "fixtures/routing/graph.json").read_bytes())
    next(e for e in graph["entities"] if e["kind"] == "routing:handler")["locators"].append({"uri": "rust:crate::service::greet"})
    policy = json.loads((ROOT / "fixtures/routing/policy.json").read_bytes())
    policy["graph"] = {"id": "urn:patamaps:workspace:test", "revision": "1"}
    for name, value in [("graph.json", graph), ("policy.json", policy)]:
        (work / name).write_text(json.dumps(value, indent=2) + "\n")
    for name, origin in [("pack.json", "relation-packs/routing.json"), ("projection.json", "fixtures/routing/projection-spec.json")]:
        (work / name).write_bytes((ROOT / origin).read_bytes())
    config = {"schemaVersion": "0.1.0", "documentType": "workspace-config", "id": policy["graph"]["id"], "namespace": "workspace-test", "revision": "1", "sources": [{"adapter": "portable-shard", "id": "urn:patamaps:source:test", "path": "graph.json"}], "packs": ["pack.json"], "policy": "policy.json", "projections": [{"path": "projection.json", "emissions": [{"path": "bindings.rs", "language": "rust", "bindingSlot": "handler"}]}], "context": {"environment": "production"}, "evaluatedAt": "2026-10-10T12:00:00Z"}
    (work / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    inputs = {name: (work / name).read_bytes() for name in ["graph.json", "policy.json", "pack.json", "projection.json", "config.json"]}
    (work / "graph.before.json").write_bytes(inputs["graph.json"])
    commands = []
    report = {"status": "running", "installedReceipt": installed_path.relative_to(ROOT).as_posix(), "binaryDigest": digest(cli.read_bytes()), "nodeInPath": False, "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "deleted": [], "activation": "not-performed"}
    receipt = output / "receipt.json"

    def save():
        receipt.write_text(json.dumps(report, indent=2) + "\n")

    def run(label, arguments, expected=0):
        argv = [str(cli), *arguments]
        result = subprocess.run(argv, cwd=work, env=env, capture_output=True)
        for stream in ["stdout", "stderr"]:
            (output / f"{label}.{stream}.log").write_bytes(getattr(result, stream))
        commands.append({"label": label, "argv": argv, "exitCode": result.returncode, "expectedExitCode": expected})
        save()
        assert result.returncode == expected, f"{label}: inspect retained logs"
        return result.stdout

    save()
    try:
        assert json.loads(run("engine", ["engine"])) == installed["engines"]
        generated = json.loads(run("generate", ["generate", "config.json", "--root", str(work)]))
        baseline = generated["baseline"]
        assert baseline["captures"][0]["result"]["status"] == "viable"
        assert generated["cacheHits"] == 0
        assert "pub fn dispatch" in baseline["outputs"]["bindings.rs"]
        baseline_path = work / "baseline.json"
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
        saved = baseline_path.read_bytes()
        offline = json.loads(run("offline-baseline", ["verify-workspace", "baseline.json"]))
        assert offline == {"status": "verified-record-bindings", "baseline": baseline["digest"], "sourceRediscovery": "not-performed", "authentication": "not-evaluated", "authorizationNow": "not-evaluated", "active": "not-evaluated"}
        current = json.loads(run("unchanged", ["check", "config.json", "baseline.json", "--root", str(work)]))
        assert current["status"] == "unchanged" and not current["changes"]
        captured = work / "capture.json"
        captured.write_text(json.dumps(baseline["captures"][0], indent=2) + "\n")
        # Preserve the exact prior input; change only the independent fixture.
        graph["entities"][0]["label"] = '<script>document.documentElement.dataset.patamapsInjected="yes"</script>'
        (work / "graph.json").write_text(json.dumps(graph, indent=2) + "\n")
        drift = json.loads(run("drift", ["check", "config.json", "baseline.json", "--root", str(work)], 2))
        assert drift["status"] == "drift" and "discovery" in drift["changes"]
        assert baseline_path.read_bytes() == saved
        assert not any(p.is_dir() for p in work.iterdir()), "No implicit cache directory"
        regenerated = json.loads(run("regenerate-current", ["generate", "config.json", "--root", str(work)]))
        assert regenerated["baseline"]["digest"] == drift["currentDigest"]
        after = regenerated["baseline"]["captures"][0]
        (work / "after.json").write_text(json.dumps(after, indent=2) + "\n")
        inspected = json.loads(run("inspect", ["inspect", "after.json", "--before", "capture.json", "--subject", "urn:example:command:create-user"]))
        assert inspected["record"]["admission"] == "viable"
        html = run("html", ["inspect", "after.json", "--before", "capture.json", "--subject", "urn:example:command:create-user", "--html"])
        html_path = output / "debugger.html"
        html_path.write_bytes(html)
        assert b'<script>document.documentElement.dataset.patamapsInjected=' not in html
        styles = re.findall(rb"<style>(.*?)</style>", html, re.S)
        assert len(styles) == 1
        style_hash = base64.b64encode(hashlib.sha256(styles[0]).digest())
        assert b"style-src 'sha256-" + style_hash + b"'" in html
        assert b"unsafe-inline" not in html
        # The static report has no executable candidate tags or external links.
        assert not re.search(rb"<(script|img|iframe|svg|link|form|input|button)\b", html, re.I)
        assert not re.search(rb'href="(?:https?:|javascript:)', html, re.I)
        for name, raw in inputs.items():
            if name != "graph.json":
                assert (work / name).read_bytes() == raw
        report.update(status="passed", baselineUnchanged=True, noCacheCreated=True, sourceChange={"before": digest(inputs["graph.json"]), "after": digest((work / "graph.json").read_bytes()), "beforePreservedAt": (work / "graph.before.json").relative_to(ROOT).as_posix()}, html=html_path.relative_to(ROOT).as_posix(), browserVerification="pending", engines=installed["engines"])
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status": report["status"], "receipt": receipt.relative_to(ROOT).as_posix()}), flush=True)


if __name__ == "__main__":
    main()
