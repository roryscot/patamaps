#!/usr/bin/env python3
"""Continue this authorized alpha upload, honoring crates.io's new-crate quota."""
import datetime as dt
import email.utils
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

STATE = Path(__file__).resolve().parent
ROOT = STATE.parent / "publishing-source-0001"
CHECKOUT = STATE.parent / "checkout"
UPLOADER = STATE / "publish_alpha_v3.py"
VERIFIER = STATE / "verify_alpha_public_v2.py"
UTC = dt.timezone.utc


def emit(value):
    print(json.dumps({"at": dt.datetime.now(UTC).isoformat(), **value}), flush=True)


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def guarded(script, arguments):
    growth = "500000000" if script == UPLOADER else "1500000000"
    return [os.environ["PATAMAPS_DEV_NODE"], str(STATE / "bounded-intel-run.mjs"), growth, "--",
            sys.executable, str(script), *map(str, arguments)]


def main():
    summary = {"startedAt": dt.datetime.now(UTC).isoformat(), "status": "running", "runs": [],
               "quota": "one additional new crate per ten minutes after the first five",
               "filesDeleted": 0, "activationAttempted": False,
               "drivers": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [Path(__file__), UPLOADER, VERIFIER]}}
    installer = None
    try:
        # A single guarded resume is already running in the interactive session.
        first = STATE / "publish-0003/publication.json"
        until = time.monotonic() + 1800
        while not first.exists():
            assert time.monotonic() < until, "Timed out waiting for the already-running upload"
            time.sleep(10)
        initial = json.loads(first.read_text())
        assert initial["status"] == "partial" and len(initial["packages"]) == 6, initial.get("error")
        deadline = dt.datetime(2026, 10, 21, 14, 34, 1, tzinfo=UTC)
        for number in range(4, 16):
            # Wait outside the supervisor so idle quota time holds no build slot.
            start = deadline - dt.timedelta(seconds=180)
            emit({"phase": "quota-wait", "nextUploadNotBefore": deadline.isoformat(),
                  "queueGuardedRunAt": start.isoformat()})
            while (remaining := (start - dt.datetime.now(UTC)).total_seconds()) > 0:
                time.sleep(min(remaining, 10))
            record = f"publish-{number:04}"
            command = guarded(UPLOADER, ["--source", ROOT, "--inventory",
                CHECKOUT / "docs/acceptance/crates-io/2026-10-19/candidate-inventory.json",
                "--state", STATE, "--record", record, "--new-crate-limit", "1",
                "--not-before", deadline.isoformat()])
            emit({"phase": "publication", "record": record})
            result = subprocess.run(command, cwd=os.environ["PATAMAPS_DEV_ROOT"])
            receipt_path = STATE / record / "publication.json"
            assert receipt_path.exists(), f"Guarded upload exited {result.returncode} without a publication receipt"
            receipt = json.loads(receipt_path.read_text())
            summary["runs"].append({"record": str(receipt_path), "exitCode": result.returncode,
                                    "status": receipt["status"], "verifiedPackages": len(receipt["packages"])})
            if result.returncode:
                diagnostic = "\n".join(p.read_text() for p in (STATE / record).glob("publish-*.stderr.log"))
                retry = re.search(r"Please try again after (.+?) and see https://crates.io/docs/rate-limits", diagnostic)
                if not retry:
                    raise RuntimeError(receipt.get("error", "Upload failed"))
                deadline = email.utils.parsedate_to_datetime(retry.group(1))
                emit({"phase": "server-rate-limit", "retryAt": deadline.isoformat()})
                continue
            assert receipt["status"] in {"partial", "passed"}
            if len(receipt["packages"]) >= 9 and installer is None:
                install = guarded(VERIFIER, ["--source", ROOT, "--driver", CHECKOUT / "scripts/crates_alpha_package.py",
                    "--state", STATE, "--publication", receipt_path, "--record", "public-install-0001"])
                installer = subprocess.Popen(install, cwd=os.environ["PATAMAPS_DEV_ROOT"])
                emit({"phase": "public-install-queued", "pid": installer.pid, "publication": str(receipt_path)})
            if receipt["status"] == "passed":
                summary["publicationRecord"] = str(receipt_path)
                break
            deadline += dt.timedelta(minutes=10)
        else:
            raise RuntimeError("Publication retry budget exhausted")
        assert installer is not None
        assert installer.wait() == 0, "Fresh public-registry installation failed"
        install_path = STATE / "public-install-0001/receipt.json"
        assert json.loads(install_path.read_text())["status"] == "passed"
        summary.update(status="passed", publicInstallRecord=str(install_path))
    except Exception as error:
        summary.update(status="failed", error=str(error))
        raise
    finally:
        summary["finishedAt"] = dt.datetime.now(UTC).isoformat()
        save(STATE / "queue-0002.json", summary)
        emit({"phase": "finished", "status": summary["status"]})


if __name__ == "__main__":
    main()
