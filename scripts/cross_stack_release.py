"""Independent Linux/BuildKit/browser acceptance for the declared fixture.

This module never treats parser output as compilation or image evidence. All
containers/images are owned by this invocation and retained; only owned running
containers and frontend process groups are stopped. No registry push occurs.
"""
from contextlib import contextmanager
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import copy
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import uuid


class Unavailable(RuntimeError):
    pass


def dependencies(docker, browser):
    if not shutil.which(str(docker)):
        raise Unavailable("REQUIRED_DOCKER_LANE_UNAVAILABLE")
    if not (Path(browser) / "node_modules/playwright/package.json").is_file():
        raise Unavailable("REQUIRED_BROWSER_LANE_UNAVAILABLE")


def elf(raw):
    if len(raw) < 64 or raw[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError("REQUIRED_LINUX_ELF64_LITTLE_ENDIAN")
    kind, machine = struct.unpack_from("<HH", raw, 16)
    if kind not in (2, 3) or machine != 62:
        raise ValueError("REQUIRED_LINUX_X86_64_EXECUTABLE")
    return {"format": "ELF64", "endianness": "little", "type": kind, "machine": machine}


def request(base, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = Request(base + path, data=data, headers={"content-type": "application/json"})
    try:
        response = urlopen(req, timeout=2)
    except HTTPError as response:
        return response.code, json.loads(response.read())
    with response:
        return response.status, json.loads(response.read())


def verify(root, work, env, run):
    fixture = root / "examples/cross-stack"
    sys.path.insert(0, str(fixture))
    import build
    import workspace
    import dev
    browser = fixture / "acceptance/browser"
    dependencies("docker", browser)
    for label, command in [("docker-version", ["docker", "version"]), ("buildx-version", ["docker", "buildx", "version"]),
                           ("buildkit-info", ["docker", "buildx", "inspect", "--bootstrap"]), ("clang-version", ["clang", "--version"]),
                           ("linker-version", ["ld.lld", "--version"])]:
        run("m6-" + label, command)
    expected = json.loads((fixture / "acceptance/m6-expected.json").read_bytes())
    run("m6-cli", ["cargo", "build", "--release", "-p", "patamaps-cli", "--locked", "--offline"], timeout=900)
    cli = root / "target/release/patamaps"
    cargo = Path(run("m6-cargo", ["rustup", "which", "cargo"]).decode().strip()).resolve()
    rustc = Path(run("m6-rustc", ["rustup", "which", "rustc"]).decode().strip()).resolve()
    node = Path(env["PATAMAPS_DEV_NODE"]).resolve()
    candidate = work / "release-candidate"
    owner, config, policy, _ = workspace.prepare(root, fixture, candidate, cli, node, cargo, rustc, run)
    source_receipt = workspace.bind(candidate, cli, owner, config, policy, run)
    context = candidate / "build-context"
    web = candidate / "app/web"
    dev.copy_tree(fixture / "web/node_modules", web / "node_modules")
    run("m6-next-build", [node, web / "node_modules/next/dist/bin/next", "build", "--webpack"], cwd=web)
    run("m6-next-typecheck", [node, web / "node_modules/typescript/lib/tsc.js", "--noEmit"], cwd=web)
    client = work / "client-js"
    def compile_client(label, source, output):
        run(label, [node, web / "node_modules/typescript/lib/tsc.js", "--target", "ES2022", "--module", "commonjs", "--lib", "ES2022,DOM",
                    "--strict", "--skipLibCheck", "--outDir", output, source])
    compile_client("m6-client", web / "generated/operations.ts", client)
    controls = []
    images = []
    containers = []
    def record(control, **details):
        controls.append({"control": control, **details})
        (work / "image-controls.json").write_text(json.dumps(controls, indent=2) + "\n")
    def retained():
        (work / "owned-docker-objects.json").write_text(json.dumps({"images": images, "containers": containers, "deleted": []}, indent=2) + "\n")
    retained()
    def image(label, ctx, target="runtime", success=True):
        iid = work / (label + ".iid")
        args = ["docker", "buildx", "build", "--load", "--platform", "linux/amd64", "--target", target,
                "--progress", "plain", "--metadata-file", work / (label + ".metadata.json"), "--iidfile", iid,
                "--file", ctx / "deploy/Dockerfile", ctx]
        run(label, args, expected_success=success, timeout=900)
        if not success:
            return None
        identity = iid.read_text().strip()
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", identity), identity
        images.append(identity)
        retained()
        return identity
    def variant(label, transform=None, ignore=None):
        target = work / "image-cases" / label
        shutil.copytree(context, target)
        dockerfile = target / "deploy/Dockerfile"
        if transform:
            before = dockerfile.read_text()
            after = transform(before)
            assert after != before, label + " made no change"
            dockerfile.write_text(after)
        if ignore is not None:
            (target / ".dockerignore").write_text(ignore)
        return target
    @contextmanager
    def container(label, identity):
        name = "patamaps-cross-stack-" + uuid.uuid4().hex
        cid = run(label + "-create", ["docker", "create", "--name", name, "--platform", "linux/amd64", "--memory", "256m", "--cpus", "1",
                   "--pids-limit", "64", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--publish", "127.0.0.1::8080", "--publish", "127.0.0.1::9090", identity]).decode().strip()
        assert re.fullmatch(r"[0-9a-f]{64}", cid)
        containers.append({"id": cid, "image": identity, "name": name, "control": label})
        retained()
        try:
            # OCI startup failure is an observation in negative controls. The
            # positive lane still requires actual health/HTTP/browser results.
            run(label + "-start", ["docker", "start", cid], expected_success=None)
            info = json.loads(run(label + "-inspect", ["docker", "inspect", cid]))[0]
            ports = info["NetworkSettings"]["Ports"]
            urls = {port: ("http://127.0.0.1:" + ports[str(port) + "/tcp"][0]["HostPort"] if ports.get(str(port) + "/tcp") else None) for port in [8080, 9090]}
            yield cid, urls, info
        finally:
            run(label + "-stop", ["docker", "stop", "--time", "2", cid])
            run(label + "-logs", ["docker", "logs", cid])
            run(label + "-final-inspect", ["docker", "inspect", cid])
    def health(base, seconds=8):
        if base is None:
            return None
        deadline = time.monotonic() + seconds
        while True:
            try:
                value = request(base, "/health")
                return value
            except (OSError, ValueError, URLError):
                if time.monotonic() >= deadline:
                    return None
                time.sleep(.1)
    @contextmanager
    def frontend(backend):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        logs = work / "frontend"
        logs.mkdir()
        with (logs / "stdout.log").open("xb") as out, (logs / "stderr.log").open("xb") as err:
            command = [str(node), str(web / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(port)]
            process = subprocess.Popen(command, cwd=web, env=dict(env, CATALOG_SERVICE_URL=backend), stdout=out, stderr=err, start_new_session=True)
            (logs / "invocation.json").write_text(json.dumps({"argv": command, "pid": process.pid, "backend": backend}) + "\n")
            base = "http://127.0.0.1:" + str(port)
            try:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        with urlopen(base, timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("Next image-consumer start failed")
                    time.sleep(.1)
                yield base
            finally:
                dev.stop(process)

    table = run("m6-buildkit-targets", ["docker", "buildx", "build", "--call=targets", "--file", context / "deploy/Dockerfile", context]).decode()
    assert re.search(r"(?m)^builder\s", table) and re.search(r"(?m)^runtime\s", table), table
    record("m6-buildkit-stages", result="independently-observed", requiredStages=["builder", "runtime"])
    positive = image("m6-positive-image", context)
    image_info = json.loads(run("m6-image-inspect", ["docker", "image", "inspect", positive]))[0]
    assert (image_info["Os"], image_info["Architecture"]) == ("linux", "amd64")
    cfg = image_info["Config"]
    assert cfg["Entrypoint"] == ["/usr/local/bin/catalog-service"] and cfg["Cmd"] == ["/app/service.toml"]
    assert cfg["User"] == "65532:65532" and cfg["WorkingDir"] == "/app" and "8080/tcp" in cfg["ExposedPorts"]
    # Export only explicit builder evidence, not a duplicate Rust base filesystem.
    evidence_dockerfile = work / "inspection.Dockerfile"
    raw_dockerfile = (context / "deploy/Dockerfile").read_text()
    evidence_dockerfile.write_text(raw_dockerfile + '\nFROM scratch AS inspection\nCOPY --from=builder /build/cargo-messages.jsonl /cargo-messages.jsonl\nCOPY --from=builder /build/rustc-version.txt /rustc-version.txt\nCOPY --from=builder /build/licenses /licenses\nCOPY --from=builder /build/service/target/x86_64-unknown-linux-gnu/release/catalog-service /catalog-service\n')
    exported = work / "builder-evidence"
    run("m6-builder-evidence", ["docker", "buildx", "build", "--platform", "linux/amd64", "--target", "inspection", "--progress", "plain",
         "--metadata-file", work / "m6-builder-evidence.metadata.json", "--output", "type=local,dest=" + str(exported), "--file", evidence_dockerfile, context], timeout=900)
    artifacts = [json.loads(line) for line in (exported / "cargo-messages.jsonl").read_text().splitlines()]
    selected = [item for item in artifacts if item.get("reason") == "compiler-artifact" and item["target"]["name"] == "catalog-service" and item["target"]["kind"] == ["bin"]]
    assert len(selected) == 1 and selected[0]["executable"] == "/build/service/target/x86_64-unknown-linux-gnu/release/catalog-service"
    assert selected[0]["profile"]["opt_level"] == "3" and selected[0]["profile"]["test"] is False
    compiler_version = (exported / "rustc-version.txt").read_text()
    assert "release: 1.99.0\n" in compiler_version and "host: x86_64-unknown-linux-gnu\n" in compiler_version
    binary_digest = build.digest((exported / "catalog-service").read_bytes())
    format_evidence = elf((exported / "catalog-service").read_bytes())
    run("m6-elf-loader", ["readelf", "--program-headers", exported / "catalog-service"])
    run("m6-elf-libraries", ["readelf", "--dynamic", exported / "catalog-service"])
    assert "ld-linux-x86-64.so.2" in (work / "m6-elf-loader.stdout.log").read_text()
    record("m6-cargo-linux-artifact", result="compiled-and-inspected", digest=binary_digest, target=selected[0], compiler=compiler_version, executable=format_evidence)
    notices = {p.relative_to(exported / "licenses").as_posix(): build.digest(p.read_bytes()) for p in (exported / "licenses").rglob("*") if p.is_file()}
    assert {"application/LICENSE", "application/NOTICE", "rust/LICENSE-MIT", "rust/LICENSE-APACHE", "rust/COPYRIGHT"} <= notices.keys()
    for artifact in artifacts:
        package = artifact.get("package_id", "")
        if artifact.get("reason") == "compiler-artifact" and package.startswith("registry+"):
            name, version = package.rsplit("#", 1)[1].rsplit("@", 1)
            assert any(p.startswith("crates/" + name + "-" + version + "/") for p in notices), package
    actual = work / "image-contents"
    actual.mkdir()
    with container("m6-positive", positive) as (cid, urls, info):
        assert info["Image"] == positive
        for label, source, target in [("binary", "/usr/local/bin/catalog-service", actual / "catalog-service"),
                                      ("config", "/app/service.toml", actual / "service.toml"),
                                      ("notices", "/usr/share/licenses/catalog-service", actual / "licenses")]:
            run("m6-copy-" + label, ["docker", "cp", cid + ":" + source, target])
        assert build.digest((actual / "catalog-service").read_bytes()) == binary_digest
        config_digest = build.digest((actual / "service.toml").read_bytes())
        assert (actual / "service.toml").read_bytes() == (context / "config/service.toml").read_bytes()
        actual_notices = {p.relative_to(actual / "licenses").as_posix(): build.digest(p.read_bytes()) for p in (actual / "licenses").rglob("*") if p.is_file()}
        assert actual_notices == notices
        record("m6-image-bytes-config-licenses", result="equal-to-builder-and-captured-input", image=positive, configDigest=config_digest, noticeDigests=notices)
        assert health(urls[8080]) == (200, {"status": "ok"})
        with frontend(urls[8080]) as base:
            wire = json.loads(run("m6-runtime-contract", [node, fixture / "acceptance/check-runtime.cjs", client / "operations.js", base, urls[8080]]))
            assert request(base, "/api/items", raw=b'{"name":') == (400, {"error": "invalid-request"})
            assert request(urls[8080], "/items", raw=b'{"name":') == (400, {"error": "invalid-request"})
            record("m6-real-next-linux-http", result="passed", health={"status": "ok"}, malformedNextStatus=400, malformedServiceStatus=400, **wire)
            browser_work = work / "browser"
            browser_work.mkdir()
            run("m6-browser", [node, browser / "check.cjs", base, browser_work], timeout=120)
            browser_receipt = json.loads((browser_work / "browser-receipt.json").read_bytes())
            assert browser_receipt["status"] == "passed"
            record("m6-real-browser", **browser_receipt)
            stale = work / "stale-client"
            stale.mkdir()
            code = (web / "generated/operations.ts").read_text()
            changed = code.replace('"/api/items"', '"/api/stale-items"')
            assert changed != code
            (stale / "operations.ts").write_text(changed)
            compile_client("m6-stale-client-compile", stale / "operations.ts", stale / "js")
            run("m6-stale-client-http", [node, fixture / "acceptance/check-runtime.cjs", stale / "js/operations.js", base, urls[8080]], expected_success=False)
            record("m6-stale-generated-client", result="actual-HTTP-contract-refusal", typescriptCompilation="passed")
    alias = variant("alias-index", lambda raw: raw.replace("AS builder", "AS renamed").replace("--from=builder", "--from=0"))
    alias_id = image("m6-alias-index", alias)
    with container("m6-alias-runtime", alias_id) as (_, urls, _):
        assert health(urls[8080]) == (200, {"status": "ok"})
    record("m6-buildkit-alias-index", result="actual-image-and-runtime-pass")
    arg = variant("explicit-arg-json-copy", lambda raw: raw.replace("FROM rust:1.99.0-bookworm AS builder", "ARG BASE=rust:1.99.0-bookworm\nFROM ${BASE} AS builder").replace("COPY config/service.toml /app/service.toml", 'COPY ["config/service.toml", "/app/service.toml"]'))
    arg_id = image("m6-explicit-arg-json-copy", arg)
    with container("m6-arg-runtime", arg_id) as (_, urls, _):
        assert health(urls[8080]) == (200, {"status": "ok"})
    record("m6-buildkit-explicit-arg-json-copy", result="actual-image-and-runtime-pass")
    specific = variant("specific-ignore", ignore="config/service.toml\n")
    (specific / "deploy/Dockerfile.dockerignore").write_text("**/target\n")
    specific_id = image("m6-specific-ignore", specific)
    with container("m6-specific-runtime", specific_id) as (_, urls, _):
        assert health(urls[8080]) == (200, {"status": "ok"})
    record("m6-buildkit-specific-ignore", result="actual-specific-ignore-precedence-pass")
    for label, transform, ignore, target in [
        ("broken-copy", lambda raw: raw.replace("/release/catalog-service", "/release/absent-service"), None, "runtime"),
        ("ignored-config", None, (context / ".dockerignore").read_text() + "\nconfig/service.toml\n", "runtime"),
        ("wrong-stage", lambda raw: raw.replace("--from=builder", "--from=9"), None, "runtime")]:
        case = variant(label, transform, ignore)
        image("m6-buildkit-" + label, case, target=target, success=False)
        record("m6-buildkit-" + label, result="actual-BuildKit-refusal")
    negative_cases = [
        ("wrong-binary", lambda raw: raw.replace("COPY --from=builder /build/service/target/x86_64-unknown-linux-gnu/release/catalog-service", "COPY --from=builder /usr/bin/true")),
        ("missing-config", lambda raw: raw.replace("COPY config/service.toml /app/service.toml\n", "")),
        ("missing-loader-library", lambda raw: raw.replace("FROM debian:bookworm-slim AS runtime", "FROM scratch AS runtime")),
        ("wrong-listener", lambda raw: raw.replace("COPY config/service.toml /app/service.toml", "COPY config/wrong-listener.toml /app/service.toml"))]
    for label, transform in negative_cases:
        case = variant(label, transform)
        if label == "wrong-listener":
            (case / "config/wrong-listener.toml").write_text('[http]\nlisten = "0.0.0.0:8081"\n')
        identity = image("m6-image-" + label, case)
        with container("m6-runtime-" + label, identity) as (_, urls, _):
            assert health(urls[8080], seconds=3) is None, label + " unexpectedly satisfied service health"
        record("m6-" + label, result="actual-image-runtime-refusal", image=identity)
    assembly = work / "wrong-architecture.S"
    assembly.write_text('.global _start\n_start:\n mov x0, #0\n mov x8, #93\n svc #0\n')
    incompatible = work / "wrong-architecture.elf"
    run("m6-build-incompatible-elf", ["clang", "--target=aarch64-linux-gnu", "-fuse-ld=lld", "-nostdlib", "-static", "-Wl,-e,_start", assembly, "-o", incompatible])
    assert incompatible.read_bytes()[:4] == b"\x7fELF" and struct.unpack_from("<H", incompatible.read_bytes(), 18)[0] == 183
    try:
        elf(incompatible.read_bytes())
    except ValueError:
        pass
    else:
        raise AssertionError("Wrong architecture passed independent artifact gate")
    arch = variant("wrong-architecture", lambda raw: raw.replace("COPY --from=builder /build/service/target/x86_64-unknown-linux-gnu/release/catalog-service", "COPY wrong-architecture"))
    shutil.copy2(incompatible, arch / "wrong-architecture")
    arch_id = image("m6-image-wrong-architecture", arch)
    with container("m6-runtime-wrong-architecture", arch_id) as (_, urls, _):
        assert health(urls[8080], seconds=3) is None
    record("m6-wrong-architecture", result="format-gate-and-actual-runtime-refusal", observedMachine=183, requiredMachine=62)
    exposure = variant("wrong-expose", lambda raw: raw.replace("EXPOSE 8080", "EXPOSE 9090"))
    exposure_id = image("m6-image-wrong-expose", exposure)
    with container("m6-runtime-wrong-expose", exposure_id) as (_, urls, _):
        assert health(urls[8080]) == (200, {"status": "ok"}) and health(urls[9090], seconds=2) is None
    record("m6-expose-is-not-listener", result="advertised-port-closed-actual-listener-observed", advertised=9090, actual=8080)
    for label, docker, path in [("docker", work / "absent-docker", browser), ("browser", "docker", work / "absent-browser")]:
        try:
            dependencies(docker, path)
        except Unavailable as error:
            (work / ("unavailable-" + label + ".json")).write_text(json.dumps({"status": "unavailable", "reason": str(error), "fullReleaseAccepted": False}) + "\n")
        else:
            raise AssertionError("Missing required lane was skipped")
    record("m6-missing-required-lanes", result="unavailable-refuses-full-release", lanes=["docker", "browser"])
    release = {"artifactDigest": binary_digest, "configurationDigest": config_digest, "image": positive, "platform": "linux/amd64",
               "cargoTarget": selected[0]["target"]["name"], "executable": format_evidence, "http": True, "browser": True}
    admission = admit_release(candidate, cli, release, run)
    record("m6-native-release-admission", result="native-admission-and-offline-replay-passed", **admission)
    record("m6-native-evidence-refusals", result="native-refusals", controls=admission["negativeControls"])
    assert {value["control"] for value in controls} == set(expected["controls"])
    return {"status": "passed-linux-image-browser-scope", "controls": controls, "source": source_receipt, "release": release,
            "metamapCompatibility": "pending-M7", "installedConsumer": "pending-M7", "fullReleaseAccepted": False,
            "productionActivation": "not-performed", "ownedObjects": str(work / "owned-docker-objects.json")}


def admit_release(candidate, cli, release, run):
    """Add tool observations to a fresh native workspace; never mutate a capture."""
    import build
    import workspace
    config = json.loads((candidate / "workspace.json").read_bytes())
    policy = json.loads((candidate / "policy.json").read_bytes())
    prefix = workspace.WORKSPACE + ":release"
    graph = {"schemaVersion": "0.1.0", "documentType": "graph", "id": prefix, "namespace": "cross-stack-release", "entities": [], "mappings": [], "authorities": []}
    subjects = [
        ("artifact", "build:artifact", {"evidenceClass": "independent-tool-observation", "compilationEstablished": True,
          "digest": release["artifactDigest"], "platform": release["platform"], "target": release["cargoTarget"], "format": release["executable"]}),
        ("image", "release:image", {"evidenceClass": "independent-tool-observation", "identity": release["image"], "platform": release["platform"],
          "artifactDigest": release["artifactDigest"], "configurationDigest": release["configurationDigest"], "imageBytesCompared": True}),
        ("configuration", "build:configuration", {"evidenceClass": "independent-tool-observation", "digest": release["configurationDigest"],
          "destination": "/app/service.toml", "imageContentsEstablished": True}),
        ("runtime", "release:runtime", {"evidenceClass": "independent-tool-observation", "image": release["image"], "healthy": True,
          "realNextRustHttp": release["http"], "actualBrowserInteraction": release["browser"]})]
    for name, kind, attributes in subjects:
        subject = prefix + ":requirement:" + name
        target = prefix + ":observation:" + name
        graph["entities"] += [{"id": target, "kind": kind, "attributes": attributes}, {"id": subject, "kind": "build:requirement", "attributes": {"evidenceClass": "owner-authored"}}]
        mapping = {"id": subject + ":binding", "relation": "core:references", "sources": [subject], "targets": [target], "cardinality": "one-to-one", "lossiness": "lossless",
                   "provenance": {"status": "declared", "assertedBy": "fixture-owner"}}
        graph["mappings"].append(mapping)
        policy["mappings"].append({"mapping": mapping["id"], "coverage": "total", "determinism": "deterministic", "reversibility": "irreversible"})
        policy["constraints"].append({"id": subject + ":observations", "kind": "build:observation-binding-v1", "subjects": [subject],
            "parameters": {"relation": "core:references", "targetKind": kind, "conditions": [{"path": ["attributes", key], "equals": value} for key, value in attributes.items()]}})
        for constraint_kind in ["core:requires-mapping", "core:unique-target"]:
            policy["constraints"].append({"id": subject + ":" + constraint_kind, "kind": constraint_kind, "subjects": [subject], "parameters": {"relation": "core:references", "direction": "source"}})
    owner = json.loads((candidate / "app/contracts/operations.json").read_bytes())
    source = json.loads((candidate / "source-intent.json").read_bytes())
    stages = next(v["matches"] for v in source["requirements"] if v["name"] == "runtime")
    assert len(stages) == 1
    links = [(owner["operations"][0]["id"] + ":linux-artifact", prefix + ":observation:artifact"),
             (workspace.WORKSPACE + ":configuration", prefix + ":observation:configuration"),
             (stages[0], prefix + ":observation:image"),
             (prefix + ":observation:image", prefix + ":observation:artifact"),
             (prefix + ":observation:image", prefix + ":observation:configuration"),
             (prefix + ":observation:runtime", prefix + ":observation:image")]
    for index, (source_id, target_id) in enumerate(links):
        mid = prefix + ":chain:" + str(index)
        graph["mappings"].append({"id": mid, "relation": "core:references", "sources": [source_id], "targets": [target_id],
            "cardinality": "one-to-one", "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "fixture-owner"}})
        policy["mappings"].append({"mapping": mid, "coverage": "total", "determinism": "deterministic", "reversibility": "irreversible"})
    workspace.write(candidate / "release-observations.json", graph)
    workspace.write(candidate / "release-policy.json", policy)
    config["sources"].append({"adapter": "portable-shard", "id": prefix + ":source", "path": "release-observations.json"})
    config["policy"] = "release-policy.json"
    config["context"]["mode"] = "observed-linux-image-browser"
    workspace.write(candidate / "release-workspace.json", config)
    admitted = json.loads(run("m6-release-admit", [cli, "generate", "release-workspace.json", "--root", candidate], cwd=candidate))
    assert admitted["cacheHits"] == 0
    workspace.write(candidate / "release-baseline.json", admitted["baseline"])
    run("m6-release-offline", [cli, "verify-workspace", candidate / "release-baseline.json"], cwd=candidate)
    negatives = []
    for label, name, key, value in [("uncompiled", "artifact", "compilationEstablished", False),
                                   ("stale-config", "configuration", "digest", "sha256:" + "0" * 64),
                                   ("different-image", "image", "identity", "sha256:" + "0" * 64),
                                   ("unobserved-browser", "runtime", "actualBrowserInteraction", False),
                                   ("ambiguous-artifact", "artifact", None, None)]:
        changed = copy.deepcopy(graph)
        observation = next(v for v in changed["entities"] if v["id"] == prefix + ":observation:" + name)
        if key:
            observation["attributes"][key] = value
        else:
            duplicate = copy.deepcopy(observation)
            duplicate["id"] += ":duplicate"
            changed["entities"].append(duplicate)
        graph_path = "release-negative-" + label + ".json"
        workspace.write(candidate / graph_path, changed)
        negative_config = copy.deepcopy(config)
        negative_config["sources"][-1]["path"] = graph_path
        config_path = "release-workspace-negative-" + label + ".json"
        workspace.write(candidate / config_path, negative_config)
        command_label = "m6-release-refuse-" + label
        output = run(command_label, [cli, "generate", config_path, "--root", candidate], cwd=candidate, expected_success=False)
        # Both CI and the retained native driver store command logs at work.
        diagnostic = output.decode() + (candidate.parent / (command_label + ".stderr.log")).read_text()
        assert "BUILD_OBSERVATION_BINDING_MISMATCH" in diagnostic, diagnostic[-2000:]
        negatives.append({"control": label, "result": "refused", "code": "BUILD_OBSERVATION_BINDING_MISMATCH"})
    # A rehashed observation cannot be substituted for the original tool work by
    # this entry point: verify() above must succeed before admission is reachable.
    return {"baseline": admitted["baseline"]["digest"], "toolAuthenticationEstablished": False, "offlineImageBytesReexecuted": False, "negativeControls": negatives}
