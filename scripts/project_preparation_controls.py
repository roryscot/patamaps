"""Owner preparation integration controls; controlled inputs, not application acceptance."""
from pathlib import Path
import copy, hashlib, json, shutil, tempfile


def verify(root, work, env, run, fixture_work):
    cli = root / ("target/" + env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE", "debug") + "/patamaps")
    base = work / "project-preparation"
    base.mkdir()
    prior = json.loads((fixture_work / "project-builds/receipt.json").read_text())
    source = base / "owner"
    shutil.copytree(prior["retainedOriginalSource"], source)
    plan = json.loads((fixture_work / "project-builds/observe-plan.json").read_text())

    def write(path, value):
        with path.open("x") as f:
            json.dump(value, f, indent=2)
            f.write("\n")

    def command(body):
        value = copy.deepcopy(plan["buildSteps"][0])
        value["invocation"]["arguments"] = ["-c", body]
        return value

    plan["buildSteps"] = [command("/bin/mkdir -p bundle; /bin/cp contract.txt bundle/app")]
    plan["verificationSteps"] = [command("/usr/bin/cmp input.txt bundle/app")]
    plan_path = base / "plan.json"
    write(plan_path, plan)
    owner = base / "context-owner"
    (owner / "node_modules/pkg").mkdir(parents=True)
    (owner / "node_modules/pkg/tool.bin").write_bytes(bytes([0, 255, 128]))
    old_contract = b"captured old contract\n"
    (owner / "contract.txt").write_bytes(old_contract)
    selection = base / "selection.json"
    write(selection, dict(profile="patamaps-project-context-selection-1",
                          id="urn:qualification:preparation-context", nonsecretInputs=True,
                          paths=["contract.txt", "node_modules/pkg/tool.bin"]))
    snapshot = base / "snapshot"
    captured = json.loads(run("prep-context-capture", [cli, "project-context-capture", selection,
                         "--root", owner, "--destination", snapshot]))
    context = dict(profile="patamaps-project-build-context-1", snapshot=str(snapshot),
                   digest=captured["digest"], overlays={}, writablePaths=["bundle"])
    context_path = base / "context.json"
    write(context_path, context)
    preparation = dict(profile="patamaps-project-preparation-1",
                       commands=[command("/bin/cp input.txt contract.txt")],
                       outputs={"contract.txt": "sha256:" + hashlib.sha256(old_contract).hexdigest()})
    preparation_path = base / "preparation.json"
    write(preparation_path, preparation)
    state = Path(tempfile.mkdtemp(prefix="patamaps-preparation-")) / "state"
    controls = []

    def build(label, prep=preparation_path, plan_file=plan_path, success=True, force=False):
        argv = [cli, "project-build", plan_file, "--source", source, "--state", state,
                "--context", context_path, "--preparation", prep]
        if force:
            argv.append("--force")
        return json.loads(run("prep-" + label, argv, expected_success=success))

    def key(label, prep=preparation_path):
        return json.loads(run("prep-key-" + label, [cli, "project-build-input-key", plan_path,
                          "--source", source, "--context", context_path, "--preparation", prep]))

    observed = key("initial")
    assert not state.exists()
    first = build("first")
    assert first["status"] == "selected-project-build" and first["inputKey"] == observed["inputKey"]
    pointer = (state / "selected.json").read_bytes()
    candidate = state / first["attempt"] / "candidate"
    assert (candidate / "contract.txt").read_bytes() == (source / "input.txt").read_bytes()
    assert (candidate / "bundle/app").read_bytes() == (source / "input.txt").read_bytes()
    attempt = state / first["attempt"]
    frozen = json.loads((attempt / "candidate-capture.json").read_text())
    assert "contract.txt" in frozen["definition"]["inputs"]
    assert "contract.txt" not in plan["project"]["inputs"]
    controls.append(dict(control="prepare-consumed-contract-before-frozen-capture", result="passed"))
    noop = build("noop")
    assert noop["status"] == "unchanged-project-build" and noop["verification"] == "not-repeated"
    assert (state / "selected.json").read_bytes() == pointer
    controls.append(dict(control="preparation-noop", result="passed", verification="not-repeated"))
    (source / "input.txt").write_text("edited owner contract\n")
    observed_edit = key("owner-edit")
    assert observed_edit["inputKey"] != observed["inputKey"]
    edited = build("owner-edit")
    assert edited["status"] == "selected-project-build" and edited["inputKey"] == observed_edit["inputKey"]
    assert (state / edited["attempt"] / "candidate/bundle/app").read_bytes() == (source / "input.txt").read_bytes()
    pointer = (state / "selected.json").read_bytes()
    controls.append(dict(control="owner-edit-regenerates-consumed-contract", result="passed"))
    for label, body in [
        ("failure", "printf failed >&2; exit 9"),
        ("undeclared-write", "/bin/cp input.txt contract.txt; printf stray > stray-file"),
        ("build-write-root-not-permitted", "/bin/cp input.txt contract.txt; /bin/mkdir -p bundle; printf stray > bundle/prep-only"),
        ("dependency-mutation", "/bin/cp input.txt contract.txt; printf changed > node_modules/pkg/tool.bin"),
        ("selected-source-mutation", "/bin/cp input.txt contract.txt; printf changed > input.txt"),
        ("missing-output", "/bin/mv contract.txt contract.retained-missing"),
        ("symlink-output", "/bin/mv contract.txt contract.retained-symlink; /bin/ln -s input.txt contract.txt"),
    ]:
        value = copy.deepcopy(preparation)
        value["commands"] = [command(body)]
        path = base / (label + ".json")
        write(path, value)
        assert key(label, path)["inputKey"] != observed_edit["inputKey"]
        result = build(label, path, success=False, force=True)
        assert result["previousSelectionPreserved"] and (state / "selected.json").read_bytes() == pointer
        assert not (state / result["attempt"] / "build-000.started.json").exists()
        controls.append(dict(control=label, result="refused", previousSelectionPreserved=True,
                             buildCommandStarted=False))
    stale = copy.deepcopy(preparation)
    stale["outputs"]["contract.txt"] = "sha256:" + "0" * 64
    path = base / "stale-preimage.json"
    write(path, stale)
    result = build("stale-preimage", path, success=False, force=True)
    assert result["previousSelectionPreserved"] and (state / "selected.json").read_bytes() == pointer
    assert not (state / result["attempt"] / "prepare-000.started.json").exists()
    controls.append(dict(control="stale-preimage-before-command", result="refused", preparationStarted=False))
    absent_wrong = copy.deepcopy(preparation)
    absent_wrong["outputs"]["contract.txt"] = None
    path = base / "wrong-absent-preimage.json"
    write(path, absent_wrong)
    result = build("wrong-absent-preimage", path, success=False, force=True)
    assert result["previousSelectionPreserved"] and (state / "selected.json").read_bytes() == pointer
    assert not (state / result["attempt"] / "prepare-000.started.json").exists()
    controls.append(dict(control="absent-preimage-refuses-existing-file", result="refused"))
    for label, outputs in [
        ("selected-input-collision", {"input.txt": None}),
        ("secret-output-path", {".env.local": None}),
        ("credential-output-path", {".npmrc": None}),
        ("mutable-output-path", {"bundle/contract.txt": None}),
        ("output-prefix-collision", {"new": None, "new/file.txt": None}),
    ]:
        value = copy.deepcopy(preparation)
        value["outputs"] = outputs
        path = base / (label + ".json")
        write(path, value)
        run("prep-" + label, [cli, "project-build-input-key", plan_path, "--source", source,
                             "--context", context_path, "--preparation", path], expected_success=False)
        assert (state / "selected.json").read_bytes() == pointer
        controls.append(dict(control=label, result="refused-before-execution"))
    run("prep-requires-context", [cli, "project-build", plan_path, "--source", source,
         "--state", state, "--preparation", preparation_path], expected_success=False)
    assert (state / "selected.json").read_bytes() == pointer
    controls.append(dict(control="preparation-requires-sealed-context", result="refused-before-execution"))
    # Existing outputs may also remain byte-identical to their captured preimage.
    same = copy.deepcopy(preparation)
    same["commands"] = [command(":")]
    same_path = base / "unchanged-output.json"
    write(same_path, same)
    same_plan = copy.deepcopy(plan)
    same_plan["verificationSteps"] = [command("test -s bundle/app")]
    same_plan_path = base / "unchanged-output-plan.json"
    write(same_plan_path, same_plan)
    result = build("unchanged-preimage-output", same_path, same_plan_path)
    assert result["status"] == "selected-project-build"
    pointer = (state / "selected.json").read_bytes()
    controls.append(dict(control="unchanged-generated-preimage", result="passed"))
    # A newly generated selected text file uses the existing staged-input mode 0600.
    fresh = copy.deepcopy(preparation)
    fresh["outputs"]["new-contract.txt"] = None
    fresh["commands"] = [command("umask 077; /bin/cp input.txt contract.txt; printf fresh > new-contract.txt")]
    fresh_path = base / "fresh-output.json"
    write(fresh_path, fresh)
    result = build("new-output", fresh_path)
    assert result["status"] == "selected-project-build"
    pointer = (state / "selected.json").read_bytes()
    attempt = state / result["attempt"]
    candidate = attempt / "candidate"
    assert (candidate / "new-contract.txt").read_text() == "fresh"
    controls.append(dict(control="absent-preimage-new-output", result="passed"))
    # Verification cannot mutate generated selected inputs.
    altered = copy.deepcopy(plan)
    altered["verificationSteps"] = [command("printf changed > contract.txt")]
    altered_path = base / "verify-mutates-generated.json"
    write(altered_path, altered)
    result = build("verification-mutates-generated", fresh_path, altered_path, success=False, force=True)
    assert result["previousSelectionPreserved"] and (state / "selected.json").read_bytes() == pointer
    controls.append(dict(control="verification-mutates-generated", result="refused", previousSelectionPreserved=True))
    offline_source, offline_snapshot = base / "owner.retained-offline", base / "snapshot.retained-offline"
    source.rename(offline_source)
    snapshot.rename(offline_snapshot)
    try:
        replay = json.loads(run("prep-offline-replay", ["/usr/bin/env", "-i", "PATH=", cli,
                                "project-build-verify", state]))
        assert replay["status"] == "verified-selected-build-bindings"
    finally:
        offline_source.rename(source)
        offline_snapshot.rename(snapshot)
    controls.append(dict(control="offline-preparation-replay", result="passed", sourceAndSnapshotUnavailable=True))
    original = (candidate / "contract.txt").read_bytes()
    with (base / "original-selected-generated.bytes").open("xb") as f:
        f.write(original)
    (candidate / "contract.txt").write_bytes(b"corrupt generated contract")
    run("prep-generated-tamper", [cli, "project-build-verify", state], expected_success=False)
    (base / "tampered-generated.bytes").write_bytes((candidate / "contract.txt").read_bytes())
    (candidate / "contract.txt").write_bytes(original)
    run("prep-restored-generated", [cli, "project-build-verify", state])
    controls.append(dict(control="generated-selected-byte-tamper", result="refused"))
    record = attempt / "prepare-000.json"
    original_record = record.read_bytes()
    with (base / "original-prepare-report.json").open("xb") as f:
        f.write(original_record)
    data = json.loads(original_record)
    data["captureDigest"] = "sha256:" + "0" * 64
    record.write_text(json.dumps(data))
    run("prep-report-tamper", [cli, "project-build-verify", state], expected_success=False)
    (base / "tampered-prepare-report.json").write_bytes(record.read_bytes())
    record.write_bytes(original_record)
    run("prep-restored-report", [cli, "project-build-verify", state])
    controls.append(dict(control="preparation-command-record-tamper", result="refused"))
    receipt = dict(status="passed-native-preparation-controls", controls=controls,
                   retainedState=str(state), preparation=str(fresh_path), plan=str(plan_path),
                   context=str(context_path), source=str(source), filesDeleted=0,
                   actualApplicationAcceptance=False)
    write(base / "receipt.json", receipt)
    return receipt
