"""Refresh/check declared crate-owned copies; never deletes originals or stale files."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def pairs(crate):
    for line in (crate / "package-inputs.tsv").read_text().splitlines():
        local, original = line.split("\t")
        for name in [local, original]:
            p = Path(name)
            if p.is_absolute() or not p.parts or any(s in {".", ".."} for s in p.parts):
                raise ValueError("unsafe input path")
        yield local, original

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors = []
    count = 0
    template = (ROOT / "scripts/crate_package_build.rs").read_bytes()
    for crate in sorted((ROOT / "crates").iterdir()):
        if not (crate / "Cargo.toml").is_file(): continue
        for local, original in pairs(crate):
            source = ROOT / original
            target = crate / local
            raw = source.read_bytes()
            if not target.is_file() or target.read_bytes() != raw:
                if args.check: errors.append(str(target.relative_to(ROOT)))
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
            count += 1
        if not (crate / "build.rs").is_file() or (crate / "build.rs").read_bytes() != template:
            if args.check: errors.append(str((crate / "build.rs").relative_to(ROOT)))
            else: (crate / "build.rs").write_bytes(template)
    if errors:
        raise SystemExit("stale crate inputs: " + ", ".join(errors))
    print(f"crate input {'check' if args.check else 'sync'} passed: {count} files")

if __name__ == "__main__": main()
