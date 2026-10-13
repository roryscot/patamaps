"""Enter the installed local supervisor before allocating parity outputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
INSTALL = Path.home() / "Documents/Codex/storage-safeguards"


def check_reserve():
    config = json.loads((INSTALL / "projects.json").read_text())
    policy_file = Path(config["engine"]).resolve().parent.parent / "storage-policy.json"
    policy = json.loads(policy_file.read_text())
    locations = {ROOT, Path(tempfile.gettempdir()), Path("/private/tmp")}
    free = min(shutil.disk_usage(location).free for location in locations if location.exists())
    if free < policy["reserveFreeBytes"]:
        raise RuntimeError("Storage reserve reached; retain outputs and request an exact cleanup list")


def live_parent():
    try:
        if os.environ.get("LOCAL_STORAGE_PROJECT") != str(ROOT):
            return False
        ledger = Path(os.environ["WARGAME_STORAGE_LEASE_DIR"]) / "active-run/owner.json"
        owner = json.loads(ledger.read_text())
        if (owner["token"] != os.environ.get("WARGAME_STORAGE_RUN_TOKEN")
                or str(owner["pid"]) != os.environ.get("WARGAME_STORAGE_OWNER_PID")):
            return False
        os.kill(owner["pid"], 0)
        return True
    except (OSError, KeyError, ValueError):
        return False


def ensure_guarded():
    if live_parent():
        check_reserve()
        return
    # Missing installation fails closed; no unsupervised build is started.
    config = json.loads((INSTALL / "projects.json").read_text())
    command = [config["node"], str(INSTALL / "run-project.mjs"), "patamaps", "--",
               sys.executable, str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
    result = subprocess.run(command)
    raise SystemExit(result.returncode)
