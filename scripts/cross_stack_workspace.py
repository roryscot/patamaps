"""Real-provider M4 composition, refusal and captured offline reconstruction controls."""
from pathlib import Path
import json
import sys


def verify(root, work, env, run):
    run("m4-format", ["cargo", "fmt", "--all", "--", "--check"])
    run("m4-kernel-tests", ["cargo", "test", "-p", "patamaps-core", "--test", "build_observations", "--locked", "--offline"])
    run("m4-native-tests", ["cargo", "test", "-p", "patamaps-workspace", "--lib", "--locked", "--offline"])
    run("m4-cli", ["cargo", "build", "-p", "patamaps-cli", "--locked", "--offline"])
    cli = root / "target/debug/patamaps"
    cargo = Path(run("m4-cargo", ["rustup", "which", "cargo"]).decode().strip()).resolve()
    rustc = Path(run("m4-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
    node = Path(env["PATAMAPS_DEV_NODE"]).resolve()
    fixture = root / "examples/cross-stack"
    sys.path.insert(0, str(fixture))
    import build
    import workspace
    controls = []
    cases = work / "cases"
    cases.mkdir()

    def case(label, mutate=None, refusal=None):
        source = cases / (label + "-source")
        build.snapshot(fixture, source)
        if mutate:
            mutate(source)
        owner = cases / label

        def command(name, argv, **kwargs):
            failing = refusal is not None and name == "workspace-admit"
            value = run(label + "-" + name, argv, expected_success=not failing, **kwargs)
            if failing:
                message = value.decode() + (work / (label + "-" + name + ".stderr.log")).read_text()
                assert refusal in message, message
                raise build.BuildError(refusal)
            return value

        try:
            manifest, config, policy, generated = workspace.prepare(root, source, owner, cli, node, cargo, rustc, command,
                                                                    typescript=fixture / "web/node_modules/typescript")
            if label == "m4-real-chain":
                aliases = {"provider": cli, "cargo": cargo, "rustc": rustc}
                for name, executable in aliases.items():
                    (owner / (name + "-captured")).symlink_to(executable)
                for source_config in config["sources"]:
                    if source_config["adapter"] == "process" and source_config["id"] != "urn:example:source:next":
                        source_config["invocation"]["executable"] = str(owner / "provider-captured")
                    if source_config["id"] == "urn:example:source:cargo":
                        source_config["config"]["cargo"] = str(owner / "cargo-captured")
                        source_config["config"]["rustc"] = str(owner / "rustc-captured")
                (owner / "pre-workspace.json").write_text(json.dumps(config, indent=2) + "\n")
            receipt = workspace.bind(owner, cli, manifest, config, policy, command)
        except build.BuildError as error:
            if refusal is None or refusal not in str(error):
                raise
            controls.append({"control": label, "result": "refused", "code": refusal, "candidateSelected": False})
            return owner
        assert refusal is None, label + " unexpectedly passed"
        assert receipt["fullReleaseAccepted"] is False
        assert len(receipt["requirements"]) == 15
        assert all(len(v["matches"]) == 1 for v in receipt["requirements"]), receipt
        controls.append({"control": label, "result": "source-intent-viable", "baseline": receipt["baseline"], "fullReleaseAccepted": False})
        return owner

    def replace(path, old, new):
        def mutate(owner):
            p = owner / path
            text = p.read_text()
            assert old in text
            p.write_text(text.replace(old, new))
        return mutate

    baseline = case("m4-real-chain")
    relocated = case("m4-relocated-chain")
    first = json.loads((baseline / "baseline.json").read_bytes())
    second = json.loads((relocated / "baseline.json").read_bytes())
    assert first["captures"][0]["inputs"]["graph"]["entities"] == second["captures"][0]["inputs"]["graph"]["entities"]
    changed_lock = case("m4-lock-lineage", lambda owner: (owner / "service/Cargo.lock").write_text(
                        (owner / "service/Cargo.lock").read_text() + "\n# independent lineage control\n"))
    assert json.loads((changed_lock / "baseline.json").read_bytes())["digest"] != first["digest"]
    case("m4-new-unmapped-route", lambda owner: ((owner / "web/app/extra").mkdir(),
         (owner / "web/app/extra/page.tsx").write_text("export default function Extra(){ return <p>extra</p>; }\n")), "TOPOLOGY_REQUIRED_RELATION_MISSING")
    case("m4-wrong-next-method", replace("web/app/api/items/route.ts", "function POST", "function PUT"), "REQUIRED_MAPPING_MISSING")
    case("m4-wrong-binary-copy", replace("deploy/Dockerfile", "/release/catalog-service", "/release/other-service"), "REQUIRED_MAPPING_MISSING")
    case("m4-config-ignored", replace(".dockerignore", "**/.tools", "**/.tools\nconfig/service.toml"), "REQUIRED_MAPPING_MISSING")
    case("m4-wrong-runtime-listener", replace("config/service.toml", "0.0.0.0:8080", "127.0.0.1:9090"), "REQUIRED_MAPPING_MISSING")
    case("m4-extra-opaque-run", replace("deploy/Dockerfile", "WORKDIR /app", "WORKDIR /app\nRUN echo unproved"), "TOPOLOGY_REQUIRED_RELATION_MISSING")
    case("m4-dynamic-next-config", replace("web/next.config.mjs", "export default", "const env = process.env;\nexport default"), "REQUIRED_MAPPING_MISSING")
    case("m4-disabled-required-feature", lambda owner: (owner / "service/Cargo.toml").write_text(
         (owner / "service/Cargo.toml").read_text() + '\n[features]\nflag=[]\n[[bin]]\nname="catalog-service"\npath="src/main.rs"\nrequired-features=["flag"]\n'), "REQUIRED_MAPPING_MISSING")
    # Offline reconstruction checks captured records without Node, Cargo or any
    # provider on PATH. It does not rediscover or authenticate current sources.
    moves = []
    for name in ["app", "tooling", "build-context", "provider-captured", "cargo-captured", "rustc-captured"]:
        source = baseline / name
        target = baseline / (name + ".retained")
        source.rename(target)
        moves.append({"configuredPathUnavailable": str(source), "preservedAt": str(target)})
    old = dict(env)
    try:
        env["PATH"] = "/cross-stack-no-external-programs"
        result = json.loads(run("m4-offline-no-tools", [cli, "verify-workspace", baseline / "baseline.json"], cwd=baseline))
    finally:
        env.clear()
        env.update(old)
    assert result["status"] == "verified-record-bindings" and result["sourceRediscovery"] == "not-performed", result
    controls.append({"control": "m4-offline-no-tools", "result": "verified-record-bindings", "sourceRediscovery": "not-performed", "retainedMoves": moves})
    tampered = json.loads((baseline / "baseline.json").read_bytes())
    tampered["discovery"][0]["adapterVersion"] = "substituted-version"
    tampered.pop("digest")
    tampered["digest"] = json.loads(run("m4-tamper-rehash", [cli, "json", "digest"], input_bytes=json.dumps(tampered).encode()))
    forged = work / "tampered-rehashed-baseline.json"
    forged.write_text(json.dumps(tampered, indent=2) + "\n")
    run("m4-tamper-refusal", [cli, "verify-workspace", forged], expected_success=False)
    assert "WORKSPACE_COMPOSITION_BINDING" in (work / "m4-tamper-refusal.stderr.log").read_text()
    controls.append({"control": "m4-rehashed-lineage-substitution", "result": "refused", "code": "WORKSPACE_COMPOSITION_BINDING"})
    expected = json.loads((fixture / "acceptance/m4-expected.json").read_bytes())
    assert {v["control"] for v in controls if v["result"] == "source-intent-viable"} == set(expected["positive"])
    for label, code in expected["negative"].items():
        assert any(v["control"] == label and v["result"] == "refused" and v["code"] == code for v in controls)
    assert len(controls) == len(expected["positive"]) + len(expected["negative"]) + 2
    return {"controls": controls, "count": len(controls), "fullReleaseAccepted": False,
            "requiredReleaseLanes": {"linuxCompilation": "pending", "buildkit": "pending", "imageRuntime": "pending", "browser": "pending"}}
