"""Audit retained original bytes, expectations and declared native destinations."""
import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("reference", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((ROOT / "fixtures/conformance.json").read_text())
science = json.loads((ROOT / "fixtures/scientific/source-pin.json").read_text())
revision = manifest["engineRevision"]


def original(path):
    return subprocess.check_output(["git", "-C", args.reference, "show", f"{revision}:{path}"])


entries = manifest["preservedFiles"] + science["preservedFiles"]
assert len(manifest["preservedFiles"]) == 82 and len(science["preservedFiles"]) == 9
for entry in entries:
    raw = (ROOT / "fixtures/reference" / entry["path"]).read_bytes()
    assert raw == original(entry["path"]), entry["path"]
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"], entry["path"]
for suite in manifest["suites"]:
    assert hashlib.sha256(original(suite["path"])).hexdigest() == suite["sha256"], suite["suite"]
    for path in suite["nativeCoverage"]["tests"] + suite["nativeCoverage"]["records"]:
        assert (ROOT / path).is_file(), path
assert len(manifest["suites"]) == 53
tree = subprocess.check_output(["git", "-C", args.reference, "ls-tree", "-r", "--name-only", revision]).decode().splitlines()
reference_suites = {path for path in tree if path.startswith("src/__tests__/") and path.endswith(".test.ts")}
assert {suite["path"] for suite in manifest["suites"]} == reference_suites
expectations = json.loads(original("evaluation/capability-corpus.json"))["consumerBindings"]
assert [case["originalExpectation"] for case in manifest["nativeBindingCases"]] == expectations
assert len(expectations) == 22
assert not subprocess.check_output(["git", "-C", args.reference, "status", "--porcelain"])

documents = [ROOT / "README.md", ROOT / "BUILD_PLAN.md", ROOT / "docs/SPEC.md",
             *sorted((ROOT / "docs/decisions").glob("*.md")),
             ROOT / "docs/acceptance/2026-10-11-patamaps.md"]
for document in documents:
    for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        link = link.strip("<>")
        parsed = urllib.parse.urlsplit(link)
        if parsed.scheme or link.startswith("#"):
            continue
        target = document.parent / urllib.parse.unquote(parsed.path)
        assert target.exists(), (document.relative_to(ROOT), link)

report = {"referenceEngine": revision, "preservedEntries": len(entries),
          "originalBytes": "all-exact", "referenceCheckoutClean": True,
          "referenceCheckoutHead": subprocess.check_output(["git", "-C", args.reference, "rev-parse", "HEAD"]).decode().strip(),
          "unchangedNativeBindingExpectations": len(expectations),
          "nativeCoverageDestinations": len(manifest["suites"]),
          "scope": "Explicit successor profile destinations; not 584 Rust assertions or old API parity",
          "localDocumentationLinks": "all-resolve", "preservedFiles": entries}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
print("PASS: 91 original file entries retain exact Git bytes; 22 original expectations unchanged; 53 native destinations exist; current documentation links resolve; reference checkout clean.")
