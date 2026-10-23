"""Build and observe the unchanged selected Miniserve bundle as a real OCI image."""
import argparse, gzip, hashlib, json, re, shutil, socket, subprocess, time, uuid
from pathlib import Path
from urllib.request import urlopen

BASE = "ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55"
BASE_ID = "sha256:69f919497cada9a8611f3de61df902d9f94bf20f84552ef5bd93125c38608ef9"
ENTRYPOINT = ["/bin/bash", "/app/launch.sh"]


def sha(path):
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def check_launch(info, image):
    if info["Image"] != image or info["Config"]["Entrypoint"] != ENTRYPOINT or info["Config"].get("Cmd") not in [None, []]:
        raise ValueError("IMAGE_LAUNCH_CONFIGURATION")
    if info["Config"]["User"] != "65532:65532" or info["Config"]["WorkingDir"] != "/app":
        raise ValueError("IMAGE_USER_OR_WORKDIR")


def stop_owned(path):
    """The CI always-step may stop only named, label-matching containers we created."""
    if not path.exists():
        return
    owned = json.loads(path.read_bytes())
    for item in owned["containers"]:
        identity = item["id"]
        assert re.fullmatch("[0-9a-f]{64}", identity)
        info = json.loads(subprocess.check_output(["docker", "inspect", identity], timeout=15))[0]
        assert info["Config"]["Labels"]["org.patamaps.qualification-owner"] == owned["token"]
        if info["State"]["Running"]:
            subprocess.run(["docker", "stop", "--time", "3", identity], check=True, timeout=15)
        final = json.loads(subprocess.check_output(["docker", "inspect", identity], timeout=15))[0]
        assert not final["State"]["Running"]
        item["confirmedStopped"] = True
    write(path, owned)


