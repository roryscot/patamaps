"""One bounded consumer profile; discovery and admission remain native operations.

This driver creates retained candidates. A viable source graph is not a compiled
Linux artifact, an image, a runtime result, or permission to activate anything.
"""
from pathlib import Path
import copy
import json
import os
import shutil

import build

WORKSPACE = "urn:example:cross-stack:workspace"
AS_OF = "2026-10-15T00:00:00Z"
PACKS = ["routing", "application-topology", "build-deployment"]
NEXT_LITERAL_PROFILE = b'export default { output: "standalone", experimental: { cpus: 2 } };\n'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as out:
        out.write(json.dumps(value, indent=2) + "\n")


def strict_json(cli, path, run, label):
    return json.loads(run(label, [cli, "json", "parse"], cwd=path.parent, input_bytes=path.read_bytes()))


def prepare(repo, source, destination, cli, node, cargo, rustc, run, typescript=None):
    """Freeze source and tools, then generate the existing checked HTTP bindings."""
    owner = strict_json(cli, source / "contracts/operations.json", run, "owner-json")
    if owner.get("nonsecretInputs") is not True:
        raise build.BuildError("CROSS_STACK_NONSECRET_DECLARATION_REQUIRED")
    if len(owner.get("operations", [])) != 1:
        raise build.BuildError("CROSS_STACK_SINGLE_OPERATION_PROFILE")
    destination.mkdir(parents=True, exist_ok=False)
    inventory = build.snapshot(source, destination / "app")
    generated = build.generate(destination / "app", cli, run, rustfmt=rustc.parent / "rustfmt")
    app = destination / "app"
    names = sorted(set(inventory) | set(generated["outputs"]))
    context = destination / "build-context"
    context.mkdir()
    for name in names:
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(app / name, target)
    # Discovery tools never enter the Docker context. Copy only their published
    # source closure; use the exact TypeScript installed for the actual fixture.
    copy_tree = shutil.copytree
    tools = destination / "tooling"
    tools.mkdir()
    copy_tree(repo / "adapters", tools / "adapters")
    modules = tools / "node_modules"
    modules.mkdir()
    copy_tree(repo / "sdk/typescript", modules / "patamaps-native-sdk-draft")
    copy_tree(typescript or source / "web/node_modules/typescript", modules / "typescript")
    for name in PACKS:
        shutil.copyfile(repo / ("relation-packs/" + name + ".json"), destination / (name + ".json"))
    shutil.copyfile(app / ".patamaps/graph.json", destination / "http.json")
    spec = json.loads((app / ".patamaps/projection-spec.json").read_bytes())
    write(destination / "projection.json", spec)
    native = {"executable": str(cli), "arguments": ["discover-native"], "codeInputs": [],
              "bounds": {"maximumElapsedMs": 60000, "maximumStdoutBytes": 16777216, "maximumStderrBytes": 65536}}
    code = sorted(p.relative_to(destination).as_posix() for folder in [tools / "adapters", modules / "patamaps-native-sdk-draft"]
                  for p in folder.rglob("*") if p.is_file() and p.suffix in {".js", ".mjs", ".json"})
    code += ["tooling/node_modules/typescript/lib/typescript.js", "tooling/node_modules/typescript/package.json"]
    def process(name, inputs, config, invocation=None):
        return {"adapter": "process", "id": "urn:example:source:" + name, "invocation": invocation or native,
                "inputs": inputs, "config": config}
    app_inputs = ["app/" + name for name in names]
    next_inputs = [p for p in app_inputs if p.startswith("app/web/app/") and Path(p).suffix in {".ts", ".tsx", ".js", ".jsx"}
                   and Path(p).stem in {"page", "layout", "template", "route", "loading", "error", "global-error", "not-found", "default"}]
    deployment = owner["deployment"]
    operation = owner["operations"][0]
    if operation["cargo"]["platform"] != "x86_64-unknown-linux-gnu" or deployment["platform"] != "linux/amd64" or operation["cargo"]["profile"] != "release":
        raise build.BuildError("CROSS_STACK_PLATFORM_PROFILE_UNSUPPORTED")
    if operation["cargo"]["features"] or operation["cargo"]["requiredFeatures"]:
        raise build.BuildError("CROSS_STACK_FEATURE_PROFILE_UNSUPPORTED")
    cargo_config = {"provider": "cargo", "nonsecretInputs": True,
                    "manifest": "app/" + operation["cargo"]["manifest"], "workspaceManifest": "app/" + operation["cargo"]["manifest"],
                    "lockfile": "app/service/Cargo.lock", "cargo": str(cargo), "cargoDigest": build.digest(cargo.read_bytes()),
                    "rustc": str(rustc), "rustcDigest": build.digest(rustc.read_bytes()),
                    "cargoHome": str(Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))).resolve()),
                    "platform": operation["cargo"]["platform"], "features": operation["cargo"]["features"], "defaultFeatures": True, "view": "resolved"}
    sources = [process("files", app_inputs, {"provider": "files", "nonsecretInputs": True}),
               process("next", next_inputs, {"adapter": "nextjs-app-router", "root": "app/web/app"},
                       {"executable": str(node), "arguments": ["tooling/adapters/metamap-process.mjs"], "codeInputs": code,
                        "bounds": {"maximumElapsedMs": 30000, "maximumStdoutBytes": 16777216, "maximumStderrBytes": 65536}}),
               process("cargo", app_inputs, cargo_config),
               process("toml", ["app/config/service.toml"], {"provider": "toml", "nonsecretInputs": True,
                       "files": [{"path": "app/config/service.toml", "fields": [["http", "listen"]]}]}),
               process("docker", ["build-context/" + name for name in names],
                       {"provider": "dockerfile", "nonsecretInputs": True, "dockerfile": "build-context/deploy/Dockerfile", "context": "build-context",
                        "contextFiles": ["build-context/" + name for name in names], "completeContextSnapshot": True,
                        "target": deployment["runtimeStage"], "platform": deployment["platform"], "frontend": deployment["frontend"], "buildArgs": {}}),
               {"adapter": "portable-shard", "id": "urn:example:source:http", "path": "http.json"}]
    policy = json.loads((app / ".patamaps/policy.json").read_bytes())
    policy["id"] = WORKSPACE + ":policy"
    policy["graph"] = {"id": WORKSPACE, "revision": "1"}
    policy["mappings"].insert(0, {"select": {"provenanceStatuses": ["observed"]}, "coverage": "partial",
                                  "determinism": "deterministic", "reversibility": "irreversible"})
    write(destination / "pre-policy.json", policy)
    config = {"schemaVersion": "0.1.0", "documentType": "workspace-config", "id": WORKSPACE, "namespace": "cross-stack-workspace", "revision": "1",
              "sources": sources, "packs": [p + ".json" for p in PACKS], "policy": "pre-policy.json",
              "projections": [{"path": "projection.json", "emissions": [{"path": "generated/operations.json", "language": "json"}]}],
              "context": {"mode": "source-intent", "platform": deployment["platform"]}, "evaluatedAt": AS_OF}
    write(destination / "pre-workspace.json", config)
    return owner, config, policy, generated


