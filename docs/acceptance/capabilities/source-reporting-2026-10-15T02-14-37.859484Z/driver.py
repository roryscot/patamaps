"""Exercise recorded source/candidate CLI workflows without Node or live rereads."""

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from identity import identities
from storage_guard import ensure_guarded


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    ensure_guarded()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/patamaps")
    args = parser.parse_args()
    cli = args.cli.absolute()
    output = ROOT / "docs/acceptance/capabilities" / datetime.now(timezone.utc).strftime("source-reporting-%Y-%m-%dT%H-%M-%S.%fZ")
    output.mkdir()
    (output / "driver.py").write_bytes(Path(__file__).read_bytes())
    work = Path(tempfile.mkdtemp(prefix="source-reporting-", dir=ROOT / ".tools/capabilities"))
    env = {"PATH": "/usr/bin:/bin"}
    assert shutil.which("node", path=env["PATH"]) is None
    commands = []
    report = {"status": "running", "binary": str(cli), "binaryDigest": digest(cli.read_bytes()), "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "nodeInPath": False, "deleted": [], "activation": "not-performed", "browserExecution": "not-run"}
    receipt = output / "receipt.json"

    def save():
        receipt.write_text(json.dumps(report, indent=2) + "\n")

    def write(name, value):
        (work / name).write_text(json.dumps(value, indent=2) + "\n")

    def run(label, arguments, expected=0):
        argv = [str(cli), *arguments]
        result = subprocess.run(argv, cwd=work, env=env, capture_output=True)
        item = {"label": label, "argv": argv, "exitCode": result.returncode, "expectedExitCode": expected}
        for stream in ["stdout", "stderr"]:
            raw = getattr(result, stream)
            log = output / f"{label}.{stream}.log"
            log.write_bytes(raw)
            item[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": digest(raw)}
        commands.append(item)
        save()
        assert result.returncode == expected, f"{label}: inspect retained logs"
        return result.stdout

    save()
    try:
        expected = {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}
        assert json.loads(run("engine", ["engine"])) == expected
        report["engines"] = expected
        graph = json.loads((ROOT / "fixtures/routing/graph.json").read_bytes())
        next(e for e in graph["entities"] if e["kind"] == "routing:handler")["locators"].append({"uri": "rust:crate::service::greet"})
        empty = {**graph, "id": "urn:source:empty", "entities": [], "mappings": [], "authorities": []}
        policy = json.loads((ROOT / "fixtures/routing/policy.json").read_bytes())
        policy["graph"] = {"id": "urn:workspace:source-reporting", "revision": "1"}
        for name, value in [("one.json", graph), ("two.json", empty), ("policy.json", policy)]:
            write(name, value)
        for name, origin in [("pack.json", "relation-packs/routing.json"), ("projection.json", "fixtures/routing/projection-spec.json")]:
            (work / name).write_bytes((ROOT / origin).read_bytes())
        config = {"schemaVersion": "0.1.0", "documentType": "workspace-config", "id": policy["graph"]["id"], "namespace": "source-reporting", "revision": "1", "sources": [{"adapter": "portable-shard", "id": "urn:source:one", "path": "one.json"}, {"adapter": "portable-shard", "id": "urn:source:two", "path": "two.json"}], "packs": ["pack.json"], "policy": "policy.json", "projections": [{"path": "projection.json", "emissions": [{"path": "bindings.rs", "language": "rust", "bindingSlot": "handler"}]}], "context": {"environment": "production"}, "evaluatedAt": "2026-10-10T12:00:00Z"}
        write("config.json", config)
        baseline = json.loads(run("generate", ["generate", "config.json", "--root", str(work)]))["baseline"]
        write("baseline.json", baseline)
        saved_baseline = (work / "baseline.json").read_bytes()
        inputs = baseline["captures"][0]["inputs"]
        write("inputs.json", inputs)
        initial = json.loads(run("evaluate-identical", ["source-evaluate", "baseline.json", "inputs.json"]))
        write("initial.json", initial)
        selected = max(inputs["graph"]["entities"], key=lambda e: e["id"])
        selected["label"] = "<script>source-label</script>"
        write("changed-inputs.json", inputs)
        changed = json.loads(run("evaluate-distinct", ["source-evaluate", "baseline.json", "changed-inputs.json"]))
        write("changed.json", changed)
        protected = {name: (work / name).read_bytes() for name in ["baseline.json", "initial.json", "changed.json", "inputs.json", "changed-inputs.json"]}
        # Keep the bytes at renamed paths; verification cannot rely on the live locators.
        (work / "one.json").rename(work / "one.offline.json")
        (work / "two.json").rename(work / "two.offline.json")
        inspected = json.loads(run("verify-offline", ["source-verify", "changed.json"]))["record"]
        assert inspected["relationship"] == "candidate-differs"
        assert inspected["graphComparison"]["status"] == "compared"
        assert inspected["sourceRediscovery"] == "not-performed"
        assert inspected["authorizationNow"] == inspected["active"] == "not-evaluated"
        member, = [r for r in inspected["sources"][0]["records"] if r["kind"] == "entity" and r["id"] == selected["id"]]
        assert member["sourceOccurrences"] == member["candidateOccurrences"] == 1
        assert inspected["sources"][1]["records"] == []
        assert json.loads(run("candidate-export", ["source-candidate", "changed.json"])) == changed["candidate"]
        comparison = json.loads(run("compare", ["source-compare", "initial.json", "changed.json"]))["record"]
        assert comparison["sourceChanges"] == [] and comparison["candidateComparison"]["status"] == "compared"
        options = ["source-inspect", "changed.json", "--before", "initial.json", "--subject", selected["id"], "--maximum-subjects", "1", "--maximum-mappings", "1"]
        explanation = json.loads(run("inspect-focused", options))["record"]
        assert explanation["subjects"][0]["id"] == selected["id"]
        assert explanation["navigation"]["omittedSubjects"] == len(inputs["graph"]["entities"]) - 1
        html = run("html", [*options, "--html"])
        (output / "debugger.html").write_bytes(html)
        assert b"<script>source-label</script>" not in html and b"&lt;script&gt;source-label&lt;/script&gt;" in html
        styles = re.findall(rb"<style>(.*?)</style>", html, re.S)
        assert len(styles) == 1
        style_hash = base64.b64encode(hashlib.sha256(styles[0]).digest())
        assert b"style-src 'sha256-" + style_hash + b"'" in html and b"unsafe-inline" not in html
        # A valid rejected capture must retain source evidence and unknown consumer outputs.
        rejected_inputs = json.loads(json.dumps(inputs))
        rejected_inputs["graph"]["mappings"].pop(0)
        write("rejected-inputs.json", rejected_inputs)
        rejected = json.loads(run("evaluate-rejected", ["source-evaluate", "baseline.json", "rejected-inputs.json"]))
        write("rejected.json", rejected)
        checked = json.loads(run("verify-rejected", ["source-verify", "rejected.json"]))["record"]
        assert checked["candidateAdmission"] == "rejected"
        delta = json.loads(run("compare-rejected", ["source-compare", "initial.json", "rejected.json"]))["record"]["candidate"]
        assert delta["riskDelta"] is None and delta["mappingStates"]["afterKnown"] is False
        forged = json.loads(json.dumps(changed))
        forged["workspace"]["discovery"][0]["sourceId"] = "urn:forged:source"
        write("forged.json", forged)
        run("refuse-substitution", ["source-verify", "forged.json"], 2)
        assert (work / "baseline.json").read_bytes() == saved_baseline
        assert all((work / name).read_bytes() == raw for name, raw in protected.items())
        assert not any(p.is_dir() for p in work.iterdir()), "No implicit cache or publication directories"
        assert digest(cli.read_bytes()) == report["binaryDigest"]
        assert identities(ROOT) == {key: expected[key] for key in ["compiler", "governance", "workspace", "scientific"]}
        report.update(status="passed", protectedInputsUnchanged=True, styleHash=style_hash.decode(), completedAtUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status": report["status"], "receipt": receipt.relative_to(ROOT).as_posix()}), flush=True)


if __name__ == "__main__":
    main()
