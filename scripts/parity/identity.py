"""Independently reconstruct the flat, string-only embedded source identities."""
import hashlib
import json
import re
from pathlib import Path


def identities(root: Path):
    def embedded(path, function, dynamic):
        source = path.read_text().split(f"pub fn {function}", 1)[1]
        # Recipes are flat string maps; fail on any unhandled source field.
        value = dict(dynamic)
        if function == "executor_id()":
            start = source.index("BTreeMap::from([")
            recipe = source[start:source.index("]))", start)]
            for name, relative in re.findall(r'\(\s*"([^"]+)"\s*,\s*include_str!\(\s*"([^"]+)"\s*\)\s*,?\s*\)', recipe):
                value[name] = (path.parent / relative).read_text()
            for name, literal in re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,?\s*\)', recipe):
                value[name] = literal
            declared = re.findall(r'\(\s*"([A-Za-z0-9]+)"\s*,', recipe)
        else:
            start = source.index("json!({")
            recipe = source[start:source.index("}))", start)]
            for name, relative in re.findall(r'"([^"]+)"\s*:\s*include_str!\(\s*"([^"]+)"\s*\)', recipe):
                value[name] = (path.parent / relative).read_text()
            for name, literal in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', recipe):
                value[name] = literal
            declared = re.findall(r'"([A-Za-z0-9]+)"\s*:', recipe)
        assert set(value) == set(declared) and len(declared) == len(value), f"Unclassified source identity fields in {function}"
        # This domain contains only strings with ASCII keys, so Python's exact
        # UTF-8 JSON string escaping/order agrees with RFC 8785. No floats or
        # arbitrary value canonicalization are reimplemented here.
        assert all(isinstance(item, str) for item in value.values())
        assert all(key.isascii() for key in value)
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    contracts = (root / "crates/patamaps-contracts/src/lib.rs").read_text()
    profile = re.search(r'pub const PROFILE: &str = "([^"]+)";', contracts)[1]
    collator = root / "vendor/icu_collator"
    digest = hashlib.sha256()
    for path in sorted(p for p in collator.rglob("*") if p.is_file()):
        raw = path.read_bytes()
        digest.update(path.relative_to(collator).as_posix().encode())
        digest.update(b"\0")
        digest.update(str(len(raw)).encode())
        digest.update(b"\0")
        digest.update(raw)
    compiler = embedded(root / "crates/patamaps-projection/src/capture.rs", "executor_id()", {
        "profile": profile, "legacyCollatorSource": "sha256:" + digest.hexdigest()})
    governance = embedded(root / "crates/patamaps-governance/src/proposal.rs", "governance_executor_id()", {"kernel": compiler})
    workspace = embedded(root / "crates/patamaps-workspace/src/lib.rs", "engine_id()", {"profile": "patamaps-workspace-draft-1", "compiler": compiler})
    scientific = embedded(root / "crates/patamaps-scientific/src/crate_export.rs", "scientific_engine_id()", {"profile": "urn:patamaps:scientific-crate:draft:1", "compiler": compiler, "artifacts": governance})
    return {"compiler": compiler, "governance": governance, "workspace": workspace, "scientific": scientific}