def bind(destination, cli, owner, config, policy, run):
    """Propose all native selector matches; native admission enforces completeness."""
    prepared = json.loads(run("workspace-observe", [cli, "generate", "pre-workspace.json", "--root", destination], cwd=destination))
    baseline = prepared["baseline"]
    graph = baseline["captures"][0]["inputs"]["graph"]
    write(destination / "observed-graph.json", graph)
    overlay = {"schemaVersion": "0.1.0", "documentType": "graph", "id": WORKSPACE + ":owned", "namespace": "cross-stack-owned",
               "entities": [], "mappings": [], "authorities": []}
    policy = copy.deepcopy(policy)
    requirements = []
    packs = [v for p in PACKS for v in ["--relation-pack", destination / (p + ".json")]]

    def requirement(name, kind, fields, semantic=None, relation="core:references"):
        subject = WORKSPACE + ":requirement:" + name
        overlay["entities"].append({"id": subject, "kind": "build:requirement", "attributes": {"evidenceClass": "owner-authored", "name": name}})
        constraint = {"id": subject + ":observations", "kind": "build:observation-binding-v1", "subjects": [subject],
                      "parameters": {"relation": relation, "targetKind": kind,
                                     "conditions": [{"path": ["attributes", *key.split(".")], "equals": value} for key, value in fields.items()]}}
        path = destination / "queries" / (name + ".json")
        write(path, constraint)
        query = json.loads(run("query-" + name, [cli, "match-observations", destination / "observed-graph.json", path, *packs], cwd=destination))
        for i, target in enumerate(query["matches"]):
            mid = subject + ":binding:" + str(i)
            overlay["mappings"].append({"id": mid, "relation": relation, "sources": [subject], "targets": [target],
                                        "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
            policy["mappings"].append({"mapping": mid, "coverage": "total", "determinism": "deterministic", "reversibility": "irreversible"})
            if semantic:
                overlay["mappings"].append({"id": mid + ":meaning", "relation": "core:implements", "sources": [semantic], "targets": [target],
                                            "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
        policy["constraints"].append(constraint)
        for constraint_kind in ["core:requires-mapping", "core:unique-target"]:
            policy["constraints"].append({"id": subject + ":" + constraint_kind, "kind": constraint_kind, "subjects": [subject], "parameters": {"relation": relation, "direction": "source"}})
        requirements.append({"name": name, "matches": query["matches"]})
        return query["matches"]

    for view in owner["views"]:
        overlay["entities"].append({"id": view["id"], "kind": "build:view", "attributes": {"evidenceClass": "owner-authored"}})
        requirement(view["name"] + "-page", "topology:page",
                    {"adapter": "nextjs-app-router", "repositoryPath": "app/" + view["file"], "routePath": view["path"]}, view["id"])
        for i, operation in enumerate(view["operations"]):
            overlay["mappings"].append({"id": view["id"] + ":uses-operation:" + str(i), "relation": "core:depends_on", "sources": [view["id"]], "targets": [operation],
                                        "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
    for op in owner["operations"]:
        for kind in ["routing:route", "routing:handler"]:
            requirement("operation-next-" + kind.split(":")[1], kind,
                        {"adapter": "nextjs-app-router", "repositoryPath": "app/" + op["frontend"]["file"], "routePath": op["frontend"]["path"], "method": op["frontend"]["method"]}, op["id"])
        requirement("operation-next-endpoint", "routing:endpoint", {"adapter": "nextjs-app-router", "path": op["frontend"]["path"], "method": op["frontend"]["method"]}, op["id"])
        requirement("cargo-package", "cargo-package", {"name": op["cargo"]["package"], "manifest": "app/" + op["cargo"]["manifest"]})
        targets = requirement("cargo-target", "cargo-target", {"name": op["cargo"]["target"], "kind": ["bin"], "source": "app/service/src/main.rs", "requiredFeatures": op["cargo"]["requiredFeatures"],
                    "discoveryContext.manifest": "app/" + op["cargo"]["manifest"], "discoveryContext.platformFilter": op["cargo"]["platform"],
                    "discoveryContext.features": op["cargo"]["features"], "discoveryContext.defaultFeatures": True, "discoveryContext.view": "resolved"})
        for i, target in enumerate(targets):
            overlay["mappings"].append({"id": op["id"] + ":compiled-into:" + str(i), "relation": "build:compiled_into", "sources": [op["id"] + ":handler"], "targets": [target],
                                        "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
    deployment = owner["deployment"]
    requirement("listener", "toml-key", {"path": "app/config/service.toml", "observation.key": ["http", "listen"],
                                         "observation.value": {"type": "string", "value": deployment["listener"]}})
    requirement("next-config", "build:input", {"file": "app/web/next.config.mjs", "digest": build.digest(NEXT_LITERAL_PROFILE)})
    builder = requirement("builder", "docker-stage", {"alias": deployment["builderStage"], "dockerfile": "build-context/deploy/Dockerfile", "platform": deployment["platform"]})
    by_id = {e["id"]: e for e in graph["entities"]}
    builder_index = by_id[builder[0]]["attributes"]["index"] if len(builder) == 1 else -1
    runtime = {"alias": deployment["runtimeStage"], "dockerfile": "build-context/deploy/Dockerfile", "platform": deployment["platform"],
               "workdir": "/app", "entrypoint": [deployment["executable"]], "cmd": [deployment["configDestination"]], "expose": ["8080"], "unsupportedReasons": []}
    runtime_ids = requirement("runtime", "docker-stage", runtime)
    artifact_source = "/build/service/target/" + op["cargo"]["platform"] + "/release/" + op["cargo"]["target"]
    requirement("binary-copy", "docker-instruction", {"file": "build-context/deploy/Dockerfile", "instruction": "copy_instruction",
                "observation.fromStageIndex": builder_index, "observation.sources": [artifact_source],
                "observation.resolvedDestination": deployment["executable"] , "supportedSyntaxAndResolution": True})
    config_digest = build.digest((destination / "build-context/config/service.toml").read_bytes())
    requirement("config-copy", "docker-instruction", {"file": "build-context/deploy/Dockerfile", "instruction": "copy_instruction", "supportedSyntaxAndResolution": True,
                "observation.contextMembers": [{"source": "build-context/config/service.toml", "destination": deployment["configDestination"], "digest": config_digest, "bytesCaptured": True}]})
    # RUN is a declared recipe, never a proved artifact. Full release acceptance
    # still requires an actual selected-platform build and independent runtime.
    recipe = "RUN cargo build --manifest-path " + op["cargo"]["manifest"] + " --locked --release --target " + op["cargo"]["platform"] + " --message-format=json-render-diagnostics > /build/cargo-messages.jsonl && rustc -Vv > /build/rustc-version.txt && sh service/tools/collect-notices.sh /build/licenses"
    requirement("build-recipe", "docker-instruction", {"file": "build-context/deploy/Dockerfile", "instruction": "run_instruction", "lexeme": recipe})
    artifact_id = owner["operations"][0]["id"] + ":linux-artifact"
    config_id = WORKSPACE + ":configuration"
    overlay["entities"].extend([
        {"id": artifact_id, "kind": "build:artifact", "attributes": {"evidenceClass": "declared-build-intent", "compilationEstablished": False,
          "platform": deployment["platform"], "cargo": owner["operations"][0]["cargo"], "path": artifact_source}},
        {"id": config_id, "kind": "build:configuration", "attributes": {"evidenceClass": "captured-file-receipt", "digest": config_digest,
          "source": "build-context/config/service.toml", "destination": deployment["configDestination"], "imageContentsEstablished": False}}])
    declared_links = [("build:produces", target, artifact_id) for target in targets]
    declared_links += [(relation, stage, target) for stage in runtime_ids for relation, target in
                      [("deployment:packages", artifact_id), ("deployment:packages", config_id), ("deployment:starts", artifact_id)]]
    for i, (relation, source, target) in enumerate(declared_links):
        overlay["mappings"].append({"id": WORKSPACE + ":build-intent:" + str(i), "relation": relation, "sources": [source], "targets": [target],
                                    "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
    policy["constraints"].append({"id": WORKSPACE + ":next-totality", "kind": "topology:relation-totality", "subjects": [WORKSPACE],
              "parameters": {"subjectKinds": ["routing:route", "routing:handler", "routing:endpoint", "topology:page"], "subjectAttributes": {"adapter": "nextjs-app-router"},
                             "relation": "core:implements", "direction": "target", "cardinality": "exactly-one", "counterpartKinds": ["routing:command", "build:view"]}})
    policy["constraints"].append({"id": WORKSPACE + ":run-totality", "kind": "topology:relation-totality", "subjects": [WORKSPACE],
              "parameters": {"subjectKinds": ["docker-instruction"], "subjectAttributes": {"instruction": "run_instruction"},
                             "relation": "core:references", "direction": "target", "cardinality": "exactly-one", "counterpartKinds": ["build:requirement"]}})
    directly_declared = {value["mapping"] for value in policy["mappings"] if "mapping" in value}
    for mapping in overlay["mappings"]:
        if mapping["id"] not in directly_declared:
            policy["mappings"].append({"mapping": mapping["id"], "coverage": "total", "determinism": "deterministic", "reversibility": "irreversible"})
    write(destination / "owned.json", overlay)
    write(destination / "policy.json", policy)
    config = copy.deepcopy(config)
    config["sources"].append({"adapter": "portable-shard", "id": "urn:example:source:owned", "path": "owned.json"})
    config["policy"] = "policy.json"
    write(destination / "workspace.json", config)
    result = json.loads(run("workspace-admit", [cli, "generate", "workspace.json", "--root", destination], cwd=destination))
    assert result["cacheHits"] == 0
    for relative, content in result["baseline"]["outputs"].items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as out:
            out.write(content)
    write(destination / "baseline.json", result["baseline"])
    run("workspace-offline", [cli, "verify-workspace", destination / "baseline.json"], cwd=destination)
    receipt = {"status": "source-intent-graph-viable", "requirements": requirements, "baseline": result["baseline"]["digest"],
               "compilation": "not-established", "image": "not-established", "runtime": "not-established", "fullReleaseAccepted": False,
               "unsupported": ["RUN effects require independent build evidence", "one reviewed literal Next configuration only"],
               "activation": "not-performed"}
    write(destination / "source-intent.json", receipt)
    return receipt
