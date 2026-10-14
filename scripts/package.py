"""Create unpublished source/native bundles with exact inventories; no installers."""
import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--binary", type=Path, required=True)
parser.add_argument("--activator-binary", type=Path, help="Optional separately verified Linux host executable")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--build-profile", choices=["release", "development", "unspecified"], default="unspecified")
parser.add_argument("--acceptance-output", type=Path, help="Exact current receipt directory kept beside this package, outside its source payload")
args = parser.parse_args()
binary = args.binary.resolve()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
acceptance_output = args.acceptance_output.resolve() if args.acceptance_output else None
if acceptance_output:
    relative_acceptance = acceptance_output.relative_to(ROOT / "docs/acceptance")
    assert relative_acceptance.parts, "Do not exclude the acceptance evidence root"

def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()

def archive(path, files, prefix):
    with path.open("xb") as destination:
        # Fix both container metadata and tar members. Gzip's defaults record
        # the output filename and current time even when tar mtime is zero.
        with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name, data in sorted(files.items()):
                    entry = tarfile.TarInfo(f"{prefix}/{name}")
                    entry.size = len(data)
                    entry.mode = 0o755 if name.startswith("bin/") else 0o644
                    entry.mtime = 0
                    tar.addfile(entry, io.BytesIO(data))

source = {}
for directory in ["crates", "fixtures", "relation-packs", "schemas", "sdk", "adapters", "scripts", "examples", "vendor"]:
    for path in sorted((ROOT / directory).rglob("*")):
        if path.is_file() and not any(p in {"__pycache__", "node_modules", ".DS_Store", "target"} for p in path.parts):
            source[path.relative_to(ROOT).as_posix()] = path.read_bytes()
for name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "LICENSE", "NOTICE", "README.md", "BUILD_PLAN.md", "docs/SPEC.md", "docs/TEST_CLASSIFICATION.md"]:
    source[name] = (ROOT / name).read_bytes()
for path in (ROOT / "docs/decisions").glob("*.md"):
    source[path.relative_to(ROOT).as_posix()] = path.read_bytes()
for path in (ROOT / "docs/history").rglob("*"):
    if path.is_file():
        source[path.relative_to(ROOT).as_posix()] = path.read_bytes()
# The installation receipt identifies these archives and remains beside them,
# rather than recursively entering the bundle it verifies. Historical archives
# remain in the repository. Include all other acceptance records for inspection.
for path in (ROOT / "docs/acceptance").rglob("*"):
    relative = path.relative_to(ROOT / "docs/acceptance")
    if acceptance_output and path.is_relative_to(acceptance_output):
        continue
    if path.is_file() and relative.parts[0] not in {"distributions", "source-snapshots"} and relative.as_posix() != "native-installation.json":
        source[path.relative_to(ROOT).as_posix()] = path.read_bytes()
inventory = [{"path": name, "digest": digest(data), "bytes": len(data)} for name, data in sorted(source.items())]
source["source-inventory.json"] = (json.dumps(inventory, indent=2) + "\n").encode()
engine = json.loads(subprocess.check_output([str(binary), "engine"]))
rustc = str(Path.home() / ".cargo/bin/rustc")
toolchain = subprocess.check_output([rustc, "-vV"], text=True)
target = next(line.removeprefix("host: ") for line in toolchain.splitlines() if line.startswith("host: "))
receipt = {"schemaVersion": "0.1.0", "status": "unpublished-draft", "target": target,
           "toolchain": toolchain, "engines": engine, "binaryDigest": digest(binary.read_bytes()),
           "buildProfile": args.build_profile,
           "buildProvenance": "Caller-declared profile; hashing and source identity do not attest a reproducible or authorized binary",
           "sourceInventoryDigest": digest(source["source-inventory.json"]),
           "protectedActivationAcceptance": "recorded-separately"}
if acceptance_output:
    receipt["acceptanceOutputOutsideSourcePayload"] = acceptance_output.relative_to(ROOT).as_posix()
if args.activator_binary:
    assert target.endswith("unknown-linux-gnu"), "Protected executable packaging is Linux-only"
    activator = args.activator_binary.resolve()
    receipt["activatorBinaryDigest"] = digest(activator.read_bytes())
    receipt["activatorInstallation"] = "Owner installation/trust bootstrap required; package does not install or activate"
prefix = f"patamaps-draft-{engine['compiler'][7:19]}"
source_path = output / f"{prefix}-source.tar.gz"
binary_path = output / f"{prefix}-{target}.tar.gz"
archive(source_path, source, prefix)
native = {"bin/patamaps": binary.read_bytes(), "LICENSE": source["LICENSE"], "NOTICE": source["NOTICE"],
          "distribution.json": (json.dumps(receipt, indent=2) + "\n").encode()}
if args.activator_binary:
    native["bin/patamaps-activator"] = activator.read_bytes()
archive(binary_path, native, prefix)
receipt["sourceArchive"] = {"path": source_path.name, "digest": digest(source_path.read_bytes())}
receipt["nativeArchive"] = {"path": binary_path.name, "digest": digest(binary_path.read_bytes())}
(output / "distribution.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
