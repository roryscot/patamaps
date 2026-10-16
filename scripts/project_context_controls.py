"""Native retained context CLI controls; generated fixtures and failures retained."""
from pathlib import Path
import copy,hashlib,json,os,shutil

def verify(root,work,env,run):
    cli=root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    base=work/"project-contexts";base.mkdir()
    source=base/"owner";(source/"tools").mkdir(parents=True)
    payload=bytes([0,255,128,1,0]);(source/"tools/program").write_bytes(payload)
    os.chmod(source/"tools/program",0o751)
    (source/"empty").mkdir();(source/"alias").symlink_to("tools/program")
    def write(path,value):
        with path.open("x") as f:json.dump(value,f,indent=2);f.write("\n")
    definition=dict(profile="patamaps-project-context-selection-1",id="urn:qualification:binary-context",nonsecretInputs=True,
                    paths=["tools/program","empty","alias"],symlinks="internal-closed")
    write(base/"selection.json",definition)
    snapshot=base/"snapshot"
    captured=json.loads(run("context-capture",[cli,"project-context-capture",base/"selection.json","--root",source,"--destination",snapshot]))
    assert captured["status"]=="captured-project-context"
    source.rename(base/"owner.retained-offline")
    verified=json.loads(run("context-verify-offline",["/usr/bin/env","-i","PATH=",cli,"project-context-verify",snapshot]))
    assert verified["digest"]==captured["digest"]
    staged=base/"staged"
    report=json.loads(run("context-stage",[cli,"project-context-stage",snapshot,"--destination",staged]))
    assert report["digest"]==captured["digest"] and (staged/"tools/program").read_bytes()==payload
    assert (staged/"tools/program").stat().st_mode&0o777==0o751
    assert (staged/"alias").readlink()==Path("tools/program") and (staged/"empty").is_dir()
    controls=[dict(control="binary-mode-links-source-unavailable",result="passed")]
    run("context-existing",[cli,"project-context-stage",snapshot,"--destination",staged],expected_success=False)
    assert (staged/"tools/program").read_bytes()==payload
    controls.append(dict(control="no-overwrite",result="refused"))
    corrupt=base/"corrupt";shutil.copytree(snapshot,corrupt)
    (corrupt/"data/tools/program").write_bytes(b"changed")
    rejected=base/"rejected"
    run("context-corrupt",[cli,"project-context-stage",corrupt,"--destination",rejected],expected_success=False)
    assert not rejected.exists();controls.append(dict(control="corrupt-before-destination",result="refused"))
    original=base/"owner.retained-offline"
    (original/"root-link").symlink_to(".")
    (original/"compound").symlink_to("root-link/../tools/program")
    malicious=copy.deepcopy(definition);malicious["paths"]+=["root-link","compound"]
    write(base/"compound.json",malicious)
    run("context-link-parent-escape",[cli,"project-context-capture",base/"compound.json","--root",original,"--destination",base/"escape"],expected_success=False)
    assert not (base/"escape").exists()
    controls.append(dict(control="parent-after-link-escape",result="refused"))
    reserved=copy.deepcopy(definition);reserved["paths"].append(".env.local")
    write(base/"reserved.json",reserved)
    run("context-reserved",[cli,"project-context-capture",base/"reserved.json","--root",original,"--destination",base/"reserved"],expected_success=False)
    assert not (base/"reserved").exists()
    controls.append(dict(control="reserved-path",result="refused"))
    receipt=dict(status="passed-project-context-controls",controls=controls,snapshotDigest=captured["digest"],
                 binaryDigest="sha256:"+hashlib.sha256(payload).hexdigest(),completeBuildContextEstablished=False,
                 nativeProjectBuildIntegration="not-qualified",filesDeleted=0)
    write(base/"receipt.json",receipt)
    return receipt
