"""Prepare a retained, pinned reference executor without modifying the reference."""
import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
from storage_guard import ensure_guarded

ensure_guarded()

ROOT = Path(__file__).resolve().parents[2]
ENGINE = "399747a4ad05a37cd8db1cedd53048fad2175be4"
parser = argparse.ArgumentParser()
parser.add_argument("reference", type=Path)
parser.add_argument("--node", type=Path, required=True)
args = parser.parse_args()
reference = args.reference.resolve()
assert not subprocess.check_output(["git", "-C", reference, "status", "--porcelain"])
base = ROOT / ".tools/parity/oracles"
base.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix=ENGINE[:12] + "-", dir=base))
archive = work / "reference.tar"
subprocess.run(["git", "-C", reference, "archive", ENGINE, "--output", archive], check=True)
source = work / "reference"
source.mkdir()
with tarfile.open(archive) as retained:
    retained.extractall(source, filter="data")
manifest = json.loads((ROOT / "fixtures/parity/manifest.json").read_text())
for entry in manifest["referenceSourceFiles"]:
    assert "sha256:" + hashlib.sha256((source / entry["path"]).read_bytes()).hexdigest() == entry["digest"], entry["path"]
(source / "node_modules").symlink_to(reference / "node_modules", target_is_directory=True)
command = [str(args.node.resolve()), str(source / "node_modules/typescript/lib/tsc.js"), "-p", "tsconfig.build.json"]
compiled = subprocess.run(command, cwd=source, capture_output=True, text=True)
record = {
    "status": "prepared" if compiled.returncode == 0 else "compilation-failed",
    "engine": ENGINE,
    "retainedSource": str(source.relative_to(ROOT)),
    "retainedArchive": str(archive.relative_to(ROOT)),
    "archiveDigest": "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest(),
    "command": command,
    "exitCode": compiled.returncode,
    "stdout": compiled.stdout,
    "stderr": compiled.stderr,
    "testsRun": False,
    "cleanup": "All source, archive, compiler output and records retained; no deletion",
}
(work / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
assert compiled.returncode == 0, compiled.stdout + compiled.stderr
pointer = base / "current.json"
pointer.write_text(json.dumps({"record": str((work / "preparation.json").relative_to(ROOT)), "source": str(source.relative_to(ROOT))}, indent=2) + "\n")
assert not subprocess.check_output(["git", "-C", reference, "status", "--porcelain"])
print(json.dumps({"status": record["status"], "record": str((work / "preparation.json").relative_to(ROOT)), "source": str(source.relative_to(ROOT)), "testsRun": False, "cleanup": "retained"}, indent=2))
