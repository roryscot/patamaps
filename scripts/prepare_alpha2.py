"""Stage only the two alpha.2 crates with crate-local literal inputs; never publishes."""
import argparse, hashlib, json, os, re, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("patamaps-workspace", "patamaps-cli")
VERSION = "0.1.0-alpha.2"

def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    manifest = (ROOT / "Cargo.toml").read_text()
    manifest = re.sub(r'members = \[.*?\]', 'members = ["crates/patamaps-workspace", "crates/patamaps-cli"]', manifest, count=1, flags=re.S)
    manifest = manifest.replace('exclude = ["vendor/icu_collator"]\n', '')
    for name in re.findall(r'^(patamaps-[a-z-]+) = \{ path = .*$', manifest, re.M):
        value = '{ path = "crates/patamaps-workspace", version = "=0.1.0-alpha.2" }' if name == "patamaps-workspace" else '{ version = "=0.1.0-alpha.1" }'
        manifest = re.sub(r'^' + re.escape(name) + r' = .*$', name + ' = ' + value, manifest, flags=re.M)
    manifest = re.sub(r'^icu_collator = .*$', 'icu_collator = { package = "patamaps-icu-collator", version = "=2.2.1-patamaps.1" }', manifest, flags=re.M)
    (out / "Cargo.toml").write_text(manifest)
    shutil.copyfile(ROOT / "rust-toolchain.toml", out / "rust-toolchain.toml")
    records = []
    for name in NAMES:
        original = ROOT / "crates" / name
        crate = out / "crates" / name
        shutil.copytree(original, crate)
        text = (crate / "Cargo.toml").read_text().replace("version.workspace = true", 'version = "' + VERSION + '"', 1)
        (crate / "Cargo.toml").write_text(text)
        shutil.copyfile(ROOT / "LICENSE", crate / "LICENSE")
        shutil.copyfile(ROOT / "NOTICE", crate / "NOTICE")
        for source in sorted(crate.rglob("*.rs")):
            def replace(match):
                target = (original / source.relative_to(crate)).parent / match[2]
                target = target.resolve(strict=True)
                try:
                    target.relative_to(original)
                    return match[0]
                except ValueError:
                    pass
                rel = target.relative_to(ROOT)
                dest = crate / "package-inputs" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, dest)
                records.append({"crate": name, "source": str(rel), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
                return match[1] + os.path.relpath(dest, source.parent).replace(os.sep, "/") + match[3]
            source.write_text(re.sub(r'(include_(?:str|bytes)!\(\s*")([^"]+)("\s*\))', replace, source.read_text()))
    (out / "staging-receipt.json").write_text(json.dumps({"version": VERSION, "sourceCommit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(), "packages":list(NAMES),"copiedInputs":records,"registryPublication":False},indent=2)+"\n")
    print(out)

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    prepare(parser.parse_args().output.resolve())
