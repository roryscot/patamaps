"""Run portable native checks with retained logs and exact source inventories."""
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from storage_guard import ensure_guarded

ensure_guarded()

ROOT = Path(__file__).resolve().parents[2]
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
output = ROOT / "docs/acceptance/parity" / f"native-{stamp}"
output.mkdir(parents=True)
environment = {**os.environ, "SDKROOT": "/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk",
               "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0"}
if platform.system() != "Darwin":
    environment.pop("SDKROOT", None)
cargo = Path.home() / ".cargo/bin/cargo"
command = [str(cargo), "test", "--locked", "--workspace", "--exclude", "patamaps-activator"]
files = [ROOT / name for name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"]]
files += sorted((ROOT / "crates").rglob("*.rs")) + sorted((ROOT / "crates").glob("*/Cargo.toml"))
files.append(ROOT / "fixtures/parity/pack-json-controls.json")
files.append(ROOT / "fixtures/parity/pack-nested-controls.json")
files.append(ROOT / "fixtures/parity/pack-file-syntax-controls.json")
files.append(ROOT / "fixtures/parity/digest-controls.json")
files.append(ROOT / "fixtures/parity/digest-utf16-controls.json")
files.append(ROOT / "fixtures/parity/reporting-controls.json")
files.append(ROOT / "fixtures/parity/correspondence-controls.json")
files.append(ROOT / "fixtures/parity/reference-controls.json")
files.append(ROOT / "fixtures/parity/config-controls.json")
files.append(ROOT / "fixtures/parity/workspace-controls.json")
files += [ROOT / "fixtures/parity" / name for name in ["cli-controls.json", "cli-expanded-controls.json", "migration-controls.json"]]
files.append(ROOT / "crates/patamaps-core/src/legacy_cli_usage.txt")
files.append(ROOT / "fixtures/reference/schemas/metamap-config.schema.json")
files += sorted(p for p in (ROOT / "vendor/icu_collator").rglob("*") if p.is_file())
inventory = [{"path": p.relative_to(ROOT).as_posix(), "digest": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
    result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
receipt = {"schemaVersion": "1.0.0", "status": "passed" if result.returncode == 0 else "failed", "command": command,
           "exitCode": result.returncode, "host": {"platform": platform.platform(), "architecture": platform.machine()},
           "environment": {key: environment.get(key) for key in ["SDKROOT", "CARGO_INCREMENTAL", "CARGO_PROFILE_DEV_DEBUG", "CARGO_PROFILE_TEST_DEBUG"]},
           "sourceInventory": inventory,
           "scope": "Portable native and compile-fail checks, including retained workspace/process fixtures. Protected-host tests are excluded until their cleanup preserves local material. This is not obligation-level parity acceptance.",
           "logs": {name: {"path": (output / name).relative_to(ROOT).as_posix(), "digest": "sha256:" + hashlib.sha256((output / name).read_bytes()).hexdigest()} for name in ["stdout.log", "stderr.log"]}}
(output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"status": receipt["status"], "receipt": (output / "receipt.json").relative_to(ROOT).as_posix(), "exitCode": result.returncode}, indent=2))
raise SystemExit(result.returncode)
