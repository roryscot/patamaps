"""Retain CI candidates and owned images without removing Docker objects."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["image"], required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parents[1] / "ci-evidence"
    evidence.mkdir(exist_ok=True)
    work = evidence / ("cross-stack-" + args.phase)
    work.mkdir(exist_ok=True)
    baseline = shutil.disk_usage(evidence)
    receipt = {"status": "running", "startedUtc": datetime.now(timezone.utc).isoformat(), "deleted": [],
               "resourceBoundary": {"growthBytes": 4000000000, "reserveBytes": 500000000, "phase": "archive"}}
    def check_space():
        disk = shutil.disk_usage(evidence)
        if disk.free < 500000000 or disk.used - baseline.used > 4000000000:
            raise RuntimeError("CI archive storage boundary reached; original candidates and images retained")
    try:
        objects = work / "owned-docker-objects.json"
        images = sorted(set(json.loads(objects.read_bytes())["images"])) if objects.exists() else []
        if images:
            command = ["docker", "image", "save", *images]
            receipt["imageCommand"] = command
            destination = evidence / "cross-stack-owned-images.tar.gz"
            with (work / "image-save.stderr.log").open("xb") as err, gzip.open(destination, "xb", compresslevel=2) as archive:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err)
                try:
                    while chunk := process.stdout.read(1024 * 1024):
                        check_space()
                        archive.write(chunk)
                    assert process.wait(timeout=60) == 0
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
            receipt["imageArchive"] = {"path": str(destination), "sha256": hashlib.file_digest(destination.open("rb"), "sha256").hexdigest(), "bytes": destination.stat().st_size}
        check_space()
        destination = evidence / "cross-stack-image-evidence.tar.gz"
        workspaces = sorted(p for p in evidence.glob("cross-stack-*") if p.is_dir())
        with tarfile.open(destination, "x:gz", dereference=False, compresslevel=2) as archive:
            for workspace in workspaces:
                original = workspace / "receipt.json"
                if original.exists():
                    archive.add(original, arcname=workspace.name + "/receipt.json")
            for workspace in workspaces:
                for child in sorted(workspace.iterdir()):
                    if child.name != "receipt.json":
                        check_space()
                        archive.add(child, arcname=workspace.name + "/" + child.name)
        check_space()
        receipt["status"] = "retained"
    finally:
        receipt["finishedUtc"] = datetime.now(timezone.utc).isoformat()
        (evidence / "cross-stack-image-archive-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