def verify(root, work, out, candidate, cli, license_path, run):
    folder = work / "application-image"
    folder.mkdir()
    context = folder / "context"
    context.mkdir()
    bundle = candidate / "bundle"
    files = {p.relative_to(bundle).as_posix(): sha(p) for p in bundle.rglob("*") if p.is_file()}
    assert set(files) == {"configuration.json", "launch.sh", "miniserve", "probe.sh", "public/status.txt"}
    shutil.copytree(bundle, context / "bundle")
    shutil.copy2(license_path, context / "MINISERVE-LICENSE")
    dockerfile = ("FROM " + BASE + " AS runtime\n"
                  "WORKDIR /app\n"
                  "COPY --chown=65532:65532 bundle/ /app/\n"
                  "COPY MINISERVE-LICENSE /licenses/MINISERVE-LICENSE\n"
                  "USER 65532:65532\n"
                  "EXPOSE 9100/tcp\n"
                  'ENTRYPOINT ["/bin/bash", "/app/launch.sh"]\n')
    (context / "Dockerfile").write_text(dockerfile)
    context_before = {p.relative_to(context).as_posix(): sha(p) for p in context.rglob("*") if p.is_file()}
    expected = files["miniserve"]
    run("image-input-elf", [cli, "elf-target-check", context / "bundle/miniserve", "--target", "linux/amd64", "--digest", expected])
    run("image-docker-version", ["docker", "version", "--format", "{{json .}}"])
    run("image-pull-base", ["docker", "pull", "--platform", "linux/amd64", BASE], timeout=180)
    base = json.loads(run("image-base-inspect", ["docker", "image", "inspect", BASE]))[0]
    assert base["Id"] == BASE_ID and BASE in base["RepoDigests"]
    iid, metadata = folder / "image.iid", out / "image-build-metadata.json"
    run("image-buildkit-build", ["docker", "buildx", "build", "--load", "--platform", "linux/amd64", "--network", "none",
                                "--provenance=false", "--target", "runtime", "--progress", "plain", "--iidfile", iid,
                                "--metadata-file", metadata, "--file", context / "Dockerfile", context], timeout=300)
    identity = iid.read_text().strip()
    assert re.fullmatch("sha256:[0-9a-f]{64}", identity)
    image = json.loads(run("image-built-inspect", ["docker", "image", "inspect", identity]))[0]
    assert image["Size"] < 200000000
    assert image["Id"] == identity and (image["Os"], image["Architecture"]) == ("linux", "amd64")
    assert image["Config"]["Entrypoint"] == ENTRYPOINT and image["Config"].get("Cmd") in [None, []]
    assert image["Config"]["User"] == "65532:65532" and image["Config"]["WorkingDir"] == "/app"
    assert "9100/tcp" in image["Config"]["ExposedPorts"]
    tools = folder / "browser-tools"
    tools.mkdir()
    for name in ["package.json", "package-lock.json"]:
        shutil.copy2(root / "examples/cross-stack/acceptance/browser" / name, tools / name)
    lock = sha(tools / "package-lock.json")
    browser_env = dict(PLAYWRIGHT_BROWSERS_PATH=str(folder / "chromium"), PLAYWRIGHT_SKIP_BROWSER_GC="1", NODE_PATH=str(tools / "node_modules"))
    run("image-browser-locked-install", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=tools, extra=browser_env, timeout=180)
    run("image-browser-runtime-install", ["node", tools / "node_modules/playwright/cli.js", "install", "chromium", "--only-shell"], extra=browser_env, timeout=180)
    assert sha(tools / "package-lock.json") == lock
    owned_path = out / "image-owned.json"
    token = uuid.uuid4().hex
    owned = dict(token=token, images=[identity], containers=[], filesDeleted=0)
    write(owned_path, owned)

    def create(label, override=()):
        value = run(label + "-create", ["docker", "create", "--name", "patamaps-miniserve-" + token + "-" + label,
                    "--label", "org.patamaps.qualification-owner=" + token, "--platform", "linux/amd64",
                    "--network", "host", "--cpus", "1", "--memory", "268435456", "--memory-swap", "268435456",
                    "--pids-limit", "64", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                    "--shm-size", "1048576", "--tmpfs", "/tmp:rw,noexec,nosuid,size=1048576,mode=1777", *override, identity]).strip()
        assert re.fullmatch("[0-9a-f]{64}", value)
        owned["containers"].append(dict(id=value, label=label, confirmedStopped=False))
        write(owned_path, owned)
        return value

    result = dict(status="running", imageId=identity, base=BASE, baseImageId=BASE_ID, bundleFiles=files,
                  contextFiles=context_before, browserDependencyLock=lock, applicationRecompiled=False,
                  hostNetwork=True, networkIsolationClaimed=False, productionActivation=False, registryPublication=False,
                  completeNativeDockerContextObservation=False)
    container = None
    try:
        refused = create("entrypoint-refused", ["--entrypoint", "/bin/false"])
        refused_info = json.loads(run("image-override-inspect", ["docker", "inspect", refused]))[0]
        try:
            check_launch(refused_info, identity)
        except ValueError as error:
            assert str(error) == "IMAGE_LAUNCH_CONFIGURATION"
        else:
            raise AssertionError("Entrypoint override was admitted")
        assert not refused_info["State"]["Running"] and refused_info["State"]["StartedAt"].startswith("0001-")
        result["actualEntrypointOverrideRefusedBeforeStart"] = True
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 9100))
        container = create("positive")
        info = json.loads(run("image-runtime-inspect-before", ["docker", "inspect", container]))[0]
        check_launch(info, identity)
        cfg = info["HostConfig"]
        assert cfg["ReadonlyRootfs"] and cfg["NetworkMode"] == "host" and not cfg.get("PortBindings")
        assert cfg["NanoCpus"] == 1000000000 and cfg["Memory"] == cfg["MemorySwap"] == 268435456 and cfg["PidsLimit"] == 64
        assert cfg["CapDrop"] == ["ALL"] and "no-new-privileges" in cfg["SecurityOpt"]
        assert cfg["ShmSize"] == 1048576 and cfg["Tmpfs"] == {"/tmp": "rw,noexec,nosuid,size=1048576,mode=1777"}
        assert not cfg.get("Binds") and not any(m["Type"] in ["bind", "volume"] for m in info["Mounts"])
        run("image-runtime-start", ["docker", "start", container])
        expected_body = (bundle / "public/status.txt").read_bytes()
        deadline = time.monotonic() + 15
        while True:
            try:
                with urlopen("http://127.0.0.1:9100/qualified/status.txt", timeout=1) as response:
                    assert response.status == 200 and response.read() == expected_body
                break
            except OSError:
                assert time.monotonic() < deadline, "Image listener never became ready"
                time.sleep(.1)
        readback = run("image-kernel-limits", ["docker", "exec", container, "/bin/sh", "-c",
                       "cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.swap.max /sys/fs/cgroup/pids.max"]).splitlines()
        assert readback == ["100000 100000", "268435456", "0", "64"], readback
        result["kernelLimits"] = readback
        quota = run("image-writable-quotas", ["docker", "exec", container, "df", "-B1", "--output=size", "/tmp", "/dev/shm"]).splitlines()[1:]
        assert [int(v) for v in quota] == [1048576, 1048576], quota
        result["writableFilesystemBytes"] = [1048576, 1048576]
        mounts = run("image-writable-mounts", ["docker", "exec", container, "cat", "/proc/mounts"])
        assert any(row.split()[1] == "/" and "ro" in row.split()[3].split(",") for row in mounts.splitlines())
        observed = folder / "observed-runtime"
        run("image-runtime-export", ["docker", "cp", container + ":/app/miniserve", observed])
        assert sha(observed) == expected
        run("image-runtime-elf", [cli, "elf-target-check", observed, "--target", "linux/amd64", "--digest", expected])
        browser_out = out / "image-browser"
        browser_out.mkdir()
        run("image-real-browser", ["node", root / "scripts/deployment/miniserve/browser.cjs",
                                  "http://127.0.0.1:9100", browser_out, bundle / "public/status.txt"], extra=browser_env, timeout=120)
        browser = json.loads((browser_out / "receipt.json").read_bytes())
        assert browser["status"] == "passed" and browser["actualFileLinkNavigation"] and not browser["pageErrors"] and not browser["offOriginRequests"]
        assert {p.relative_to(context).as_posix(): sha(p) for p in context.rglob("*") if p.is_file()} == context_before
        assert {p.relative_to(bundle).as_posix(): sha(p) for p in bundle.rglob("*") if p.is_file()} == files
        result.update(status="verified-image-browser-awaiting-owned-stop", browser=browser, imageRuntimeBytesMatchSelected=True,
                      contextAndSelectedBundleUnchanged=True, runtimeHostBindMounts=False)
        archive = folder / "image.tar"
        run("image-export", ["docker", "image", "save", "--output", archive, identity], timeout=120)
        assert archive.stat().st_size < 256000000
        artifacts = out / "image-artifacts"
        artifacts.mkdir()
        compressed = artifacts / "miniserve-image.tar.gz"
        with archive.open("rb") as src, compressed.open("xb") as dst, gzip.GzipFile(filename="", mode="wb", fileobj=dst, mtime=0) as gz:
            shutil.copyfileobj(src, gz)
        result["imageArchive"] = dict(path="image-artifacts/miniserve-image.tar.gz", digest=sha(compressed),
                                     bytes=compressed.stat().st_size, uncompressedBytes=archive.stat().st_size)
    except BaseException as error:
        result.update(status="failed", error=str(error))
        raise
    finally:
        stop_owned(owned_path)
        if container:
            run("image-runtime-logs", ["docker", "logs", container])
            stopped = json.loads(run("image-runtime-final-inspect", ["docker", "inspect", container]))[0]
            assert not stopped["State"]["Running"]
            with socket.socket() as probe:
                assert probe.connect_ex(("127.0.0.1", 9100)) != 0, "Owned listener survived stop"
            result["ownedContainerAndListenerStopped"] = True
        write(out / "image-receipt.json", result)
    result["status"] = "passed-real-rust-image-browser"
    write(out / "image-receipt.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop-owned", type=Path, required=True)
    stop_owned(parser.parse_args().stop_owned)
