"""Run preserved scientific/discovery workflows with the installed native host."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from identity import identities
from storage_guard import ensure_guarded, node_runtime


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    ensure_guarded()
    current = json.loads((ROOT / ".tools/capabilities/current.json").read_bytes())
    installed_path = ROOT / current["installedReceipt"]
    assert digest(installed_path.read_bytes()) == current["installedReceiptDigest"]
    installed = json.loads(installed_path.read_bytes())
    assert installed["status"] == "passed"
    cli = ROOT / installed["retainedWork"] / "installation/bin/patamaps"
    oracle = ROOT / json.loads((ROOT / ".tools/parity/oracles/current.json").read_bytes())["source"]
    node = node_runtime()
    checker = ROOT / ".tools/scientific-checker/bin/python"
    assert checker.is_file(), "Use the already installed pinned independent checker"
    output = ROOT / "docs/acceptance/capabilities" / datetime.now(timezone.utc).strftime("integrations-%Y-%m-%dT%H-%M-%S.%fZ")
    output.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="integrations-", dir=ROOT / ".tools/capabilities"))
    environment = {**os.environ, "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    if sys.platform == "darwin":
        environment["SDKROOT"] = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
    files = [
        ROOT / "scripts/test_scientific.py", ROOT / "scripts/test_adapter_bridge.py",
        ROOT / "scripts/check_scientific_independent.py", ROOT / "scripts/capabilities/integrations.py",
        ROOT / "scripts/capabilities/retained_driver.py", ROOT / "fixtures/parity/discovery-tooling.json",
    ]
    for directory in ["adapters", "sdk", "fixtures/scientific", "fixtures/reference/examples/scientific-mapping", "examples/scientific-lookup"]:
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and not any(v in {"node_modules", "target", "__pycache__"} for v in p.parts))
    before = [{"path": p.relative_to(ROOT).as_posix(), "digest": digest(p.read_bytes())} for p in sorted(set(files))]
    commands = []
    report = {"status": "running", "scope": "Installed native scientific import/proof/policy/budget/crate/lookup workflow, unchanged TypeScript shadow, independent pinned SSSOM/RDF controls and seven extracted discovery-provider fixtures. No production activation or scientific truth claim.", "installedReceipt": installed_path.relative_to(ROOT).as_posix(), "installedBinaryDigest": digest(cli.read_bytes()), "sourceInventory": before, "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "deleted": []}
    path = output / "receipt.json"

    def save():
        path.write_text(json.dumps(report, indent=2) + "\n")

    def run(label, argv):
        save()
        result = subprocess.run([str(v) for v in argv], cwd=ROOT, env=environment, capture_output=True)
        command = {"label": label, "argv": [str(v) for v in argv], "exitCode": result.returncode}
        for stream in ["stdout", "stderr"]:
            log = output / f"{label}.{stream}.log"
            log.write_bytes(getattr(result, stream))
            command[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": digest(log.read_bytes())}
        commands.append(command)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed; retained logs: {output}")
        return result.stdout

    try:
        actual = json.loads(run("installed-engine", [cli, "engine"]))
        assert actual == installed["engines"] == {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}
        scientific_output = output / "scientific"
        run("scientific", [sys.executable, "-B", ROOT / "scripts/capabilities/retained_driver.py", "--retain-in", work / "scientific", ROOT / "scripts/test_scientific.py", "--cli", cli, "--node", node, "--tsc", oracle / "node_modules/typescript/lib/tsc.js", "--output", scientific_output])
        run("independent", [checker, "-B", ROOT / "scripts/check_scientific_independent.py", scientific_output, "--output", output / "independent.json"])
        run("discovery", [sys.executable, "-B", ROOT / "scripts/capabilities/retained_driver.py", "--retain-in", work / "discovery", ROOT / "scripts/test_adapter_bridge.py", "--cli", cli, "--node", node, "--reference", oracle, "--output", output / "discovery.json"])
        scientific = json.loads((scientific_output / "acceptance.json").read_bytes())
        assert scientific["engines"] == actual
        assert scientific["sourceAssertions"] == 7 and scientific["existingTypeScriptShadow"] == "exactly-equal"
        assert scientific["sourceBytesPreserved"]
        discovery = json.loads((output / "discovery.json").read_bytes())
        assert len(discovery["cases"]) == 7
        for item in before:
            assert digest((ROOT / item["path"]).read_bytes()) == item["digest"], item["path"]
        assert digest(cli.read_bytes()) == report["installedBinaryDigest"]
        report.update(status="passed", engines=actual, scientificAssertions=7, discoveryProviders=7, independentCheckerReport=(output / "independent.json").relative_to(ROOT).as_posix(), sourceUnchanged=True, completedAtUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status":report["status"],"receipt":path.relative_to(ROOT).as_posix()}),flush=True)


if __name__ == "__main__":
    main()
