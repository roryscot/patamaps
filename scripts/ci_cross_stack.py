"""Retained cross-stack source acceptance on an isolated GitHub Linux runner.

This is a CI host entry, not a bypass of the installed Intel storage supervisor.
Container, browser and installed-consumer acceptance remain separate lanes.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import argparse
import json
import os
import platform
import shutil
import subprocess
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["source", "development"], default="source")
    args = parser.parse_args()
    if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Use the configured isolated GitHub Linux CI job; Intel work uses its existing supervisor")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if revision != os.environ.get("GITHUB_SHA"):
        raise RuntimeError("CI source revision does not match the dispatched commit")
    work = ROOT / ("ci-evidence/cross-stack-" + args.phase)
    work.mkdir(parents=True, exist_ok=False)
    disk_before = shutil.disk_usage(ROOT)
    env = dict(os.environ, CARGO_INCREMENTAL="0", CARGO_BUILD_JOBS="2", RUST_TEST_THREADS="1",
               CARGO_PROFILE_DEV_DEBUG="0", CARGO_PROFILE_TEST_DEBUG="0", NEXT_TELEMETRY_DISABLED="1",
               PATAMAPS_DEV_NODE=str(Path(shutil.which("node")).resolve()))
    receipt = {"status": "running", "sourceRevision": revision, "startedUtc": datetime.now(timezone.utc).isoformat(),
               "commands": [], "fullCrossStackAcceptance": False, "linuxImage": "pending", "browser": "pending", "deleted": [],
               "ciResourceChecks": {"growthBytes": 4000000000, "reserveBytes": 500000000, "checkedBetweenCommands": True,
                                    "diskUsedBefore": disk_before.used, "localIntelPolicyChanged": False}}

    def save():
        (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def space():
        disk = shutil.disk_usage(ROOT)
        if disk.free < 500000000 or disk.used - disk_before.used > 4000000000:
            raise RuntimeError("CI storage boundary reached; retained outputs remain, acceptance refuses")

    def run(label, argv, cwd=ROOT, timeout=300, input_bytes=None, expected_success=True):
        space()
        item = {"label": label, "argv": [str(v) for v in argv], "cwd": str(cwd), "expectedSuccess": expected_success}
        receipt["commands"].append(item)
        if input_bytes is not None:
            (work / (label + ".stdin.json")).write_bytes(input_bytes)
            item["stdinDigest"] = digest(input_bytes)
        save()
        began = time.monotonic()
        with (work / (label + ".stdout.log")).open("xb") as out, (work / (label + ".stderr.log")).open("xb") as err:
            process = subprocess.run(item["argv"], cwd=cwd, env=env, input=input_bytes, stdout=out, stderr=err, timeout=timeout)
        item.update(exitCode=process.returncode, seconds=round(time.monotonic() - began, 3))
        for stream in ["stdout", "stderr"]:
            item[stream + "Digest"] = digest((work / (label + "." + stream + ".log")).read_bytes())
        save()
        print(json.dumps({"check": label, "exitCode": process.returncode, "seconds": item["seconds"]}), flush=True)
        if (process.returncode == 0) != expected_success:
            print((work / (label + ".stderr.log")).read_text()[-9000:], flush=True)
            print((work / (label + ".stdout.log")).read_text()[-3000:], flush=True)
            raise RuntimeError(label + " failed; all candidate material and logs are retained")
        space()
        return (work / (label + ".stdout.log")).read_bytes()

    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    before = {name: digest((ROOT / name).read_bytes()) for name in tracked if name and (ROOT / name).is_file()}
    try:
        for label, argv in [("rust-version", ["rustc", "-Vv"]), ("cargo-version", ["cargo", "--version"]), ("node-version", ["node", "--version"])]:
            run(label, argv)
        if args.phase == "source":
            from cross_stack_workspace import verify
            receipt["sourceWorkspace"] = verify(ROOT, work, env, run)
            from cross_stack_supervision import verify as verify_supervision
            receipt["toolSupervision"] = verify_supervision(ROOT, work, env, run)
        else:
            from cross_stack_development import verify
            receipt["developmentPreview"] = verify(ROOT, work, env, run)
        space()
        assert all(digest((ROOT / name).read_bytes()) == value for name, value in before.items()), "Tracked source changed during acceptance"
        receipt["sourceUnchanged"] = True
        receipt["status"] = "passed-source-intent-scope" if args.phase == "source" else "passed-development-preview-scope"
    except BaseException as error:
        receipt.update(status="failed", failure=str(error), traceback=traceback.format_exc())
        raise
    finally:
        receipt["finishedUtc"] = datetime.now(timezone.utc).isoformat()
        receipt["ciResourceChecks"]["diskUsedAfter"] = shutil.disk_usage(ROOT).used
        save()


if __name__ == "__main__":
    main()
