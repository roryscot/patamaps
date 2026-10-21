#!/usr/bin/env python3
"""Verify a fresh public-registry alpha install using the accepted runtime checks."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--record", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("accepted_alpha_checks", args.driver)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    accepted = json.loads(args.publication.read_text())
    # The CLI and its libraries can be tested while the independent final
    # activator upload waits for its new-crate quota. Overall release acceptance
    # still requires a separate complete ten-package publication record.
    assert accepted["status"] in {"passed", "partial"}
    assert [item["name"] for item in accepted["packages"]] in [module.ORDER[:9], module.ORDER]
    gate_args = argparse.Namespace(source=args.source, state=args.state, record=args.record,
                                   stage="public-install", expected_source=accepted["sourceCommit"])
    gate = module.Gate(gate_args)
    receipt = gate.receipt
    receipt.update(publicRegistryDownload=True, candidateSourceReplacement=False,
                   publicationRecord=str(args.publication), publicationDigest=module.digest(args.publication),
                   publicVerificationDriverDigest=module.digest(Path(__file__)),
                   cargoHomeFreshForThisAttempt=True, targetFreshForThisAttempt=True,
                   installationProfile="release", activationAttempted=False)
    try:
        work = gate.output / "work"
        work.mkdir(exist_ok=False)
        home, target, installation, consumer, unpacked = [work / name for name in
            ["cargo-home", "target", "installation", "rust-consumer", "unpacked-public-archives"]]
        home.mkdir(exist_ok=False)
        assert not list(home.iterdir())
        (consumer / "src").mkdir(parents=True)
        unpacked.mkdir(exist_ok=False)
        for item in accepted["packages"]:
            archive = Path(item["publicDownload"])
            assert module.digest(archive) == item["sha256"]
            destination = unpacked / ("vendor/icu_collator" if item["name"] == module.FORK else "crates/" + item["name"])
            module.inspect_archive(archive, item["name"], item["version"], destination)
        verifier = work / "identity-verifier.py"
        with (gate.source / "scripts/parity/identity.py").open("rb") as original, verifier.open("xb") as copied:
            shutil.copyfileobj(original, copied)
        libraries = [name for name in module.ORDER if name not in {module.FORK, "patamaps-cli", "patamaps-activator"}]
        versions = [p["version"] for p in tomllib.loads((gate.source / "Cargo.lock").read_text())["package"] if p["name"] == "serde_json"]
        assert len(versions) == 1
        (consumer / "Cargo.toml").write_text('[package]\nname = "alpha-public-registry-consumer"\nversion = "0.0.0"\nedition = "2024"\n[dependencies]\n' +
            ''.join(name + ' = "=' + module.ALPHA + '"\n' for name in libraries) + 'serde_json = "=' + versions[0] + '"\n[workspace]\n')
        (consumer / "src/main.rs").write_text("fn main() {}\n")
        profile = gate.profile("source-unavailable.sb")
        online = gate.output / "public-registry-network.sb"
        online.write_text(profile.read_text().replace("(deny network-outbound)\n", ""))
        denial = 'from pathlib import Path\nfor name in ' + repr([
            str(gate.source / "Cargo.toml"),
            str(Path(os.environ["PATAMAPS_DEV_ROOT"]).resolve() / "crates/patamaps-core/src/lib.rs")]) + ''':
 try: Path(name).read_bytes()
 except PermissionError: continue
 raise AssertionError("development source was readable")
print("development source reads denied")
'''
        python = Path(sys.executable).resolve()
        gate.command("source-denial", [python, "-c", denial], cwd=consumer, sandbox=online)
        gate.command("install-public-cli", ["cargo", "install", "patamaps-cli", "--version", module.ALPHA,
            "--locked", "--registry", "crates-io", "--root", installation],
            cwd=consumer, home=home, target=target, sandbox=online)
        cli = installation / "bin/patamaps"
        engines = json.loads(gate.command("installed-engine", [cli, "engine"], cwd=consumer, sandbox=profile, minimal_path=True))
        code = 'import importlib.util,json; from pathlib import Path; s=importlib.util.spec_from_file_location("identity",' + repr(str(verifier)) + '); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.identities(Path(' + repr(str(unpacked)) + '))))'
        expected = json.loads(gate.command("archive-identities", [python, "-c", code], cwd=consumer, sandbox=profile))
        assert engines == {"schemaVersion": "0.1.0", "documentType": "executor-description", **expected}
        receipt.update(engines=engines, independentArchiveIdentityMatched=True,
                       installedBinaryDigest=module.digest(cli), identityVerifierDigest=module.digest(verifier))
        gate.runtime_consumer(consumer, cli, home, target, profile, unpacked)
        gate.command("consumer-lock", ["cargo", "generate-lockfile"], cwd=consumer, home=home, sandbox=online)
        gate.command("consumer-fetch", ["cargo", "fetch", "--locked"], cwd=consumer, home=home, sandbox=online)
        gate.command("library-consumer", ["cargo", "run", "--locked", "--offline", "--", str(consumer / "cases/after")],
                     cwd=consumer, home=home, target=target, sandbox=profile)
        metadata = json.loads(gate.command("consumer-metadata", ["cargo", "metadata", "--locked", "--offline", "--format-version", "1"],
                             cwd=consumer, home=home, sandbox=profile))
        origins = []
        for package in metadata["packages"]:
            if package["name"] not in module.ORDER:
                continue
            assert package["source"] == "registry+https://github.com/rust-lang/crates.io-index"
            assert Path(package["manifest_path"]).resolve().is_relative_to(home.resolve())
            origins.append({key: package[key] for key in ["name", "version", "source", "manifest_path"]})
        assert {p["name"] for p in origins} == set(libraries) | {module.FORK}
        assert not (home / "config.toml").exists() and not (home / "config").exists()
        receipt.update(registryLibraryOrigins=origins, sourceUnavailableCleanInstall=True,
                       cargoSourceReplacement=False, status="passed")
        gate.check_source()
    except Exception as error:
        receipt.update(status="failed", error=str(error))
        raise
    finally:
        receipt["finishedAt"] = time.time()
        module.save(gate.output / "receipt.json", receipt)
        print(json.dumps({"publicRegistryInstall": receipt["status"], "record": str(gate.output / "receipt.json")}), flush=True)


if __name__ == "__main__":
    main()
