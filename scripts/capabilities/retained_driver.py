"""Run an unchanged historical driver while retaining its temporary fixtures."""

import argparse
import hashlib
import json
import runpy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from storage_guard import ensure_guarded


def main():
    ensure_guarded()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retain-in", type=Path, required=True)
    parser.add_argument("driver", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    driver = args.driver.resolve()
    allowed = {
        ROOT / "scripts/reference/semantic.py",
        ROOT / "scripts/test_lifecycle_pure.py",
        ROOT / "scripts/test_native.py",
        ROOT / "scripts/test_scientific.py",
        ROOT / "scripts/test_adapter_bridge.py",
    }
    if driver not in allowed:
        parser.error("Select an audited, unchanged capability driver")
    retained = args.retain_in.resolve()
    retained.relative_to(ROOT / ".tools/capabilities")
    retained.mkdir(parents=True, exist_ok=False)
    raw = driver.read_bytes()
    paths = []

    original_mkdtemp = tempfile.mkdtemp

    def retained_mkdtemp(suffix=None, prefix=None, dir=None):
        name = original_mkdtemp(prefix=prefix or "fixture-", suffix=suffix or "", dir=retained)
        paths.append(name)
        return name

    class RetainedDirectory:
        def __init__(self, suffix=None, prefix=None, dir=None, **options):
            self.name = retained_mkdtemp(suffix=suffix, prefix=prefix)

        def __enter__(self):
            return self.name

        def __exit__(self, *exception):
            return False

        def cleanup(self):
            # Explicitly retain all driver-created material, including failures.
            pass

    original = tempfile.TemporaryDirectory
    original_path = sys.path.copy()
    original_arguments = sys.argv
    tempfile.TemporaryDirectory = RetainedDirectory
    tempfile.mkdtemp = retained_mkdtemp
    # Match direct Python script execution: imports resolve from its directory.
    sys.path.insert(0, str(driver.parent))
    sys.argv = [str(driver), *args.arguments]
    status = "failed"
    try:
        runpy.run_path(str(driver), run_name="__main__")
        status = "passed"
    finally:
        tempfile.TemporaryDirectory = original
        tempfile.mkdtemp = original_mkdtemp
        sys.path[:] = original_path
        sys.argv = original_arguments
        unchanged = driver.read_bytes() == raw
        (retained / "retention.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "driver": driver.relative_to(ROOT).as_posix(),
                    "driverDigest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "driverUnchanged": unchanged,
                    "retainedTemporaryDirectories": paths,
                    "deleted": [],
                },
                indent=2,
            )
            + "\n"
        )
        if not unchanged:
            raise RuntimeError("Historical driver changed during execution")


if __name__ == "__main__":
    main()
