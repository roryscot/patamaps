"""Independently reconstruct the flat, string-only embedded source identities."""
import hashlib
import json
import re
from pathlib import Path


def package_inputs_digest(crate: Path):
    digest = hashlib.sha256(b"patamaps-package-inputs-v1\0")
    origins = (crate / "package-inputs.tsv").read_bytes()
    digest.update(origins)
    for line in origins.decode().splitlines():
        local, _ = line.split("\t")
        raw = (crate / local).read_bytes()
        digest.update(local.encode())
        digest.update(b"\0")
        digest.update(str(len(raw)).encode())
        digest.update(b"\0")
        digest.update(raw)
    return "sha256:" + digest.hexdigest()


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
            for name, crate, constant in re.findall(r'\(\s*"([^"]+)"\s*,\s*(patamaps_contracts|patamaps_core)::source_identity::([A-Z_]+)\s*,?\s*\)', recipe):
                owner = root / "crates" / crate.replace("_", "-") / "src/source_identity.rs"
                if constant == "PACKAGE_INPUTS_DIGEST":
                    assert re.search(r'pub const PACKAGE_INPUTS_DIGEST: &str\s*=\s*env!\("PATAMAPS_PACKAGE_INPUTS_DIGEST"\);', owner.read_text())
                    value[name] = package_inputs_digest(owner.parent.parent)
                    continue
                matches = re.findall(r'pub const ' + constant + r': &str\s*=\s*include_str!\(\s*"([^"]+)"\s*\);', owner.read_text())
                assert len(matches) == 1, f"Unclassified owner source constant: {constant}"
                value[name] = (owner.parent / matches[0]).read_text()
            for name, literal in re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,?\s*\)', recipe):
                value[name] = literal
            for name in re.findall(r'\(\s*"([^"]+)"\s*,\s*env!\("PATAMAPS_PACKAGE_INPUTS_DIGEST"\)\s*,?\s*\)', recipe):
                value[name] = package_inputs_digest(path.parent.parent)
            declared = re.findall(r'\(\s*"([A-Za-z0-9]+)"\s*,', recipe)
        else:
            start = source.index("json!({")
            recipe = source[start:source.index("}))", start)]
            for name, relative in re.findall(r'"([^"]+)"\s*:\s*include_str!\(\s*"([^"]+)"\s*\)', recipe):
                value[name] = (path.parent / relative).read_text()
            for name, literal in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', recipe):
                value[name] = literal
            for name in re.findall(r'"([^"]+)"\s*:\s*env!\("PATAMAPS_PACKAGE_INPUTS_DIGEST"\)', recipe):
                value[name] = package_inputs_digest(path.parent.parent)
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
    inputs = [collator / "Cargo.toml", collator / "build.rs"]
    for directory in ["src", "data"]:
        if (collator / directory).is_dir():
            inputs.extend(p for p in (collator / directory).rglob("*") if p.is_file())
    for path in sorted(inputs):
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
