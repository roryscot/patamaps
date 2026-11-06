"""Compiled Next observation CLI controls; fixture manifests are not app runtime proof."""
from pathlib import Path
import copy,hashlib,json,os

def verify(root,work,env,run):
    cli=root/("target/"+env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE","debug")+"/patamaps")
    base=work/"next-build-observations";base.mkdir()
    source=base/"inputs";source.mkdir()
    def sha(raw):return "sha256:"+hashlib.sha256(raw).hexdigest()
    def write(path,value):
        with path.open("x") as f:json.dump(value,f,indent=2);f.write("\n")
    routes=dict(version=3,pages404=True,appType="app",caseSensitive=False,basePath="",
                staticRoutes=[dict(page="/",regex="^/$",namedRegex="^/$",routeKeys={})],
                dynamicRoutes=[dict(page="/item/[id]",regex="^/item/([^/]+)$",namedRegex="^/item/(?<id>[^/]+)$",routeKeys=dict(id="id"))],
                redirects=[],headers=[],rewrites=dict(beforeFiles=[dict(source="/old",destination="/new",regex="^/old$",
                  has=[dict(type="header",key="x-mode",value="on")])],afterFiles=[],fallback=[]),
                dataRoutes=[],rsc=dict(header="rsc"),rewriteHeaders=dict(pathHeader="x-rewritten-path"))
    apps={"/(group)/page":"app/(group)/page.js","/item/[id]/page":"app/item/[id]/page.js"}
    app_routes={"/(group)/page":"/","/item/[id]/page":"/item/[id]"}
    write(source/"routes.json",routes);write(source/"apps.json",apps);write(source/"app-routes.json",app_routes)
    projection=dict(profile="patamaps-next-build-config-1",frameworkVersion="16.1.6",buildReceiptDigest="sha256:"+"a"*64,
                    routesDigest=sha((source/"routes.json").read_bytes()),appPathsDigest=sha((source/"apps.json").read_bytes()),
                    appPathRoutesDigest=sha((source/"app-routes.json").read_bytes()),
                    configuration=dict(basePath="",output="standalone",trailingSlash=False,
                       environment=dict(NEXT_PUBLIC_API_URL="http://127.0.0.1:1"),secretReferences=dict(AUTH_TOKEN="OWNER_AUTH_TOKEN"),
                       transpilePackages=[],serverActions=None))
    write(source/"config.json",projection)
    identity="urn:qualification:compiled-next"
    profile=dict(profile="patamaps-project-inputs-1",id=identity+":inputs",nonsecretInputs=True,
                 inputs=["routes.json","apps.json","app-routes.json","config.json"],components=[dict(id="build",kind="configuration",root=".",entrypoints=["config.json"])],
                 nonsecretConfiguration={},secretReferences={})
    write(base/"profile.json",profile)
    invocation=dict(executable=str(cli),arguments=["discover-native"],codeInputs=[],
                    bounds=dict(maximumElapsedMs=60000,maximumStdoutBytes=16777216,maximumStderrBytes=65536))
    config=dict(schemaVersion="0.1.0",documentType="workspace-config",id=identity,namespace="next-build-controls",revision="1",
                sources=[dict(adapter="process",id=identity+":source",invocation=invocation,
                  inputs=["inputs/routes.json","inputs/apps.json","inputs/app-routes.json","inputs/config.json"],
                  config=dict(provider="next-build",nonsecretInputs=True,routesManifest="inputs/routes.json",
                    appPathsManifest="inputs/apps.json",appPathRoutesManifest="inputs/app-routes.json",
                    configurationProjection="inputs/config.json"))],
                packs=[],policy="policy.json",projections=[dict(path="projection.json",emissions=[dict(path="observations.json",language="json")])],
                context=dict(scope="captured-compiled-next-observations"),evaluatedAt="2026-10-16T00:00:00Z")
    write(base/"workspace.json",config)
    write(base/"policy.json",dict(schemaVersion="0.1.0",documentType="policy",id=identity+":policy",graph=dict(id=identity,revision="1"),
                                 mappings=[],constraints=[],evidence=[]))
    write(base/"projection.json",dict(schemaVersion="0.1.0",documentType="projection-spec",id=identity+":projection",
                                      select=dict(kinds=["next-build-route"]),slots=[]))
    run("next-build-input-capture",[cli,"project-capture",base/"profile.json","--root",source,"--output",base/"capture.json"])
    generated=json.loads(run("next-build-generate",[cli,"generate",base/"workspace.json","--root",base]))
    baseline=generated["baseline"];write(base/"baseline.json",baseline)
    entities=baseline["captures"][0]["inputs"]["graph"]["entities"]
    assert sum(e["kind"]=="next-build-route" for e in entities)==2
    modules={e["attributes"]["appPath"]:e["attributes"] for e in entities if e["kind"]=="next-build-module"}
    assert {key:value["moduleFile"] for key,value in modules.items()}==apps
    assert {key:value["routePath"] for key,value in modules.items()}==app_routes
    rule=next(e for e in entities if e["kind"]=="next-build-rule")
    assert rule["attributes"]["rule"]==routes["rewrites"]["beforeFiles"][0]
    controls=[dict(control="compiled-manifest-workspace",result="passed",routeGroups=True,conditionsPreserved=True,runtime=False)]
    for label,change in [
        ("digest",lambda v:v.update(routesDigest="sha256:"+"b"*64)),
        ("app-path-routes-digest",lambda v:v.update(appPathRoutesDigest="sha256:"+"c"*64)),
        ("public-env",lambda v:v["configuration"]["environment"].update(AUTH_TOKEN="must-refuse")),
        ("projection-unknown",lambda v:v["configuration"].update(unreviewed=True)),
    ]:
        value=copy.deepcopy(projection);change(value)
        retained=source/("config."+label+".original.json")
        (source/"config.json").rename(retained);write(source/"config.json",value)
        try:
            run("next-build-refuse-"+label,[cli,"generate",base/"workspace.json","--root",base],expected_success=False)
        finally:
            (source/"config.json").rename(source/("config."+label+".rejected.json"))
            retained.rename(source/"config.json")
        controls.append(dict(control="refuse-"+label,result="refused"))
    (source/"config.json").rename(source/"config.retained-missing.json")
    try:run("next-build-refuse-missing",[cli,"generate",base/"workspace.json","--root",base],expected_success=False)
    finally:(source/"config.retained-missing.json").rename(source/"config.json")
    controls.append(dict(control="refuse-missing",result="refused"))
    source.rename(base/"inputs.retained-offline")
    replay=json.loads(run("next-build-offline",["/usr/bin/env","-i","PATH=",cli,"verify-workspace",base/"baseline.json"]))
    assert replay["status"]=="verified-record-bindings"
    controls.append(dict(control="offline-baseline-replay",result="passed",configuredSourceUnavailable=True,externalPathEmpty=True))
    receipt=dict(status="passed-next-build-observation-controls",controls=controls,baselineDigest=baseline["digest"],
                 scope="synthetic captured manifests; no compiler/HTTP/real-project claim",filesDeleted=0)
    write(base/"receipt.json",receipt)
    return receipt
