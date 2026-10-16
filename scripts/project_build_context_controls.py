"""Native context build CLI controls, reusing the retained legacy build fixture."""
from pathlib import Path
import copy,hashlib,json,shutil,tempfile

def verify(root,work,env,run,fixture_work=None):
    cli=root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    base=work/"project-build-contexts";base.mkdir()
    fixture_work=fixture_work or work
    prior=json.loads((fixture_work/"project-builds/receipt.json").read_text())
    source=base/"owner";shutil.copytree(prior["retainedOriginalSource"],source)
    plan=json.loads((fixture_work/"project-builds/observe-plan.json").read_text())
    plan["buildSteps"][0]["invocation"]["arguments"][1]+="; /bin/cp dep-link bundle/dependency"
    def write(path,value):
        with path.open("x") as f:json.dump(value,f,indent=2);f.write("\n")
    plan_path=base/"plan.json";write(plan_path,plan)
    owner=base/"context-owner";(owner/"node_modules/pkg").mkdir(parents=True)
    payload=bytes([0,255,128,0,1]);(owner/"node_modules/pkg/tool.bin").write_bytes(payload)
    (owner/"node_modules/pkg/tool.bin").chmod(0o751)
    (owner/"dep-link").symlink_to("node_modules/pkg/tool.bin")
    (owner/"input.txt").write_text("old context\n")
    definition=dict(profile="patamaps-project-context-selection-1",id="urn:qualification:native-context-build",
        nonsecretInputs=True,paths=["node_modules/pkg/tool.bin","dep-link","input.txt"],symlinks="internal-closed")
    selection=base/"selection.json";write(selection,definition)
    snapshot=base/"snapshot"
    captured=json.loads(run("ctxbuild-capture",[cli,"project-context-capture",selection,"--root",owner,"--destination",snapshot]))
    binding=dict(profile="patamaps-project-build-context-1",snapshot=str(snapshot),digest=captured["digest"],
        overlays={"input.txt":"sha256:"+hashlib.sha256(b"old context\n").hexdigest()},writablePaths=["bundle"])
    binding_path=base/"binding.json";write(binding_path,binding)
    state=Path(tempfile.mkdtemp(prefix="patamaps-context-build-"))/"state"
    def build(label,plan_file=plan_path,context_file=binding_path,success=True,force=False):
        return json.loads(run(label,[cli,"project-build",plan_file,"--source",source,"--state",state,"--context",context_file,
            *(["--force"] if force else [])],expected_success=success))
    observed=json.loads(run("ctxbuild-key",[cli,"project-build-input-key",plan_path,"--source",source,"--context",binding_path]))
    assert observed["contextReference"]["bytesVerification"]=="not-performed"
    selected=build("ctxbuild-first");assert selected["status"]=="selected-project-build" and selected["inputKey"]==observed["inputKey"]
    pointer=(state/"selected.json").read_bytes();candidate=state/selected["attempt"]/"candidate"
    assert (candidate/"bundle/dependency").read_bytes()==payload
    assert (candidate/"node_modules/pkg/tool.bin").stat().st_mode&0o777==0o751
    assert (candidate/"dep-link").readlink()==Path("node_modules/pkg/tool.bin")
    assert (candidate/"input.txt").read_bytes()==(source/"input.txt").read_bytes()
    controls=[dict(control="native-binary-context-overlay-selection",result="passed")]
    noop=build("ctxbuild-noop")
    assert noop["status"]=="unchanged-project-build" and noop["verification"]=="not-repeated" and noop["cacheHits"]==0
    controls.append(dict(control="native-context-noop",result="passed",cacheHits=0))
    for label,suffix in [("dependency-mutation","; printf changed > node_modules/pkg/tool.bin"),("undeclared-write","; printf stray > stray-file"),("command-failure","; exit 9")]:
        value=copy.deepcopy(plan);value["buildSteps"][0]["invocation"]["arguments"][1]+=suffix
        path=base/(label+".json");write(path,value)
        result=build("ctxbuild-"+label,path,success=False,force=True)
        assert result["previousSelectionPreserved"] and (state/"selected.json").read_bytes()==pointer
        controls.append(dict(control=label,result="refused",previousSelectionPreserved=True))
    for label,value in [
        ("wrong-preimage",dict(binding,overlays={"input.txt":"sha256:"+"0"*64})),
        ("mutable-dependencies",dict(binding,writablePaths=["bundle","node_modules"]))]:
        path=base/(label+".json");write(path,value)
        result=build("ctxbuild-"+label,context_file=path,success=False,force=True)
        assert result["previousSelectionPreserved"] and (state/"selected.json").read_bytes()==pointer
        controls.append(dict(control=label,result="refused",previousSelectionPreserved=True))
    corrupt=base/"corrupt-snapshot";shutil.copytree(snapshot,corrupt)
    (corrupt/"data/node_modules/pkg/tool.bin").write_bytes(b"corrupt")
    path=base/"corrupt-binding.json";write(path,dict(binding,snapshot=str(corrupt)))
    result=build("ctxbuild-corrupt-snapshot",context_file=path,success=False,force=True)
    assert result["previousSelectionPreserved"] and (state/"selected.json").read_bytes()==pointer
    controls.append(dict(control="corrupt-snapshot-before-selection",result="refused"))
    # A fresh correct retained copy is supplied to the separate watch qualification.
    watch_snapshot=base/"watch-snapshot";shutil.copytree(snapshot,watch_snapshot)
    write(base/"watch-binding.json",dict(binding,snapshot=str(watch_snapshot)))
    source.rename(base/"owner.retained-offline");snapshot.rename(base/"snapshot.retained-offline")
    replay=json.loads(run("ctxbuild-offline",[ "/usr/bin/env","-i","PATH=",cli,"project-build-verify",state]))
    assert replay["status"]=="verified-selected-build-bindings"
    controls.append(dict(control="context-selection-offline-replay",result="passed",sourceAndSnapshotUnavailable=True))
    binary=candidate/"node_modules/pkg/tool.bin";binary.write_bytes(b"tamper")
    run("ctxbuild-selected-binary-tamper",[cli,"project-build-verify",state],expected_success=False)
    (base/"tampered-selected-binary.bin").write_bytes(binary.read_bytes());binary.write_bytes(payload)
    replay=json.loads(run("ctxbuild-restored-state",[cli,"project-build-verify",state]))
    assert replay["status"]=="verified-selected-build-bindings"
    controls.append(dict(control="selected-binary-tamper",result="refused"))
    receipt=dict(status="passed-native-context-build-controls",controls=controls,retainedState=str(state),
        snapshotDigest=captured["digest"],watchBinding=str(base/"watch-binding.json"),filesDeleted=0,
        actualApplicationQualification=False,generatedContractIntegration="not-qualified")
    write(base/"receipt.json",receipt)
    return receipt
