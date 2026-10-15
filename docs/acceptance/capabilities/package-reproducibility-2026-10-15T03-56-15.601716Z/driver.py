"""Verify full source/native archive reproducibility for identical source/binary inputs."""

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from identity import identities
from storage_guard import ensure_guarded


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(block)
    return "sha256:" + value.hexdigest()


def file_digest(path):
    with path.open("rb") as stream:
        return digest(stream)


def main():
    ensure_guarded()
    output = ROOT / "docs/acceptance/capabilities" / datetime.now(timezone.utc).strftime("package-reproducibility-%Y-%m-%dT%H-%M-%S.%fZ")
    output.mkdir()
    (output / "driver.py").write_bytes(Path(__file__).read_bytes())
    work = Path(tempfile.mkdtemp(prefix="package-reproducibility-", dir=ROOT / ".tools/capabilities"))
    cli = ROOT / "target/debug/patamaps"
    expected = {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(ROOT)}
    binary_digest = file_digest(cli)
    commands = []
    report = {"status": "running", "retainedWork": work.relative_to(ROOT).as_posix(), "commands": commands, "binaryDigest": binary_digest, "engines": expected, "scope": "Full source/native archives from identical current source and one identified development binary, created at separate paths/times. This does not attest deterministic independent binary rebuilds, owner acceptance, registry publication or activation.", "deleted": []}
    receipt = output / "receipt.json"

    def save():
        receipt.write_text(json.dumps(report, indent=2) + "\n")

    def package(label, destination, expected_exit=0):
        argv = [sys.executable, "-B", str(ROOT / "scripts/package.py"), "--binary", str(cli), "--build-profile", "development", "--output", str(destination), "--acceptance-output", str(output)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True)
        item = {"label": label, "argv": argv, "exitCode": result.returncode, "expectedExitCode": expected_exit}
        for stream in ["stdout", "stderr"]:
            log = output / f"{label}.{stream}.log"
            log.write_bytes(getattr(result, stream))
            item[stream] = {"path": log.relative_to(ROOT).as_posix(), "digest": file_digest(log)}
        commands.append(item)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode}), flush=True)
        assert result.returncode == expected_exit, f"{label}: inspect retained logs"

    save()
    try:
        assert json.loads(subprocess.check_output([cli, "engine"])) == expected
        first = work / "first"
        second = work / "different-output-path"
        package("first", first)
        package("second", second)
        a = json.loads((first / "distribution.json").read_bytes())
        b = json.loads((second / "distribution.json").read_bytes())
        assert a == b and a["engines"] == expected and a["binaryDigest"] == binary_digest
        archives = []
        for kind in ["sourceArchive", "nativeArchive"]:
            paths = [directory / a[kind]["path"] for directory in [first, second]]
            for path in paths:
                assert file_digest(path) == a[kind]["digest"]
                with path.open("rb") as stream:
                    header = stream.read(10)
                assert header[:3] == bytes([31, 139, 8])
                assert int.from_bytes(header[4:8], "little") == 0 and not header[3] & 8
            archives.append({"kind": kind, "paths": [p.relative_to(ROOT).as_posix() for p in paths], "digest": a[kind]["digest"], "gzipMtime": 0, "gzipFilenamePresent": False})
        prefix = a["sourceArchive"]["path"].removesuffix("-source.tar.gz")
        with tarfile.open(first / a["sourceArchive"]["path"], "r:gz") as archive:
            inventory_raw = archive.extractfile(prefix + "/source-inventory.json").read()
            assert "sha256:" + hashlib.sha256(inventory_raw).hexdigest() == a["sourceInventoryDigest"]
            inventory = json.loads(inventory_raw)
            expected_files = {prefix + "/" + item["path"]: item for item in inventory}
            members = archive.getmembers()
            assert [m.name for m in members] == sorted([*expected_files, prefix + "/source-inventory.json"])
            for member in members:
                assert member.isfile() and member.mtime == member.uid == member.gid == 0
                assert member.mode == 0o644
                if member.name == prefix + "/source-inventory.json":
                    continue
                item = expected_files[member.name]
                assert member.size == item["bytes"]
                with archive.extractfile(member) as stream:
                    assert digest(stream) == item["digest"], member.name
                assert file_digest(ROOT / item["path"]) == item["digest"], item["path"]
        with tarfile.open(first / a["nativeArchive"]["path"], "r:gz") as archive:
            members = archive.getmembers()
            assert [m.name for m in members] == sorted(prefix + "/" + name for name in ["LICENSE", "NOTICE", "bin/patamaps", "distribution.json"])
            for member in members:
                assert member.isfile() and member.mtime == member.uid == member.gid == 0
                assert member.mode == (0o755 if member.name.endswith("/bin/patamaps") else 0o644)
            with archive.extractfile(prefix + "/bin/patamaps") as stream:
                assert digest(stream) == binary_digest
        preserved = {p.name: file_digest(p) for p in first.iterdir() if p.is_file()}
        package("refuse-overwrite", first, 1)
        assert "FileExistsError" in (output / "refuse-overwrite.stderr.log").read_text()
        assert preserved == {p.name: file_digest(p) for p in first.iterdir() if p.is_file()}
        assert file_digest(cli) == binary_digest and identities(ROOT) == {key: expected[key] for key in ["compiler", "governance", "workspace", "scientific"]}
        report.update(status="passed", archives=archives, sourceInventoryEntries=len(inventory), sourceInventoryDigest=a["sourceInventoryDigest"], allSourceMembersAndCurrentBytesVerified=True, nativeBinaryBytesVerified=True, existingOutputsPreserved=True, completedAtUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status": report["status"], "receipt": receipt.relative_to(ROOT).as_posix()}), flush=True)


if __name__ == "__main__":
    main()
