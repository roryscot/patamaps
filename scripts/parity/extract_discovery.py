"""Extract licensed discovery facts only; no reference compiler at runtime."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / json.loads((ROOT / ".tools/parity/oracles/current.json").read_text())["source"]
DESTINATION = ROOT / "adapters/discovery"
SUPPLEMENT = json.loads((ROOT / "fixtures/parity/supplement.json").read_text())
parser = argparse.ArgumentParser()
parser.add_argument("--refresh-private-types", action="store_true", help="Regenerate private configuration declarations and their derived provenance")
args = parser.parse_args()
for item in SUPPLEMENT["referenceTree"]:
    raw = (ORACLE / item["path"]).read_bytes()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == item["gitBlob"], item["path"]

providers = ["prisma", "typescript-zod", "nextjs-app-router", "json-collections", "legacy-sources", "source-of-truth", "sssom-tsv", "metamap-shard", "types"]
modules = ["model", "references", "stable"] + ["adapters/" + name for name in providers]
sha = lambda raw: "sha256:" + hashlib.sha256(raw).hexdigest()
inventory = []
for module in modules:
    for extension in ["js", "d.ts"]:
        source = ORACLE / f"dist/{module}.{extension}"
        target = DESTINATION / f"{module}.{extension}"
        raw = source.read_bytes()
        transformed = re.sub(rb"\n?//# sourceMappingURL=[^\n]*\n?$", b"\n", raw)
        transformation = "Remove the trailing source-map locator; preserve executable code and declarations"
        if module == "adapters/metamap-shard" and extension == "js":
            old = b'../../schemas/metamap-graph.schema.json'
            assert transformed.count(old) == 1
            transformed = transformed.replace(old, b'../schemas/metamap-graph.schema.json')
            transformation += "; relocate the unmodified graph schema inside this package by changing only its relative URL"
        if target.exists():
            assert target.read_bytes() == transformed, f"Do not overwrite a modified provider: {target}"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(transformed)
        origin = ORACLE / f"src/{module}.ts"
        inventory.append({"path": target.relative_to(DESTINATION).as_posix(), "digest": sha(transformed),
                          "compiledOrigin": source.relative_to(ORACLE).as_posix(), "compiledOriginDigest": sha(raw),
                          "sourceOrigin": origin.relative_to(ORACLE).as_posix(), "sourceOriginDigest": sha(origin.read_bytes()),
                          "transformation": transformation})

# Graph facts refer to the risk-assessment types in this private declaration.
# Extract its type closure only, never the reference viability implementation.
source = ORACLE / "dist/viability-model.d.ts"
raw = source.read_bytes()
transformed = re.sub(rb"\n?//# sourceMappingURL=[^\n]*\n?$", b"\n", raw)
target = DESTINATION / "viability-model.d.ts"
if target.exists():
    assert target.read_bytes() == transformed, "Do not overwrite private risk types"
else:
    with target.open("xb") as output:
        output.write(transformed)
inventory.append({"path": "viability-model.d.ts", "digest": sha(transformed), "compiledOrigin": "dist/viability-model.d.ts",
                  "compiledOriginDigest": sha(raw), "sourceOrigin": "src/viability-model.ts",
                  "sourceOriginDigest": sha((ORACLE / "src/viability-model.ts").read_bytes()),
                  "transformation": "Private type closure only; remove the trailing source-map locator; no runtime viability implementation"})

# Providers import configuration interfaces only. Do not advertise reference
# configuration loaders or parsers that this package does not implement.
source = ORACLE / "dist/config.d.ts"
raw = source.read_bytes()
text = raw.decode()
text = re.sub(r"^export declare (?:const METAMAP_CONFIG_VERSION|function parseMetamapConfig|function loadMetamapConfig)[^\n]*\n", "", text, flags=re.MULTILINE)
text = text.replace("typeof METAMAP_CONFIG_VERSION", '"1.0.0"')
text = re.sub(r"\n?//# sourceMappingURL=[^\n]*\n?$", "\n", text)
target = DESTINATION / "config.d.ts"
if target.exists():
    if target.read_text() != text:
        assert args.refresh_private_types, "Do not overwrite modified private configuration types"
        target.write_text(text)
else:
    with target.open("x") as output:
        output.write(text)
inventory.append({"path": "config.d.ts", "digest": sha(text.encode()), "compiledOrigin": "dist/config.d.ts",
                  "compiledOriginDigest": sha(raw), "sourceOrigin": "src/config.ts",
                  "sourceOriginDigest": sha((ORACLE / "src/config.ts").read_bytes()),
                  "transformation": "Retain private interfaces; inline the 1.0.0 version type; omit unimplemented runtime config parser/loader/version declarations and source-map locator"})
for name in ["LICENSE", "NOTICE"]:
    target = DESTINATION / name
    raw = (ORACLE / name).read_bytes()
    if target.exists():
        assert target.read_bytes() == raw
    else:
        with target.open("xb") as output:
            output.write(raw)
source = ORACLE / "relation-packs/scientific-skos.json"
target = DESTINATION / "profiles/scientific-skos.json"
raw = source.read_bytes()
if target.exists():
    assert target.read_bytes() == raw, "Do not overwrite modified pinned profile data"
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(raw)
inventory.append({"path": "profiles/scientific-skos.json", "digest": sha(raw),
                  "sourceOrigin": "relation-packs/scientific-skos.json", "sourceOriginDigest": sha(raw),
                  "transformation": "Unmodified licensed bundled relation data; no relation-pack parser or policy implementation is extracted"})
source = ORACLE / "schemas/metamap-graph.schema.json"
target = DESTINATION / "schemas/metamap-graph.schema.json"
raw = source.read_bytes()
if target.exists():
    assert target.read_bytes() == raw, "Do not overwrite modified pinned graph shape data"
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(raw)
inventory.append({"path": "schemas/metamap-graph.schema.json", "digest": sha(raw),
                  "sourceOrigin": "schemas/metamap-graph.schema.json", "sourceOriginDigest": sha(raw),
                  "transformation": "Unmodified licensed shard shape schema; semantic validation remains in the composed native workspace"})
receipt = {"schemaVersion": "1.0.0", "referenceEngine": SUPPLEMENT["referenceEngine"],
           "referencePackage": "@roryscot/metamap@0.7.1", "license": "Apache-2.0", "originalTreeFilesVerified": len(SUPPLEMENT["referenceTree"]),
           "scope": "Seven framework/file/scientific/shard discovery providers and their fact/type helpers and fixed relation/schema data. Ajv validates the unmodified legacy shard shape only; scientific parsing and canonical hashing delegate to the native SDK. No scientific parser, admission, policy, semantic graph evaluation, governance or compiler implementation is extracted.",
           "files": inventory}
path = DESTINATION / "provenance.json"
encoded = (json.dumps(receipt, indent=2) + "\n").encode()
if path.exists():
    if path.read_bytes() != encoded:
        assert args.refresh_private_types, "Extraction provenance changed"
        path.write_bytes(encoded)
else:
    with path.open("xb") as output:
        output.write(encoded)
print(json.dumps({"status": "extracted-and-verified", "files": len(inventory), "path": str(DESTINATION.relative_to(ROOT)), "referenceEngine": receipt["referenceEngine"]}))
