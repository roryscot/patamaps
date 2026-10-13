"""Retain independent test installations without duplicating APFS data blocks."""
import platform
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from storage_guard import check_reserve


def copy_tree(source: Path, destination: Path) -> None:
    source, destination = source.resolve(), destination.absolute()
    if destination.exists():
        raise FileExistsError(destination)
    check_reserve()
    if platform.system() == "Darwin":
        destination.parent.mkdir(parents=True, exist_ok=True)
        # clonefile copies have independent names and diverge on writes. macOS
        # cp falls back to an ordinary copy if the filesystem cannot clone.
        subprocess.run(["/bin/cp", "-cR", str(source), str(destination)], check=True)
    else:
        shutil.copytree(source, destination)


def copy_file(source: Path, destination: Path) -> None:
    source, destination = source.resolve(), destination.absolute()
    if destination.exists():
        raise FileExistsError(destination)
    check_reserve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Darwin":
        subprocess.run(["/bin/cp", "-cp", str(source), str(destination)], check=True)
    else:
        shutil.copy2(source, destination)


def install_discovery_tools(oracle: Path, node_modules: Path) -> dict:
    root = Path(__file__).resolve().parents[2]
    manifest = root / "fixtures/parity/discovery-tooling.json"
    raw = manifest.read_bytes()
    spec = json.loads(raw)
    digest = lambda value: "sha256:" + hashlib.sha256(value).hexdigest()
    assert digest((oracle / "package-lock.json").read_bytes()) == spec["referenceLockDigest"]
    installed = []
    for item in spec["packages"]:
        source, target = oracle / "node_modules" / item["name"], node_modules / item["name"]
        assert json.loads((source / "package.json").read_bytes())["version"] == item["version"]
        expected = {file["path"] for file in item["files"]}
        assert {file.relative_to(source).as_posix() for file in source.rglob("*") if file.is_file()} == expected
        for file in item["files"]:
            assert digest((source / file["path"]).read_bytes()) == file["digest"]
        copy_tree(source, target)
        assert {file.relative_to(target).as_posix() for file in target.rglob("*") if file.is_file()} == expected
        for file in item["files"]:
            assert digest((target / file["path"]).read_bytes()) == file["digest"]
        installed.append({"name": item["name"], "version": item["version"]})
    return {"manifest": manifest.relative_to(root).as_posix(), "digest": digest(raw), "packages": installed}
