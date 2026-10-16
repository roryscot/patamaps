"""Independent retained Cargo/TOML process-provider controls for the M1 profile."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def verify(root, work, env, run):
    run("m1-format", ["cargo", "fmt", "--all", "--", "--check"])
    run("m1-unit-and-process-tests", ["cargo", "test", "-p", "patamaps-workspace", "--locked", "--offline"])
    run("m1-cli-build", ["cargo", "build", "-p", "patamaps-cli", "--locked", "--offline"])
    cli = root / "target/debug/patamaps"
    cargo = Path(run("m1-selected-cargo", ["rustup", "which", "cargo"]).decode().strip()).resolve()
    rustc = Path(run("m1-selected-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
    cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))).resolve()
    engine = json.loads(run("m1-executor-description", [cli, "engine"]))
    sys.path.insert(0, str(root / "scripts/parity"))
    from identity import identities
    assert engine == {"schemaVersion": "0.1.0", "documentType": "executor-description", **identities(root)}

    cases = work / "cases"
    cases.mkdir()
    base = cases / "base"
    base.mkdir()
    files = {
        "rust-toolchain.toml": '[toolchain]\nchannel="1.99.0"\nprofile="minimal"\n',
        "Cargo.toml": '[workspace]\nmembers=["app","helper","platform"]\nresolver="3"\n[workspace.package]\nversion="0.1.0"\nedition="2024"\n[workspace.dependencies]\nrenamed={package="support-lib",path="helper"}\n',
        "app/Cargo.toml": '[package]\nname="catalog-app"\nversion.workspace=true\nedition.workspace=true\nbuild="build.rs"\n[features]\ndefault=["enabled"]\nenabled=[]\n[dependencies]\nrenamed.workspace=true\n[target.\'cfg(unix)\'.dependencies]\nplatform-lib={path="../platform"}\n[[bin]]\nname="catalog-service"\npath="src/main.rs"\nrequired-features=["enabled"]\n[[bin]]\nname="maintenance"\npath="src/maintenance.rs"\n',
        "app/src/main.rs": "fn main() {}\n",
        "app/src/maintenance.rs": "fn main() {}\n",
        "app/src/lib.rs": "pub fn handler() {}\n",
        "app/build.rs": 'fn main() { std::fs::write("BUILD_SCRIPT_WAS_EXECUTED", b"unexpected").unwrap(); }\n',
        "helper/Cargo.toml": '[package]\nname="support-lib"\nversion.workspace=true\nedition.workspace=true\n',
        "helper/src/lib.rs": "pub fn helper() {}\n",
        "platform/Cargo.toml": '[package]\nname="platform-lib"\nversion.workspace=true\nedition.workspace=true\n',
        "platform/src/lib.rs": "pub fn platform() {}\n",
    }
    for name, content in files.items():
        p = base / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    run("m1-fixture-lock", [cargo, "generate-lockfile", "--offline", "--manifest-path", base / "Cargo.toml"])

    def configuration(**changes):
        result = {"provider": "cargo", "nonsecretInputs": True, "manifest": "Cargo.toml",
                  "workspaceManifest": "Cargo.toml", "lockfile": "Cargo.lock",
                  "cargo": str(cargo), "cargoDigest": sha(cargo),
                  "rustc": str(rustc), "rustcDigest": sha(rustc), "cargoHome": str(cargo_home),
                  "platform": "x86_64-unknown-linux-gnu", "features": [],
                  "defaultFeatures": True, "view": "resolved"}
        result.update(changes)
        return result

    def inputs(owner, omitted=()):
        names = sorted([p.relative_to(owner).as_posix() for p in owner.rglob("*")
                        if p.is_file() and p.name in {"Cargo.toml", "Cargo.lock", "config.toml", "rust-toolchain.toml", "rust-toolchain"}
                        and "target" not in p.parts and p.relative_to(owner).as_posix() not in omitted])
        return [{"receipt": {"path": p, "digest": sha(owner / p), "byteLength": len((owner / p).read_bytes())},
                 "content": (owner / p).read_text()} for p in names]

    observed = []
    def provider(label, owner, config=None, omitted=(), refuse=None, mutate_live=None):
        request = {"schemaVersion": "0.1.0", "documentType": "adapter-request",
                   "profile": "patamaps-workspace-draft-1", "sourceId": "urn:test:cargo",
                   "namespace": "cross-stack-m1", "config": config or configuration(),
                   "inputs": inputs(owner, omitted), "invocationDigest": "sha256:" + "0" * 64,
                   "requestDigest": ""}
        request["requestDigest"] = json.loads(run(label + "-request", [cli, "json", "digest"],
                                               input_bytes=json.dumps(request).encode()))
        if mutate_live:
            mutate_live()
        before = {v["receipt"]["path"]: sha(owner / v["receipt"]["path"]) for v in request["inputs"]}
        output = run(label, [cli, "discover-native"], cwd=owner,
                     input_bytes=json.dumps(request).encode(), expected_success=refuse is None)
        assert all(sha(owner / p) == digest for p, digest in before.items()), label
        assert not list(owner.rglob("BUILD_SCRIPT_WAS_EXECUTED")), "Discovery executed a project build script"
        if refuse:
            text = (work / (label + ".stderr.log")).read_text() + output.decode()
            assert refuse in text, (label, text)
            observed.append({"control": label, "result": "refused", "code": refuse,
                             "manifestsAndLocksUnchanged": True, "projectBuildScriptExecuted": False})
            return None
        value = json.loads(output)
        assert value["requestDigest"] == request["requestDigest"]
        assert value["inputs"] == [v["receipt"] for v in request["inputs"]]
        evidence = value["shard"]["metadata"]["observation"]
        assert evidence["compilationEstablished"] is False and evidence["buildScriptsExecuted"] is False
        assert evidence["metadataDigest"] == "sha256:" + hashlib.sha256(evidence["metadataBytes"].encode()).hexdigest()
        raw = json.loads(evidence["metadataBytes"])
        assert raw["version"] == 1 and raw["workspace_root"] == str(owner.resolve())
        observed.append({"control": label, "result": "observed", "view": evidence["view"],
                         "manifestsAndLocksUnchanged": True, "projectBuildScriptExecuted": False,
                         "requestDigest": request["requestDigest"], "shardDigest": json.loads(
                             run(label + "-shard-digest", [cli, "json", "digest"], input_bytes=json.dumps(value["shard"]).encode()))})
        return value

    positive = provider("m1-resolved-workspace", base)
    entities = positive["shard"]["entities"]
    packages = [v for v in entities if v["kind"] == "cargo-package"]
    assert sorted(v["attributes"]["name"] for v in packages) == ["catalog-app", "platform-lib", "support-lib"]
    app = next(v["attributes"] for v in packages if v["attributes"]["name"] == "catalog-app")
    assert app["version"] == "0.1.0" and "enabled" in app["featuresResolved"]
    assert any(v["name"] == "support-lib" and v["rename"] == "renamed" and v["path"] == "helper" for v in app["dependenciesDeclared"])
    assert any(v["name"] == "platform-lib" and v["target"] == "cfg(unix)" for v in app["dependenciesDeclared"])
    targets = [v["attributes"] for v in entities if v["kind"] == "cargo-target"]
    assert any(v["name"] == "catalog-service" and v["requiredFeatures"] == ["enabled"] for v in targets)
    assert any(v["name"] == "maintenance" for v in targets)
    assert any(v["possibleExecutableInput"] and "custom-build" in v["kind"] for v in targets)

    declared = provider("m1-declared-view", base, configuration(view="declared-local"))
    assert declared["shard"]["metadata"]["observation"]["view"] == "declared-local"
    assert all(v["attributes"]["featuresResolved"] is None for v in declared["shard"]["entities"] if v["kind"] == "cargo-package")
    disabled = provider("m1-feature-disabled", base, configuration(defaultFeatures=False))
    app = next(v["attributes"] for v in disabled["shard"]["entities"] if v["kind"] == "cargo-package" and v["attributes"]["name"] == "catalog-app")
    assert "enabled" not in app["featuresResolved"]
    assert any(v["attributes"]["name"] == "catalog-service" and v["attributes"]["requiredFeatures"] == ["enabled"] for v in disabled["shard"]["entities"] if v["kind"] == "cargo-target")

    relocated = cases / "relocated"
    shutil.copytree(base, relocated)
    moved = provider("m1-root-relocated", relocated)
    assert positive["shard"]["entities"] == moved["shard"]["entities"], "Root relocation changed physical identities or normalized facts"
    assert positive["shard"]["metadata"]["observation"]["metadataDigest"] != moved["shard"]["metadata"]["observation"]["metadataDigest"]

    # G3 uses actual Cargo metadata; expansion is owner opt-in and fully captured.
    globbed = cases / "bounded-members"
    globbed.mkdir()
    for name in ["app","helper","platform"]:
        shutil.copytree(base/name,globbed/"crates"/name)
    for name in ["Cargo.lock","rust-toolchain.toml"]:shutil.copy2(base/name,globbed/name)
    (globbed/"Cargo.toml").write_text((base/"Cargo.toml").read_text().replace('members=["app","helper","platform"]','members=["crates/*"]').replace('path="helper"','path="crates/helper"'))
    provider("g3-globs-default-refused",globbed,refuse="NATIVE_CARGO_MEMBERS")
    glob_config=configuration(workspaceMembers="bounded-directory-globs")
    expanded=provider("g3-globs-explicit",globbed,glob_config)
    expansion=expanded["shard"]["metadata"]["observation"]["workspaceMembers"]
    assert expansion=={"mode":"bounded-directory-globs","preAndPostObservedEqual":True,"expansions":[{"manifest":"Cargo.toml","pattern":"crates/*","manifests":["crates/app/Cargo.toml","crates/helper/Cargo.toml","crates/platform/Cargo.toml"]}]}
    provider("g3-globs-missing-capture",globbed,glob_config,omitted=("crates/helper/Cargo.toml",),refuse="NATIVE_CARGO_MANIFEST_INPUT")
    for label,pattern,extra in [("recursive","crates/**",""),("question","crates/?",""),("escape","../*",""),("exclusions","crates/*",'exclude=["crates/helper"]\n')]:
        case=cases/("glob-"+label);shutil.copytree(globbed,case)
        text=(case/"Cargo.toml").read_text().replace('members=["crates/*"]',f'members=["{pattern}"]\n'+extra)
        (case/"Cargo.toml").write_text(text)
        provider("g3-globs-"+label,case,glob_config,refuse="NATIVE_CARGO_MEMBERS")
    linked=cases/"glob-symlink";shutil.copytree(globbed,linked)
    (linked/"crates/alias").symlink_to((base/"helper").resolve(),target_is_directory=True)
    provider("g3-globs-symlink",linked,glob_config,refuse="NATIVE_CARGO_MEMBERS")
    racing=cases/"glob-racing";shutil.copytree(globbed,racing)
    wrapper=work/"member-mutating-cargo"
    wrapper.write_text("#!"+sys.executable+"\nimport pathlib,subprocess,sys\n"+
        "result=subprocess.run(["+repr(str(cargo))+",*sys.argv[1:]])\n"+
        "if sys.argv[1:2]==['metadata']:pathlib.Path("+repr(str(racing/"crates/added-after-metadata"))+").mkdir()\n"+
        "sys.exit(result.returncode)\n")
    wrapper.chmod(0o700)
    provider("g3-globs-post-metadata-change",racing,configuration(workspaceMembers="bounded-directory-globs",cargo=str(wrapper.resolve()),cargoDigest=sha(wrapper)),refuse="NATIVE_CARGO_MEMBERS_CHANGED")

    malformed = cases / "malformed"
    shutil.copytree(base, malformed)
    (malformed / "app/Cargo.toml").write_text((malformed / "app/Cargo.toml").read_text() + "\nbroken = [")
    provider("m1-malformed-toml", malformed, refuse="NATIVE_TOML_SYNTAX")

    duplicate = cases / "duplicate"
    shutil.copytree(base, duplicate)
    (duplicate / "app/Cargo.toml").write_text((duplicate / "app/Cargo.toml").read_text() + '\n[package]\nname="duplicate"\n')
    provider("m1-duplicate-toml", duplicate, refuse="NATIVE_TOML_SYNTAX")
    provider("m1-unrecorded-member", base, omitted=("helper/Cargo.toml",), refuse="NATIVE_CARGO_MANIFEST_INPUT")

    missing = cases / "missing-lock"
    shutil.copytree(base, missing, ignore=lambda d, ns: {"Cargo.lock"} if "Cargo.lock" in ns else set())
    provider("m1-missing-lock", missing, refuse="NATIVE_CARGO_INPUT")

    offline = cases / "offline-dependency"
    shutil.copytree(root / "examples/cross-stack/service", offline,
                    ignore=lambda d, ns: {n for n in ns if n == "target"})
    (offline / "rust-toolchain.toml").write_text('[toolchain]\nchannel="1.99.0"\n')
    empty_home = work / "empty-cargo-home"
    empty_home.mkdir()
    provider("m1-offline-unavailable", offline, configuration(cargoHome=str(empty_home.resolve())), refuse="NATIVE_CARGO_UNAVAILABLE")
    assert not list(empty_home.rglob("*.crate")), "Offline discovery downloaded a dependency"

    real_service = cases / "real-service"
    shutil.copytree(root / "examples/cross-stack/service", real_service,
                    ignore=lambda d, ns: {n for n in ns if n == "target"})
    actual = provider("m1-real-service", real_service)
    assert any(v["kind"]=="cargo-target" and v["attributes"]["name"]=="catalog-service" for v in actual["shard"]["entities"])
    assert any(v["packageName"]=="serde_derive" and "proc-macro" in v["cargoTargetKind"]
               and not v["sourceContentsCaptured"] and not v["executionObserved"]
               for v in actual["shard"]["metadata"]["observation"]["possibleExecutableInputs"])
    oversized_tool = work / "oversized-tool"
    with oversized_tool.open("xb") as out:
        out.seek(256*1024*1024)
        out.write(b"\\0")
    provider("m1-oversized-tool", base, configuration(cargo=str(oversized_tool.resolve())), refuse="NATIVE_CARGO_TOOL_REFUSED")

    outside = cases / "outside"
    (outside / "src").mkdir(parents=True)
    (outside / "Cargo.toml").write_text('[package]\nname="outside"\nversion="0.1.0"\nedition="2024"\n')
    (outside / "src/lib.rs").write_text("pub fn outside() {}\n")
    escaped = cases / "escaped"
    shutil.copytree(base, escaped)
    with (escaped / "app/Cargo.toml").open("a") as f:
        f.write('\n[build-dependencies]\noutside={path="' + str(outside.resolve()) + '"}\n')
    provider("m1-out-of-scope-path", escaped, refuse="NATIVE_CARGO_PATH_ESCAPE")

    config = cases / "config"
    shutil.copytree(base, config)
    (config / ".cargo").mkdir()
    (config / ".cargo/config.toml").write_text('[build]\ntarget="x86_64-unknown-linux-gnu"\n[net]\noffline=true\n')
    configured = provider("m1-explicit-config", config)
    assert ".cargo/config.toml" in configured["shard"]["metadata"]["observation"]["configurationInputs"]
    provider("m1-unrecorded-config", config, omitted=(".cargo/config.toml",), refuse="NATIVE_CARGO_CONFIG_INPUT")
    mismatched = cases / "mismatched-toolchain"
    shutil.copytree(base, mismatched)
    (mismatched / "rust-toolchain.toml").write_text('[toolchain]\nchannel="1.98.0"\n')
    provider("m1-mismatched-toolchain", mismatched, refuse="NATIVE_CARGO_TOOLCHAIN")
    provider("m1-unrecorded-toolchain", base, omitted=("rust-toolchain.toml",), refuse="NATIVE_CARGO_CONFIG_INPUT")

    unsafe = cases / "unsafe-config"
    shutil.copytree(config, unsafe)
    (unsafe / ".cargo/config.toml").write_text('[build]\nrustc="unreviewed-wrapper"\n')
    provider("m1-executable-override", unsafe, refuse="NATIVE_CARGO_CONFIG")

    ambient = work / "ambient-parent"
    (ambient / ".cargo").mkdir(parents=True)
    (ambient / ".cargo/config.toml").write_text('[net]\noffline=true\n')
    ambient_owner = ambient / "owner"
    shutil.copytree(base, ambient_owner)
    provider("m1-ambient-config", ambient_owner, refuse="NATIVE_CARGO_AMBIENT_CONFIG")

    provider("m1-tool-substitution", base, configuration(cargoDigest="sha256:" + "0" * 64), refuse="NATIVE_CARGO_TOOL_CHANGED")
    stale = cases / "stale-source"
    shutil.copytree(base, stale)
    provider("m1-stale-source", stale, refuse="NATIVE_SOURCE_CHANGED",
             mutate_live=lambda: (stale / "app/Cargo.toml").write_text((stale / "app/Cargo.toml").read_text() + "\n# concurrent edit\n"))
    # Exercise the real generic workspace bridge, not only a direct provider call.
    owner = cases / "workspace-bridge"
    shutil.copytree(globbed, owner)
    provider_binary = work / "captured-native-provider"
    shutil.copy2(cli, provider_binary)
    cargo_alias = work / "captured-cargo"
    rustc_alias = work / "captured-rustc"
    cargo_alias.symlink_to(cargo)
    rustc_alias.symlink_to(rustc)
    bridge_config = configuration(cargo=str(cargo_alias.resolve(strict=False)),
                                  rustc=str(rustc_alias.resolve(strict=False)))
    # Keep lexical configured paths as well as the resolved byte identities.
    bridge_config["workspaceMembers"] = "bounded-directory-globs"
    bridge_config["cargo"] = str(cargo_alias.absolute())
    bridge_config["rustc"] = str(rustc_alias.absolute())
    cargo_inputs = [v["receipt"]["path"] for v in inputs(owner)]
    for source, target in [("fixtures/routing/graph.json", "routing.json"),
                           ("relation-packs/routing.json", "routing-pack.json"),
                           ("fixtures/routing/projection-spec.json", "projection.json")]:
        shutil.copyfile(root / source, owner / target)
    policy = json.loads((root / "fixtures/routing/policy.json").read_bytes())
    workspace_id = "urn:patamaps:cross-stack:m1:workspace"
    policy["graph"] = {"id": workspace_id, "revision": "1"}
    (owner / "policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    config = {"schemaVersion": "0.1.0", "documentType": "workspace-config",
              "id": workspace_id, "namespace": "cross-stack-m1", "revision": "1",
              "sources": [{"adapter": "process", "id": "urn:test:cargo",
                           "invocation": {"executable": str(provider_binary.resolve()),
                                          "arguments": ["discover-native"], "codeInputs": [],
                                          "bounds": {"maximumElapsedMs": 60000, "maximumStdoutBytes": 16777216,
                                                     "maximumStderrBytes": 65536}},
                           "inputs": cargo_inputs, "config": bridge_config},
                          {"adapter": "portable-shard", "id": "urn:test:routing", "path": "routing.json"}],
              "packs": ["routing-pack.json"], "policy": "policy.json",
              "projections": [{"path": "projection.json", "emissions": [{"path": "generated/routing.json", "language": "json"}]}],
              "context": {"environment": "production"}, "evaluatedAt": "2026-10-15T00:00:00Z"}
    (owner / "workspace.json").write_text(json.dumps(config, indent=2) + "\n")
    generated = json.loads(run("m1-workspace-native-bridge", [cli, "generate", "workspace.json", "--root", owner], cwd=owner))
    assert generated["cacheHits"] == 0, "Process observations must not manufacture cache verification"
    baseline = generated["baseline"]
    assert all(v["result"]["status"] == "viable" for v in baseline["captures"])
    saved = work / "native-workspace-baseline.json"
    saved.write_text(json.dumps(baseline, indent=2) + "\n")
    run("m1-workspace-offline-before", [cli, "verify-workspace", saved])

    moves = []
    for p in [provider_binary, cargo_alias, rustc_alias, owner / "Cargo.toml"]:
        destination = p.with_name(p.name + ".retained")
        p.rename(destination)
        moves.append({"configuredPathNowUnavailable": str(p), "preservedAt": str(destination)})
    assert all(not Path(v["configuredPathNowUnavailable"]).exists() for v in moves)
    previous_environment = dict(env)
    try:
        env.clear()
        env["PATH"] = "/patamaps-no-external-programs"
        env["HOME"] = str(work / "no-user-home")
        offline_result = json.loads(run("m1-workspace-offline-without-inputs-tools-node",
                                        [cli, "verify-workspace", saved], cwd=work))
    finally:
        env.clear()
        env.update(previous_environment)
    assert offline_result == {"active": "not-evaluated", "authentication": "not-evaluated",
                              "authorizationNow": "not-evaluated", "baseline": baseline["digest"],
                              "sourceRediscovery": "not-performed", "status": "verified-record-bindings"}, offline_result
    observed.append({"control": "m1-native-workspace-offline-reconstruction", "result": "verified",
                     "providerAndConfiguredCargoRustcAndManifestUnavailable": True,
                     "boundedMemberExpansionReplayed": True,
                     "externalProgramsAbsentFromPath": True, "retainedMoves": moves})

    tampered = json.loads(saved.read_bytes())
    tampered["discovery"][0]["adapterVersion"] = "counterfeit-observation-version"
    tampered.pop("digest")
    tampered["digest"] = json.loads(run("m1-rehash-tampered-baseline", [cli, "json", "digest"],
                                         input_bytes=json.dumps(tampered).encode()))
    forged = work / "tampered-rehashed-baseline.json"
    forged.write_text(json.dumps(tampered, indent=2) + "\n")
    run("m1-offline-rehashed-lineage-refusal", [cli, "verify-workspace", forged], expected_success=False)
    assert "WORKSPACE_COMPOSITION_BINDING" in (work / "m1-offline-rehashed-lineage-refusal.stderr.log").read_text()
    observed.append({"control": "m1-rehashed-native-workspace-lineage", "result": "refused",
                     "code": "WORKSPACE_COMPOSITION_BINDING"})

    # Native G4 source-free staging uses the same verified input record contract.
    stage_profile={"profile":"patamaps-project-inputs-1","id":"urn:qualification:retained-stage","nonsecretInputs":True,
        "inputs":["Cargo.toml","app/src/main.rs"],"components":[{"id":"service","kind":"cargo-package","root":".","entrypoints":["Cargo.toml","app/src/main.rs"]}],
        "secretReferences":{"database":"PATAMAPS_STAGE_UNRESOLVED_DATABASE"}}
    profile_path=work/"stage-profile.json";profile_path.write_text(json.dumps(stage_profile)+"\n")
    capture_path=work/"stage-capture.json"
    run("g4-stage-capture",[cli,"project-capture",profile_path,"--root",base,"--output",capture_path])
    captured=json.loads(capture_path.read_bytes())
    retained_source=cases/"base-staging-retained";base.rename(retained_source)
    assert not base.exists()
    staged=work/"staged-selected-inputs"
    previous_environment=dict(env)
    try:
        env.clear();env.update(PATH="/patamaps-no-external-programs",HOME=str(work/"stage-no-user-home"))
        stage_result=json.loads(run("g4-project-stage",[cli,"project-stage",capture_path,"--destination",staged],cwd=work))
        assert stage_result["status"]=="staged-project-inputs" and stage_result["digest"]==captured["digest"]
        expected={v["receipt"]["path"]:v["receipt"]["digest"] for v in captured["inputs"]}
        assert expected=={n:sha(staged/n) for n in expected}
        run("g4-stage-existing-destination",[cli,"project-stage",capture_path,"--destination",staged],cwd=work,expected_success=False)
        assert "PROJECT_STAGE_DESTINATION_UNAVAILABLE" in (work/"g4-stage-existing-destination.stderr.log").read_text()
        assert expected=={n:sha(staged/n) for n in expected}
        bad=json.loads(capture_path.read_bytes());bad["inputs"][0]["content"]+="tampered"
        bad_path=work/"stage-tampered.json";bad_path.write_text(json.dumps(bad)+"\n")
        refused_path=work/"stage-refused-candidate"
        run("g4-stage-tampered-capture",[cli,"project-stage",bad_path,"--destination",refused_path],cwd=work,expected_success=False)
        assert "PROJECT_RECORD_INPUT" in (work/"g4-stage-tampered-capture.stderr.log").read_text()
        assert not refused_path.exists()
    finally:env.clear();env.update(previous_environment)
    observed.extend([
        {"control":"g4-retained-input-stage","result":"staged","captureDigest":captured["digest"],"originalSelectedSourceRootUnavailable":True,"sourcePreservedAt":str(retained_source),"externalProgramsAbsentFromPath":True,"inputCount":len(expected),"selectedInputDigests":expected,"compilationEstablished":False},
        {"control":"g4-stage-no-overwrite","result":"refused","code":"PROJECT_STAGE_DESTINATION_UNAVAILABLE","selectedBytesUnchanged":True},
        {"control":"g4-stage-tamper-before-creation","result":"refused","code":"PROJECT_RECORD_INPUT","destinationCreated":False}])

    return {"status": "passed", "controls": observed, "engines": engine, "nativeBinaryDigest": sha(cli), "newNativeTomlUnitTests": 10, "memberExpansionUnitTests": 2,
            "existingBoundedProcessTests": 2, "cargo": {"path": str(cargo), "digest": sha(cargo)},
            "rustc": {"path": str(rustc), "digest": sha(rustc)}, "compiledFixtureEstablishedByTheseObservations": False,
            "limits": {"workspaceMembers": "literal default; opt-in one-star directory glob, exact captured expansion, exclusions refuse",
                       "ambientConfig": "outside owner root refuses without copying values",
                       "cargoConfig": "only matching build.target and net.offline=true",
                       "artifactAndRuntimeAcceptance": "not established"}}
