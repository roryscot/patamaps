"""Bind both installed distributions to this tree and the actual native runs."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--macos", type=Path, required=True)
parser.add_argument("--linux", type=Path, required=True)
parser.add_argument("--tested-source", type=Path, required=True)
parser.add_argument("--reference", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--macos-checks", type=Path, default=ROOT / "docs/acceptance/distributions/Patamaps/native-macos.json")
parser.add_argument("--linux-tests", type=Path, default=ROOT / "docs/acceptance/distributions/Patamaps/native-linux.json")
parser.add_argument("--linux-release-host", type=Path, default=ROOT / "docs/acceptance/distributions/Patamaps/release-linux.json")
args = parser.parse_args()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def files(archive):
    with tarfile.open(archive) as tar:
        result = {}
        for entry in tar:
            assert entry.isfile(), entry.name
            parts = Path(entry.name).parts
            assert len(parts) > 1 and not entry.name.startswith("/") and ".." not in parts
            relative = "/".join(parts[1:])
            assert relative not in result, relative
            result[relative] = tar.extractfile(entry).read()
        return result


def verified_distribution(directory, target):
    receipt = json.loads((directory / "distribution.json").read_text())
    installed = json.loads((directory / "installation.json").read_text())
    assert receipt["target"] == target
    assert installed["status"] == "passed" and installed["distribution"] == receipt
    assert installed["installedEngine"] == receipt["engines"]
    assert installed["activation"] == "not-evaluated"
    assert receipt["buildProfile"] == "release"
    for kind in ["sourceArchive", "nativeArchive"]:
        archive = directory / receipt[kind]["path"]
        assert digest(archive.read_bytes()) == receipt[kind]["digest"]
    source = files(directory / receipt["sourceArchive"]["path"])
    inventory = json.loads(source["source-inventory.json"])
    assert digest(source["source-inventory.json"]) == receipt["sourceInventoryDigest"]
    assert len(inventory) == installed["sourceInventoryEntries"]
    assert set(source) == {item["path"] for item in inventory} | {"source-inventory.json"}
    for item in inventory:
        raw = source[item["path"]]
        assert digest(raw) == item["digest"] and len(raw) == item["bytes"]
        assert raw == (ROOT / item["path"]).read_bytes(), item["path"]
    native = files(directory / receipt["nativeArchive"]["path"])
    expected = {"bin/patamaps", "LICENSE", "NOTICE", "distribution.json"}
    assert digest(native["bin/patamaps"]) == receipt["binaryDigest"]
    if "activatorBinaryDigest" in receipt:
        expected.add("bin/patamaps-activator")
        assert digest(native["bin/patamaps-activator"]) == receipt["activatorBinaryDigest"]
    assert set(native) == expected
    assert native["LICENSE"] == source["LICENSE"] and native["NOTICE"] == source["NOTICE"]
    native_receipt = json.loads(native["distribution.json"])
    assert native_receipt == {k: v for k, v in receipt.items() if k not in {"sourceArchive", "nativeArchive"}}
    return receipt, source, inventory


mac, mac_source, inventory = verified_distribution(args.macos, "aarch64-apple-darwin")
linux, linux_source, _ = verified_distribution(args.linux, "aarch64-unknown-linux-gnu")
assert mac_source == linux_source
assert mac["engines"] == linux["engines"]
assert mac["sourceInventoryDigest"] == linux["sourceInventoryDigest"]
tested = files(args.tested_source)
linux_tests = json.loads(args.linux_tests.read_text())
assert digest(args.tested_source.read_bytes()) == linux_tests["sourceArchive"]["digest"]
unchanged = []
for name, raw in tested.items():
    if (name.startswith(("crates/", "fixtures/", "relation-packs/", "schemas/")) and name != "fixtures/conformance.json") or name in {"Cargo.toml", "Cargo.lock", "rust-toolchain.toml"}:
        assert mac_source[name] == raw, name
        unchanged.append({"path": name, "digest": digest(raw)})
# New native source/test files cannot hide outside the tested snapshot.
assert {name for name in mac_source if name.startswith("crates/")} == {name for name in tested if name.startswith("crates/")}
mac_tests = json.loads(args.macos_checks.read_text())
assert mac_tests["status"] == linux_tests["status"] == "passed"
assert mac_tests["engine"] == mac["engines"]
assert mac_tests["nativeTests"]["passed"] == 100 and mac_tests["nativeTests"]["compileFailDocumentationPassed"] == 13
assert linux_tests["nativeTests"] == 110 and linux_tests["compileFailDocumentationTests"] == 13
for item in mac_tests["linuxLifecycleTestUpdate"]["sources"]:
    assert digest((ROOT / item["path"]).read_bytes()) == item["digest"]
release = json.loads(args.linux_release_host.read_text())
assert release["status"] == "passed" and release["linuxTestFunctions"] == 10
assert release["compilerBinaryDigest"] == linux["binaryDigest"]
assert release["activatorBinaryDigest"] == linux["activatorBinaryDigest"]
for receipt, path in [(linux_tests, args.linux_tests), (release, args.linux_release_host)]:
    assert digest((path.parent / receipt["rawConsole"]).read_bytes()) == receipt["rawConsoleDigest"]
assert "- [ ]" not in (ROOT / "BUILD_PLAN.md").read_text()
integrity_path = args.output.with_name("source-integrity-final.json")
args.output.parent.mkdir(parents=True, exist_ok=True)
assert not args.output.exists(), "Use a fresh output receipt; preserve earlier acceptance"
args.output.write_text(json.dumps({"status": "verification-in-progress", "sourceInventoryDigest": mac["sourceInventoryDigest"]}, indent=2) + "\n")
command = ["python3", str(ROOT / "scripts/test_source_integrity.py"), str(args.reference.resolve()), "--output", str(integrity_path.resolve())]
checked = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
assert checked.returncode == 0, checked.stdout + checked.stderr
report = {"verifiedAtUtc": datetime.now(timezone.utc).isoformat(), "status": "passed",
          "sourceInventoryEntries": len(inventory), "sourceInventoryDigest": mac["sourceInventoryDigest"],
          "macos": mac, "linux": linux,
          "nativeAcceptance": {"macosTests": 100, "linuxTests": 110, "compileFailTestsPerPlatform": 13,
                               "linuxReleaseHostFunctions": 10, "toolchain": "1.99.0", "features": "default"},
          "testedSourceArchive": linux_tests["sourceArchive"], "unchangedTestedInputs": unchanged,
          "integrityCommand": {"argv": command, "exitCode": checked.returncode, "stdout": checked.stdout, "stderr": checked.stderr},
          "scope": "Identical exact source inventories, actual independent package installations and unchanged native production/test/fixture bytes; no public release or production activation"}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
print("PASS: both installed candidates share exact current source bytes; native acceptance is bound to unchanged tested inputs and release host binaries; original source/expectation integrity passed.")
