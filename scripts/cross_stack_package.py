"""Package, verify and install an exact unpublished source/native pair."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile


def digest(path):
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def install_archive(archive, destination, capacity_root):
    """Extract an externally digest-verified package into a fresh consumer prefix."""
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        assert len(members) < 100000 and sum(v.size for v in members) < 1500000000
        assert shutil.disk_usage(capacity_root).free > sum(v.size for v in members) + 500000000
        assert len({Path(item.name).parts for item in members}) == len(members), "Duplicate package members"
        prefixes = set()
        for item in members:
            path = Path(item.name)
            assert not path.is_absolute() and ".." not in path.parts and len(path.parts) >= 2 and item.isfile()
            prefixes.add(path.parts[0])
        assert len(prefixes) == 1
        source.extractall(destination, members=members, filter="data")
    return destination / prefixes.pop()

def verify(root, work, env, run):
    cli = root / "target/release/patamaps"
    run("installed-cli-build", ["cargo", "build", "--release", "-p", "patamaps-cli", "--locked", "--offline"], timeout=900)
    package = work / "package"
    run("installed-exact-package", [env.get("PATAMAPS_DEV_PYTHON", sys.executable), "-B", root / "scripts/package.py",
        "--binary", cli, "--build-profile", "release", "--output", package], timeout=600)
    distribution = json.loads((package / "distribution.json").read_bytes())
    source_archive = package / distribution["sourceArchive"]["path"]
    native_archive = package / distribution["nativeArchive"]["path"]
    assert digest(source_archive) == distribution["sourceArchive"]["digest"]
    assert digest(native_archive) == distribution["nativeArchive"]["digest"]
    source = install_archive(source_archive, work / "consumer-source", work)
    native = install_archive(native_archive, work / "consumer-native", work)
    executable = native / "bin/patamaps"
    assert digest(executable) == distribution["binaryDigest"] == digest(cli)
    assert os.access(executable, os.X_OK)
    inventory = json.loads((source / "source-inventory.json").read_bytes())
    assert all(digest(source / item["path"]) == item["digest"] for item in inventory)
    names = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    assert names == {v["path"] for v in inventory} | {"source-inventory.json"}
    mode = "image" if platform.system() == "Linux" else "preview"
    command = [env.get("PATAMAPS_DEV_PYTHON", sys.executable), "-B", source / "scripts/cross_stack_installed.py", "--root", source,
               "--compiler", executable, "--node", env["PATAMAPS_DEV_NODE"], "--output", work / "installed-workflow", "--mode", mode]
    result = json.loads(run("installed-real-mixed-workflow", command, cwd=source, timeout=1500))
    assert result["status"] == "passed-installed-consumer-scope" and result["configuredCompilerUnavailable"] is True
    return {"status": "passed-installed-consumer-scope", "mode": mode, "distribution": distribution,
            "sourceInventoryFiles": len(inventory), "allInstalledSourceBytesVerified": True, "nativeBinaryMatchesPackagedAndSelected": True,
            "mixedWorkflow": result, "fullReleaseAccepted": False, "productionActivation": "not-performed", "deleted": []}
