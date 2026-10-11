"""Add original licensed scientific evidence, without changing R0 fixtures."""
import hashlib
import json
import subprocess
from pathlib import Path
import argparse
ROOT = Path(__file__).resolve().parents[2]
ENGINE = "399747a4ad05a37cd8db1cedd53048fad2175be4"
parser = argparse.ArgumentParser(); parser.add_argument("reference", type=Path); args = parser.parse_args()
paths = ["standards/sssom-1.0.0/sssom_schema.yaml", "standards/sssom-1.0.0/LICENSE", "standards/sssom-1.0.0/README.md", "schemas/sssom-1.0.0.schema.json", "schemas/sssom-1.0.0-slots.json", "examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv", "examples/scientific-mapping/fixtures/mgi-subset-manifest.json", "examples/scientific-mapping/lookup.mjs", "examples/scientific-mapping/consumer.mjs"]
inventory = []
for name in paths:
    raw = subprocess.check_output(["git", "-C", str(args.reference), "show", f"{ENGINE}:{name}"])
    target = ROOT / "fixtures/reference" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists(): assert target.read_bytes() == raw, name
    else: target.write_bytes(raw)
    inventory.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest()})
value = json.loads((ROOT / "fixtures/reference/relation-packs/scientific-skos.json").read_text())
value.pop("$schema", None); value.update(schemaVersion="0.1.0", documentType="relation-pack")
(ROOT / "relation-packs/scientific-skos.json").write_text(json.dumps(value, indent=2) + "\n")
pin = ROOT / "fixtures/scientific/source-pin.json"
pin.parent.mkdir(parents=True, exist_ok=True)
pin.write_text(json.dumps({"referenceEngine":ENGINE,"sssomSchemaCommit":"658de421c21a686f1213ff41879c9245ac0b4925","preservedFiles":inventory}, indent=2) + "\n")
print(f"Preserved {len(inventory)} licensed scientific files at the pinned reference engine")
