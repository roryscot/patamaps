"""Paired native/MetaMap decisions over actual portable cross-stack facts."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys

REFERENCE = "399747a4ad05a37cd8db1cedd53048fad2175be4"


def reference_runtime(root, work, run):
    reference = root / ".tools/reference/metamap-399747a4ad05"
    if not reference.exists():
        reference = work / "metamap-reference"
        run("m7-reference-clone", ["git", "clone", "--no-checkout", "https://github.com/roryscot/metamap.git", reference], timeout=300)
        run("m7-reference-checkout", ["git", "-C", reference, "checkout", "--detach", REFERENCE])
    assert run("m7-reference-commit", ["git", "-C", reference, "rev-parse", "HEAD"]).decode().strip() == REFERENCE
    assert not run("m7-reference-clean", ["git", "-C", reference, "status", "--porcelain", "--untracked-files=no"])
    names = run("m7-reference-files", ["git", "-C", reference, "ls-files", "-z"]).decode().split("\0")
    before = {name: hashlib.sha256((reference / name).read_bytes()).hexdigest() for name in names if name and (reference / name).is_file()}
    runtime = work / "metamap-runtime"
    runtime.mkdir()
    for name in before:
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((reference / name).read_bytes())
    run("m7-reference-runtime-dependencies", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=runtime, timeout=300)
    run("m7-reference-runtime-build", ["npm", "run", "build"], cwd=runtime, timeout=300)
    assert all(hashlib.sha256((reference / name).read_bytes()).hexdigest() == digest for name, digest in before.items())
    return reference, runtime, before


def verify(root, work, env, run):
    fixture = root / "examples/cross-stack"
    sys.path.insert(0, str(fixture))
    import build
    import workspace
    def commands(prefix):
        def call(label, argv, **kwargs):
            return run(prefix + "-" + label, argv, **kwargs)
        return call
    reference, runtime, reference_before = reference_runtime(root, work, run)
    cli = root / "target/release/patamaps"
    run("m7-cli-build", ["cargo", "build", "--release", "-p", "patamaps-cli", "--locked", "--offline"], timeout=900)
    cargo = Path(run("m7-cargo", ["rustup", "which", "cargo"]).decode().strip()).resolve()
    rustc = Path(run("m7-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
    node = Path(env["PATAMAPS_DEV_NODE"]).resolve()
    # Prefer actual M6 release observations when this phase follows the image
    # lane. Source-only compatibility is separately useful and named as such.
    release_baseline = root / "ci-evidence/cross-stack-image/release-candidate/release-baseline.json"
    if release_baseline.exists():
        raw = release_baseline.read_bytes()
        baseline = json.loads(raw)
        input_scope = "actual-Linux-image-browser-observations"
    else:
        candidate = work / "supported-source"
        owner, config, policy, _ = workspace.prepare(root, fixture, candidate, cli, node, cargo, rustc, commands("m7-source"))
        workspace.bind(candidate, cli, owner, config, policy, commands("m7-source"))
        raw = (candidate / "baseline.json").read_bytes()
        baseline = json.loads(raw)
        input_scope = "source-intent-only; image compatibility not established"
    (work / "baseline-original.json").write_bytes(raw)
    inputs = baseline["captures"][0]["inputs"]
    graph, policy, packs = inputs["graph"], inputs["policy"], inputs["packs"]
    cases = []
    cases_root = work / "native-cases"
    cases_root.mkdir()
    context_path = work / "context.json"
    context_path.write_text(json.dumps(inputs["context"]) + "\n")
    def materialize(label, g, p, code=None):
        folder = cases_root / label
        folder.mkdir()
        paths = []
        for name, value in [("graph.json", g), ("policy.json", p), *[("pack-" + str(i) + ".json", pack) for i, pack in enumerate(packs)]]:
            path = folder / name
            path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
            if name.startswith("pack-"):
                paths.append(str(path))
        cases.append({"control": label, "graphPath": str(folder / "graph.json"), "policyPath": str(folder / "policy.json"), "packPaths": paths, "code": code})
    materialize("m7-supported", graph, policy)
    moved_source = work / "moved-source"
    build.snapshot(fixture, moved_source)
    handler = moved_source / "service/src/handlers/create_item.rs"
    handler.rename(handler.with_name("moved_create_item.rs"))
    path = moved_source / "contracts/operations.json"
    owner = json.loads(path.read_bytes())
    owner["moduleMap"]["catalog"] = "service/src/handlers/moved_create_item.rs"
    owner["operations"][0]["implementation"]["file"] = owner["moduleMap"]["catalog"]
    path.write_text(json.dumps(owner, indent=2) + "\n")
    moved = work / "moved-workspace"
    owner, config, changed_policy, _ = workspace.prepare(root, moved_source, moved, cli, node, cargo, rustc, commands("m7-moved"),
        typescript=fixture / "web/node_modules/typescript")
    workspace.bind(moved, cli, owner, config, changed_policy, commands("m7-moved"))
    previous_rustc = env.get("RUSTC")
    env["RUSTC"] = str(rustc)
    try:
        run("m7-moved-real-cargo", [cargo, "test", "--manifest-path", moved / "app/service/Cargo.toml", "--locked", "--offline"], timeout=300)
    finally:
        if previous_rustc is None:
            env.pop("RUSTC", None)
        else:
            env["RUSTC"] = previous_rustc
    moved_inputs = json.loads((moved / "baseline.json").read_bytes())["captures"][0]["inputs"]
    materialize("m7-moved-handler", moved_inputs["graph"], moved_inputs["policy"])
    missing = copy.deepcopy(graph)
    actual = next((v for v in missing["entities"] if v["kind"] == "build:artifact" and v.get("attributes", {}).get("compilationEstablished") is True), None)
    if actual:
        actual["attributes"]["compilationEstablished"] = False
    else:
        # The source-only variant removes packaging evidence, not a real file.
        binary_requirement = workspace.WORKSPACE + ":requirement:binary-copy"
        mapping = next(v for v in missing["mappings"] if binary_requirement in v["sources"] and v["relation"] == "core:references")
        observed = next(v for v in missing["entities"] if v["id"] == mapping["targets"][0])
        observed["attributes"]["observation"]["sources"] = ["/build/absent-artifact"]
    materialize("m7-missing-artifact", missing, policy, "BUILD_OBSERVATION_BINDING_MISMATCH")
    ambiguous, ambiguous_policy = copy.deepcopy(graph), copy.deepcopy(policy)
    operation = "urn:example:operation:create-item"
    handler = copy.deepcopy(next(v for v in graph["entities"] if v["id"] == operation + ":handler"))
    handler["id"] += ":ambiguous"
    ambiguous["entities"].append(handler)
    mapping = {"id": operation + ":ambiguous-mapping", "relation": "routing:handled_by", "sources": [operation], "targets": [handler["id"]],
               "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}}
    ambiguous["mappings"].append(mapping)
    ambiguous_policy["mappings"].append({"mapping": mapping["id"], "coverage": "total", "determinism": "deterministic", "reversibility": "irreversible"})
    materialize("m7-ambiguous-operation", ambiguous, ambiguous_policy, "NON_UNIQUE_MAPPING_TARGET")
    for label, value, path, code in [("m7-numeric-equivalence", 1.0, ["attributes", "compatibilityNumeric"], None),
                                    ("m7-missing-versus-null", None, ["attributes", "compatibilityMissing"], "BUILD_OBSERVATION_BINDING_MISMATCH"),
                                    ("m7-selector-bound", 1, ["attributes"] * 33, "INVALID_CONSTRAINT_PARAMETERS")]:
        changed, changed_policy = copy.deepcopy(graph), copy.deepcopy(policy)
        target = next(v for v in changed["entities"] if v["kind"] == "cargo-target" and v["attributes"]["name"] == "catalog-service")
        target["attributes"]["compatibilityNumeric"] = 1
        constraint = next(v for v in changed_policy["constraints"] if v["kind"] == "build:observation-binding-v1" and v["parameters"]["targetKind"] == "cargo-target")
        constraint["parameters"]["conditions"].append({"path": path, "equals": value})
        materialize(label, changed, changed_policy, code)
    malformed_source = work / "malformed-source"
    build.snapshot(fixture, malformed_source)
    (malformed_source / "config/service.toml").write_text('[http]\nlisten="0.0.0.0:8080"\nlisten="duplicate"\n')
    malformed = work / "malformed-workspace"
    workspace.prepare(root, malformed_source, malformed, cli, node, cargo, rustc, commands("m7-malformed"), typescript=fixture / "web/node_modules/typescript")
    refused = run("m7-malformed-native-source", [cli, "generate", "pre-workspace.json", "--root", malformed], cwd=malformed, expected_success=False)
    diagnostic = refused.decode() + (work / "m7-malformed-native-source.stderr.log").read_text()
    assert "NATIVE_TOML_SYNTAX" in diagnostic
    unavailable = {"status": "unavailable", "producer": "actual-native-TOML-source", "diagnostic": diagnostic, "graphAvailable": False}
    (work / "unavailable-source.json").write_text(json.dumps(unavailable, indent=2) + "\n")
    cases.append({"control": "m7-malformed-config", "sourceRoot": str(work), "unavailablePath": "unavailable-source.json", "nativeDiagnostic": "NATIVE_TOML_SYNTAX"})
    request = {"referenceRuntime": str(runtime), "executable": str(cli), "output": str(work / "metamap-comparison"), "context": inputs["context"],
               "contextPath": str(context_path), "evaluatedAt": inputs["evaluatedAt"], "cases": cases}
    request_path = work / "metamap-request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n")
    paired = json.loads(run("m7-actual-metamap-compiler", [node, fixture / "compatibility/check.mjs", request_path], timeout=600))
    assert paired["status"] == "passed-portable-facts-metamap-scope"
    assert all(hashlib.sha256((reference / name).read_bytes()).hexdigest() == digest for name, digest in reference_before.items())
    return {"status": "passed-portable-facts-metamap-scope", "inputScope": input_scope, "referenceCommit": REFERENCE,
            "referenceTrackedFilesUnchanged": len(reference_before), "controls": paired["controls"], "fullReleaseAccepted": False,
            "installedConsumer": "separate-required-gate", "nativeCapturesOrApprovalsReusedAsMetamapRecords": False,
            "baselineOriginalDigest": build.digest(raw), "materializedNativeValuePointers": ["/captures/0/inputs/graph", "/captures/0/inputs/policy", "/captures/0/inputs/packs"]}
