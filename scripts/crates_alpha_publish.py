#!/usr/bin/env python3
"""Publish the frozen Patamaps alpha and retain public-channel evidence."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib
import urllib.error
import urllib.request


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--record", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    inventory = json.loads(args.inventory.read_text())
    expected_commit = "3f54166f8ad4f2071c88de145e2b20ed38355502"
    expected_names = ["patamaps-icu-collator", "patamaps-contracts", "patamaps-core",
                      "patamaps-projection", "patamaps-governance", "patamaps-workspace",
                      "patamaps-scientific", "patamaps-inspect", "patamaps-cli", "patamaps-activator"]

    def source_guard():
        head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
        assert head == expected_commit and not dirty, "Frozen publication source changed"

    assert [item["name"] for item in inventory] == expected_names
    source_guard()
    for item in inventory:
        version = "2.2.1-patamaps.1" if item["name"] == expected_names[0] else "0.1.0-alpha.1"
        assert item["version"] == version and item["sourceCommit"] == expected_commit
        assert digest(item["path"]) == item["sha256"], "Prepared archive changed"
    home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
    assert home.resolve() == Path("/Users/admin/.cargo"), "Use ordinary Intel Cargo home"
    for parent in [source, *source.parents, home.parent]:
        for suffix in [".cargo/config.toml", ".cargo/config"]:
            path = parent / suffix
            if path.is_file():
                config = tomllib.loads(path.read_text())
                assert not config.get("source", {}).get("crates-io", {}).get("replace-with"), str(path)
                assert config.get("registry", {}).get("default", "crates-io") == "crates-io", str(path)
    assert not any(os.environ.get(name) for name in ["CARGO_SOURCE_CRATES_IO_REPLACE_WITH",
                                                      "CARGO_REGISTRIES_CRATES_IO_INDEX"])
    if args.check_only:
        print(json.dumps({"status": "passed", "sourceCommit": expected_commit,
                          "preparedArchives": len(inventory), "registry": "crates-io"}), flush=True)
        return

    token = os.environ.get("CARGO_REGISTRY_TOKEN") or os.environ.get("CARGO_REGISTRIES_CRATES_IO_TOKEN")
    for filename in ["credentials.toml", "credentials"]:
        path = home / filename
        if not token and path.is_file():
            token = tomllib.loads(path.read_text()).get("registry", {}).get("token")
    assert token, "Cargo login is required on Intel; keep the token out of chat"
    output = args.state / args.record
    output.mkdir(parents=True, exist_ok=False)
    environment = {**os.environ, "CARGO_TARGET_DIR": str(args.state / "package-target"),
                   "CARGO_TERM_COLOR": "never"}
    summary = {"startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "sourceCommit": expected_commit, "inventorySha256": digest(args.inventory),
               "driverSha256": digest(__file__), "registry": "crates-io", "packages": []}

    def request(url, missing=False):
        headers = {"User-Agent": "patamaps-alpha-publisher (https://github.com/roryscot/patamaps)"}
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            raise RuntimeError(f"HTTP {error.code} from {url}") from None

    def write_json(path, value):
        with path.open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")

    def cargo(label, arguments):
        source_guard()
        command = ["cargo", *arguments]
        print(json.dumps({"step": label, "command": command}), flush=True)
        start = time.monotonic()
        result = subprocess.run(command, cwd=source, env=environment, capture_output=True, text=True)
        stdout, stderr = [text.replace(token, "[REDACTED]") for text in [result.stdout, result.stderr]]
        for suffix, text in [("stdout.log", stdout), ("stderr.log", stderr)]:
            with (output / (label + "." + suffix)).open("x") as stream:
                stream.write(text)
        receipt = {"command": command, "cwd": str(source), "cargoHome": str(home),
                   "target": environment["CARGO_TARGET_DIR"], "exitCode": result.returncode,
                   "elapsedSeconds": round(time.monotonic() - start, 3)}
        write_json(output / (label + ".receipt.json"), receipt)
        print(json.dumps({"step": label, **receipt}), flush=True)
        if result.returncode:
            print(stderr[-12000:], flush=True)
            raise RuntimeError(f"{label} exited {result.returncode}; inspect registry before any retry")
        source_guard()

    try:
        # The official /me endpoint only accepts browser cookies, not API tokens.
        # Cargo handles private authentication; the registry enforces verified
        # email and public records identify the actual publisher after upload.
        summary["publisher"] = {"expectedLogin": "roryscot",
                                "authentication": "Intel Cargo credential provider",
                                "emailVerification": "enforced by crates.io at upload",
                                "identityVerification": "published_by and owners after each upload"}
        print(json.dumps({"publisher": summary["publisher"]}), flush=True)
        for item in inventory:
            name, version = item["name"], item["version"]
            url = f"https://crates.io/api/v1/crates/{name}/{version}"
            existing = request(url, missing=True)
            if existing is not None:
                current = json.loads(existing)["version"]
                assert current["checksum"] == item["sha256"] and not current["yanked"], "Public version differs"
                action = "already-present"
            else:
                selection = ["--manifest-path", "vendor/icu_collator/Cargo.toml"] if name == expected_names[0] else ["-p", name]
                cargo("preflight-" + name, ["package", "--locked", "--registry", "crates-io", *selection])
                regenerated = args.state / "package-target/package" / Path(item["path"]).name
                assert digest(regenerated) == item["sha256"], f"Regenerated {name} archive differs"
                cargo("publish-" + name, ["publish", "--locked", "--registry", "crates-io", *selection])
                action = "published"
            index_url = "https://index.crates.io/pa/ta/" + name
            indexed = None
            for attempt in range(30):
                raw = request(index_url, missing=True)
                entries = [json.loads(line) for line in raw.splitlines()] if raw else []
                indexed = next((entry for entry in entries if entry["vers"] == version), None)
                if indexed:
                    break
                time.sleep(2)
            assert indexed and indexed["cksum"] == item["sha256"] and not indexed["yanked"], "Public index mismatch"
            api = json.loads(request(url))["version"]
            assert api["checksum"] == item["sha256"] and not api["yanked"], "Public API mismatch"
            assert api.get("published_by", {}).get("login") == "roryscot", "Unexpected actual publisher"
            owners = json.loads(request(f"https://crates.io/api/v1/crates/{name}/owners"))["users"]
            assert "roryscot" in [owner["login"] for owner in owners], "Expected owner is missing"
            archive = output / Path(item["path"]).name
            with archive.open("xb") as stream:
                stream.write(request(f"https://static.crates.io/crates/{name}/{name}-{version}.crate"))
            assert digest(archive) == item["sha256"], "Public download differs from prepared archive"
            result = {"name": name, "version": version, "action": action, "sha256": item["sha256"],
                      "publicDownload": str(archive), "publicBytes": archive.stat().st_size,
                      "owners": [owner["login"] for owner in owners], "index": indexed,
                      "createdAt": api["created_at"]}
            write_json(output / (name + ".json"), result)
            summary["packages"].append(result)
            print(json.dumps({key: result[key] for key in ["name", "version", "action", "sha256"]}), flush=True)
        source_guard()
        summary["status"] = "passed"
    except Exception as error:
        summary.update(status="failed", error=str(error).replace(token, "[REDACTED]"))
        raise
    finally:
        summary["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(output / "publication.json", summary)


if __name__ == "__main__":
    main()
