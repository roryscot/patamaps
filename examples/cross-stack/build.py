"""Consumer-owned source staging; native admission/emission and Cargo do the checking.

Only fresh candidate directories are written. No selected output, trust store,
production service or old candidate is overwritten or removed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess


class BuildError(Exception):
    pass


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def owned(root, relative):
    lexical = Path(relative)
    if lexical.is_absolute() or any(p in {".", "..", ""} for p in relative.split("/")):
        raise BuildError("HTTP_MODULE_OUTSIDE_OWNER: " + relative)
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()):
        raise BuildError("HTTP_MODULE_OUTSIDE_OWNER: " + relative)
    return path


def snapshot(source, destination):
    source = source.resolve()
    if destination.resolve(strict=False).is_relative_to(source):
        raise BuildError("HTTP_SNAPSHOT_DESTINATION_INSIDE_SOURCE")
    destination.mkdir(parents=True, exist_ok=False)
    inventory = {}
    total = 0
    for directory, dirs, names in os.walk(source, followlinks=False):
        dirs[:] = sorted(v for v in dirs if v not in {"node_modules", ".next", "target", "runs", ".patamaps", "generated", "__pycache__", ".git"})
        if any((Path(directory) / name).is_symlink() for name in dirs):
            raise BuildError("HTTP_SNAPSHOT_DIRECTORY_SYMLINK")
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(source).as_posix()
            if name in {"generated.rs", "next-env.d.ts", "tsconfig.tsbuildinfo"}:
                continue
            if name == ".env" or name.startswith(".env."):
                raise BuildError("HTTP_SNAPSHOT_SECRET_INPUT_UNAVAILABLE: " + relative)
            actual = owned(source, relative)
            if path.is_symlink() or not actual.is_file():
                raise BuildError("HTTP_SNAPSHOT_SYMLINK: " + relative)
            raw = actual.read_bytes()
            total += len(raw)
            if total > 16777216:
                raise BuildError("HTTP_SNAPSHOT_INPUT_LIMIT")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as out:
                out.write(raw)
            inventory[relative] = {"digest": digest(raw), "byteLength": len(raw)}
    return inventory


def generate(root, cli, run, rustfmt=None):
    root = root.resolve()
    state = root / ".patamaps"
    state.mkdir(exist_ok=False)
    manifest_bytes = (root / "contracts/operations.json").read_bytes()
    def strict_json(label, raw):
        return json.loads(run(label, [cli, "json", "parse"], cwd=root, input_bytes=raw))

    manifest = strict_json("http-owner-json", manifest_bytes)
    if manifest.get("nonsecretInputs") is not True:
        raise BuildError("HTTP_NONSECRET_DECLARATION_REQUIRED")
    if manifest["profile"] != "patamaps-cross-stack-fixture-1" or not 1 <= len(manifest["operations"]) <= 64:
        raise BuildError("HTTP_OWNER_MANIFEST_PROFILE")
    ids = [op["id"] for op in manifest["operations"]]
    if len(set(ids)) != len(ids):
        raise BuildError("HTTP_DUPLICATE_OPERATION")
    modules = manifest["moduleMap"]
    graph = {"schemaVersion": "0.1.0", "documentType": "graph", "id": "urn:example:cross-stack:http", "revision": "1", "namespace": "cross-stack-http",
             "relationPacks": [{"id": "urn:metamap:relation-pack:core", "version": "1.0.0"}, {"id": "urn:metamap:relation-pack:routing", "version": "1.0.0"}],
             "entities": [], "mappings": [], "authorities": []}
    policy = {"schemaVersion": "0.1.0", "documentType": "policy", "id": "urn:example:cross-stack:http-policy", "graph": {"id": graph["id"], "revision": "1"}, "mappings": [], "constraints": [], "evidence": []}
    source_receipts = {"contracts/operations.json": digest(manifest_bytes)}
    for index, op in enumerate(manifest["operations"]):
        implementation = op["implementation"]
        module = implementation["module"]
        filename = modules.get(module)
        if filename != implementation["file"] or not filename.startswith("service/src/"):
            raise BuildError("HTTP_MODULE_MAP_MISMATCH")
        source = owned(root, filename).read_bytes()
        source.decode("utf-8", errors="strict")
        source_receipts[filename] = digest(source)
        request_path = op["schemas"]["request"]
        response_path = op["schemas"]["response"]
        request = owned(root, request_path).read_bytes()
        response = owned(root, response_path).read_bytes()
        source_receipts.update({request_path: digest(request), response_path: digest(response)})
        handler_id, input_id, endpoint_id = (op["id"] + suffix for suffix in [":handler", ":input", ":endpoint"])
        graph["entities"].extend([
            {"id": op["id"], "kind": "routing:command", "attributes": {"http": {k: op["frontend"][k] for k in ["method", "path"]}}},
            {"id": handler_id, "kind": "routing:handler", "locators": [{"uri": "rust:crate::" + module + "::" + implementation["symbol"], "digest": digest(source)}],
             "attributes": {"http": {"profile": op.get("httpProfile", "patamaps-http-object-strings-1"), "modulePath": filename.removeprefix("service/src/"),
                                      "requestType": implementation["request"], "responseType": implementation["response"], "errorType": implementation["error"],
                                      "errors": op["errors"], "responseSchema": strict_json("http-response-schema-" + str(index), response)}}},
            {"id": input_id, "kind": "routing:schema", "locators": [{"uri": "json-schema:" + request_path, "digest": digest(request)}], "attributes": {"jsonSchema": strict_json("http-request-schema-" + str(index), request)}},
            {"id": endpoint_id, "kind": "routing:endpoint", "attributes": {"http": {**op["endpoint"], "successStatus": op["successStatus"]}}},
        ])
        for name, relation, target in [("handler", "routing:handled_by", handler_id), ("input", "routing:accepts", input_id), ("endpoint", "routing:exposed_as", endpoint_id)]:
            mid = op["id"] + ":mapping:" + name
            graph["mappings"].append({"id": mid, "relation": relation, "sources": [op["id"]], "targets": [target], "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
            policy["mappings"].append({"mapping": mid, "coverage": "total", "determinism": "deterministic", "reversibility": "irreversible"})
            for kind in ["core:requires-mapping", "core:unique-target"]:
                policy["constraints"].append({"id": mid + ":" + kind, "kind": kind, "subjects": [op["id"]], "parameters": {"relation": relation, "direction": "source"}})
        graph["authorities"].append({"id": op["id"] + ":authority", "concept": op["id"], "source": op["id"], "facts": ["operation-identity"], "mode": "canonical", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
    spec = {"schemaVersion": "0.1.0", "documentType": "projection-spec", "id": "urn:example:cross-stack:http-projection", "select": {"kinds": ["routing:command"]},
            "slots": [{"name": name, "relation": relation, "direction": "outgoing", "cardinality": "exactly-one", "targetKinds": [kind]}
                      for name, relation, kind in [("handler", "routing:handled_by", "routing:handler"), ("input", "routing:accepts", "routing:schema"), ("endpoint", "routing:exposed_as", "routing:endpoint")]]}
    for name, value in [("graph.json", graph), ("policy.json", policy), ("projection-spec.json", spec), ("context.json", {})]:
        (state / name).write_text(json.dumps(value, indent=2) + "\n")
    common = [cli, "link", state / "graph.json", state / "policy.json", state / "projection-spec.json", "--relation-pack", root / "mappings/routing-pack.json", "--as-of", "2026-10-15T00:00:00Z", "--context", state / "context.json"]
    projection = json.loads(run("http-projection", common, cwd=root))
    rust = run("http-rust", [*common, "--format", "http-rust"], cwd=root)
    typescript = run("http-typescript", [*common, "--format", "http-typescript"], cwd=root)
    rust_path = root / "service/src/generated.rs"
    typescript_path = root / "web/generated/operations.ts"
    typescript_path.parent.mkdir(parents=True, exist_ok=True)
    for p, raw in [(rust_path, rust), (typescript_path, typescript)]:
        with p.open("xb") as out:
            out.write(raw)
    # Formatting does not choose source, symbols, types or semantics.
    run("http-rust-format", [rustfmt or "rustfmt", "--edition", "2024", rust_path], cwd=root)
    for name, expected in source_receipts.items():
        if digest(owned(root, name).read_bytes()) != expected:
            raise BuildError("HTTP_SOURCE_CHANGED_DURING_GENERATION: " + name)
    source_receipts.update({"service/src/lib.rs": digest((root / "service/src/lib.rs").read_bytes()), "service/src/main.rs": digest((root / "service/src/main.rs").read_bytes())})
    result = {"profile": "patamaps-consumer-http-build-1", "status": "generated-candidate", "projection": projection,
              "sourceBytes": source_receipts, "moduleMap": modules, "operationIds": ids,
              "outputs": {str(p.relative_to(root)): digest(p.read_bytes()) for p in [rust_path, typescript_path]},
              "compilation": "not-run-by-generation", "runtime": "not-run-by-generation", "fullExecutableClosure": "not-established", "authorization": "not-evaluated", "activation": "not-evaluated"}
    (state / "generation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    declaration = subprocess.run([str(args.compiler.resolve()), "json", "parse"], input=(args.root / "contracts/operations.json").read_bytes(), capture_output=True, timeout=10, check=True)
    if json.loads(declaration.stdout).get("nonsecretInputs") is not True:
        raise BuildError("HTTP_NONSECRET_DECLARATION_REQUIRED")
    inventory = snapshot(args.root, args.candidate)
    logs = args.candidate / "build-logs"
    logs.mkdir()
    commands = []

    def run(label, argv, cwd, input_bytes=None):
        with (logs / (label + ".stdout.log")).open("xb") as out, (logs / (label + ".stderr.log")).open("xb") as err:
            result = subprocess.run([str(v) for v in argv], cwd=cwd, stdout=out, stderr=err, timeout=90, input=input_bytes)
        commands.append({"label": label, "argv": [str(v) for v in argv], "exitCode": result.returncode})
        (logs / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if result.returncode:
            raise BuildError(label + " failed; logs: " + str(logs))
        return (logs / (label + ".stdout.log")).read_bytes()

    result = generate(args.candidate, args.compiler.resolve(), run)
    result["snapshot"] = inventory
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
