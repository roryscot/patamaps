#!/usr/bin/env python3
"""Check or update core's packaged mirrors from their authoritative files."""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "crates/patamaps-core"
MIRRORS = CRATE / "package-data"
INCLUDE = re.compile(r'include_(?:str|bytes)!\s*\(\s*"([^"]+)"', re.S)


def referenced_assets():
    assets = {}
    for folder in ("src", "tests", "examples"):
        for source in sorted((CRATE / folder).rglob("*.rs")):
            for literal in INCLUDE.findall(source.read_text(encoding="utf-8")):
                target = (source.parent / literal).resolve()
                if not target.is_relative_to(CRATE):
                    raise ValueError(f"include escapes core crate: {source.relative_to(ROOT)}")
                if not target.is_relative_to(MIRRORS):
                    continue
                relative = target.relative_to(MIRRORS)
                if not relative.parts or relative.parts[0] not in ("fixtures", "relation-packs"):
                    raise ValueError("unsupported packaged asset path")
                authority = (ROOT / relative).resolve()
                if not authority.is_relative_to(ROOT) or not authority.is_file():
                    raise ValueError(f"authoritative asset missing: {relative}")
                assets[target] = authority
    if not assets:
        raise ValueError("no packaged assets found")
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="update mirrors without deleting files")
    args = parser.parse_args()
    assets = referenced_assets()
    for mirror, authority in assets.items():
        data = authority.read_bytes()
        if args.sync:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_bytes(data)
        if not mirror.is_file() or mirror.read_bytes() != data:
            raise ValueError(f"packaged asset differs: {mirror.relative_to(ROOT)}")
    print(f"verified {len(assets)} core package assets against authoritative files")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
