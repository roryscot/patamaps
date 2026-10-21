#!/usr/bin/env python3
"""Qualify pinned Fumadocs source and, optionally, its isolated Next production build.

This does not establish runtime, deployment, hermetic dependencies or release acceptance.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import shutil
import subprocess
import tarfile
import time
import urllib.request

REVISION = "2919bf9a9a84a7a594d42460878548d0677d7bb3"
UPSTREAM = "https://github.com/fuma-nama/fumadocs.git"
NODE_ARCHIVE = "https://nodejs.org/dist/v24.21.0/node-v24.21.0-linux-x64.tar.xz"
NODE_ARCHIVE_SHA = "fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6"
PNPM_ARCHIVE = "https://registry.npmjs.org/@pnpm/exe.linux-x64/-/exe.linux-x64-12.14.0.tgz"
PNPM_INTEGRITY = "F6K8e/jWxiuEYJaQtRRUG9ynBSTEHa+t7Lf86MKuOO5UA7WVVMbi+oB8nY6iKW++ncWS2yG6T9faXZGxqNsfoQ=="


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            h.update(data)
    return "sha256:" + h.hexdigest()


def excluded(path):
    return any(p.startswith(".env") or p in [".npmrc", ".ssh", ".aws", ".git"]
               for p in Path(path).parts)


def acquire_source(run, work, evidence, upstream=UPSTREAM, revision=REVISION):
    owner = work / "source"
    run("git-init", ["git", "init", owner])
    run("git-origin", ["git", "remote", "add", "origin", upstream], cwd=owner)
    for key, value in [("remote.origin.promisor", "true"),
                       ("remote.origin.partialclonefilter", "blob:none"), ("core.hooksPath", "/dev/null")]:
        run("git-config-" + key.replace(".", "-"), ["git", "config", key, value], cwd=owner)
    run("git-fetch-tree", ["git", "-c", "protocol.version=2", "fetch", "--filter=blob:none",
                          "--depth=1", "origin", revision], cwd=owner)
    tree = run("git-source-tree", ["git", "ls-tree", "-rz", "--full-tree", revision], cwd=owner)
    entries = []
    for raw in tree.split(b"\0"):
        if not raw:
            continue
        fields, name = raw.split(b"\t", 1)
        mode, kind, oid = fields.decode().split()
        name = name.decode()
        assert kind == "blob" and mode in ["100644", "100755", "120000"]
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        assert not any(ord(c) < 32 or c == "\\" for c in name)
        entries.append({"path": name, "mode": mode, "gitBlob": oid})
    selected, omitted = [[e for e in entries if excluded(e["path"]) == value] for value in [False, True]]
    assert selected and len(selected) <= 16384
    assert any(e["path"] == "apps/docs/.env" for e in omitted)
    safe_oids = {e["gitBlob"] for e in selected}
    excluded_only_oids = {e["gitBlob"] for e in omitted} - safe_oids

    def audit(label, repo=owner):
        objects = run(label, ["git", "cat-file", "--batch-all-objects",
                             "--batch-check=%(objectname) %(objecttype)"], cwd=repo)
        local = {line.split()[0].decode() for line in objects.splitlines()}
        assert not local & excluded_only_oids, "Excluded unique blob unexpectedly fetched"
        assert all(not os.path.lexists(repo / e["path"]) for e in omitted)

    audit("excluded-blobs-before-checkout")
    run("git-head", ["git", "update-ref", "HEAD", revision], cwd=owner)
    run("git-read-index", ["git", "read-tree", revision], cwd=owner)
    run("git-skip-secret-paths", ["git", "update-index", "--skip-worktree", "-z", "--stdin"],
        cwd=owner, data=b"".join(e["path"].encode() + b"\0" for e in omitted))
    # Explicit blob wants backfill only allowed inputs; do not fetch whole source archives.
    run("git-fetch-selected-blobs", ["git", "-c", "fetch.negotiationAlgorithm=noop", "fetch", "--no-tags", "--no-write-fetch-head",
        "--recurse-submodules=no", "--filter=blob:none", "origin", "--stdin"], cwd=owner,
        data="".join(oid + "\n" for oid in sorted(safe_oids)).encode())
    audit("excluded-blobs-after-backfill")
    run("git-materialize-selected", ["git", "checkout-index", "--all", "--index"], cwd=owner)
    audit("excluded-blobs-after-checkout")
    inventory = []
    for entry in selected:
        path = owner / entry["path"]
        if path.is_symlink():
            data = os.readlink(path).encode()
            path.resolve(strict=True).relative_to(owner.resolve())
        else:
            assert path.is_file() and path.stat().st_size <= 128 * 1024 * 1024
            data = path.read_bytes()
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == entry["gitBlob"]
        inventory.append({**entry, "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                          "bytes": len(data), "symlink": path.is_symlink()})
    assert sum(e["bytes"] for e in inventory) <= 128 * 1024 * 1024
    (evidence / "selected-source.json").write_text(json.dumps(inventory, indent=2) + "\n")
    assert not run("source-status-before", ["git", "status", "--porcelain=v1"], cwd=owner)
    return owner, selected, omitted, inventory, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--next-build", action="store_true", help="Run owner pre-build and Next production build in a separate source copy; skip post-build")
    args = parser.parse_args()
    work, evidence = args.work.resolve(), args.evidence.resolve()
    assert not work.exists() and not evidence.exists(), "Use fresh retained paths"
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    node, cli = work / "tools/node", args.cli.resolve(strict=True)
    for name in ["home", "tmp", "tools", "store"]:
        (work / name).mkdir()
    env = {"PATH": str(node.parent) + ":/usr/bin:/bin", "HOME": str(work / "home"),
           "TMPDIR": str(work / "tmp"), "XDG_CONFIG_HOME": str(work / "home/config"),
           "CI": "true", "LANG": "C.UTF-8", "TZ": "UTC", "FORCE_COLOR": "0",
           "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_SYSTEM": "/dev/null", "NEXT_TELEMETRY_DISABLED": "1",
           "NODE_OPTIONS": "--max-old-space-size=2048",
           "npm_config_userconfig": "/dev/null", "npm_config_globalconfig": "/dev/null"}
    def interrupted(signum, frame):
        raise KeyboardInterrupt("Qualification interrupted; owned command groups are stopped and records retained")
    for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
        signal.signal(sig, interrupted)
    baseline_free = os.statvfs(work).f_bavail * os.statvfs(work).f_frsize
    maximum_growth = 4_000_000_000
    report = {"status": "failed", "sourceCommit": REVISION, "upstream": UPSTREAM,
              "commands": [], "frameworkBuildEstablished": False, "runtimeEstablished": False,
              "dependencyClosureEstablished": False, "applicationAcceptance": False,
              "nextBuildExecuted": False, "preBuildExecuted": False, "postBuildExecuted": False,
              "filesDeleted": 0, "maximumWorkflowGrowthBytes": maximum_growth}

    def capacity():
        free = os.statvfs(work).f_bavail * os.statvfs(work).f_frsize
        assert free >= 500_000_000, "CI free-space reserve"
        assert baseline_free - free <= maximum_growth, "CI preparation growth budget exceeded"
        return free

    def run(label, argv, cwd=None, data=None, timeout=1200):
        capacity()
        began = time.monotonic()
        outpath, errpath = [evidence / (label + suffix) for suffix in [".stdout.log", ".stderr.log"]]
        with outpath.open("xb") as out, errpath.open("xb") as err:
            child = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env,
                                     stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                                     stdout=out, stderr=err, start_new_session=True)
            try:
                if data is not None:
                    child.stdin.write(data)
                    child.stdin.close()
                while child.poll() is None:
                    capacity()
                    assert time.monotonic() - began <= timeout, (label, "deadline")
                    assert outpath.stat().st_size <= 16 * 1024 * 1024 and errpath.stat().st_size <= 16 * 1024 * 1024, (label, "log bound")
                    time.sleep(1)
                assert child.returncode == 0, (label, child.returncode)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=10)
                report["commands"].append({"label": label, "argv": [str(a) for a in argv],
                    "exitCode": child.returncode, "seconds": round(time.monotonic() - began, 3),
                    "stdoutDigest": sha(outpath), "stderrDigest": sha(errpath)})
        return outpath.read_bytes()

    def download(url, path, maximum):
        with urllib.request.urlopen(url, timeout=60) as source, path.open("xb") as target:
            total = 0
            while True:
                data = source.read(1024 * 1024)
                if not data:
                    break
                total += len(data)
                assert total <= maximum
                target.write(data)
                capacity()
        return path

    try:
        assert platform.system() == "Linux" and platform.machine() == "x86_64"
        release = download(NODE_ARCHIVE, work / "node-release.tar.xz", 64 * 1024 * 1024)
        assert sha(release) == "sha256:" + NODE_ARCHIVE_SHA
        with tarfile.open(release, "r:xz") as archive:
            member = archive.getmember("node-v24.21.0-linux-x64/bin/node")
            assert member.isfile() and member.size <= 256 * 1024 * 1024
            with archive.extractfile(member) as source, node.open("xb") as target:
                h = hashlib.sha256()
                for data in iter(lambda: source.read(1024 * 1024), b""):
                    h.update(data)
                    target.write(data)
            node.chmod(0o755)
            assert sha(node) == "sha256:" + h.hexdigest()
        assert run("node-version", [node, "--version"]).decode().strip() == "v24.21.0"
        pnpm_archive = download(PNPM_ARCHIVE, work / "pnpm-12.14.0.tgz", 32 * 1024 * 1024)
        assert base64.b64encode(hashlib.sha512(pnpm_archive.read_bytes()).digest()).decode() == PNPM_INTEGRITY
        with tarfile.open(pnpm_archive, "r:gz") as archive:
            entries = archive.getmembers()
            assert len(entries) <= 8192 and sum(m.size for m in entries) <= 128 * 1024 * 1024
            assert all(not Path(m.name).is_absolute() and ".." not in Path(m.name).parts
                       and (m.isfile() or m.isdir()) for m in entries)
            archive.extractall(work / "tools", filter="data")
        pnpm_binary = work / "tools/package/pnpm"
        with pnpm_binary.open("rb") as source:
            header = source.read(64)
        assert len(header) == 64 and header[:6] == b"\x7fELF\x02\x01" and int.from_bytes(header[18:20], "little") == 62
        pnpm = [pnpm_binary]
        env["PATH"] = str(node.parent) + ":" + str(pnpm_binary.parent) + ":/usr/bin:/bin"
        assert run("pnpm-version", [*pnpm, "--version"]).decode().strip() == "12.14.0"
        report["tools"] = {"nodeVersion": "24.21.0", "nodeDigest": sha(node),
                           "nodeDistributionDigest": sha(release), "pnpmVersion": "12.14.0",
                           "pnpmTarballDigest": sha(pnpm_archive), "pnpmIntegrityVerified": True,
                           "pnpmExecutableDigest": sha(pnpm_binary), "pnpmImplementation": "official Linux x64 native package",
                           "compilerDigest": sha(cli)}

        owner, selected, omitted, inventory, audit = acquire_source(run, work, evidence)
        build_owner = owner
        if args.next_build:
            capacity()
            build_owner = work / "build-candidate"
            shutil.copytree(owner, build_owner, symlinks=True)
            for entry in inventory:
                path = build_owner / entry["path"]
                if entry["symlink"]:
                    assert path.is_symlink()
                    copied = os.readlink(path).encode()
                else:
                    assert path.is_file()
                    copied = path.read_bytes()
                assert hashlib.sha256(copied).hexdigest() == entry["digest"].removeprefix("sha256:")
            audit("excluded-blobs-after-build-copy", build_owner)
            capacity()
        package = json.loads((build_owner / "package.json").read_text())
        app = json.loads((build_owner / "apps/docs/package.json").read_text())
        assert package["packageManager"] == "pnpm@12.14.0" and app["dependencies"]["next"] == "16.4.2"
        assert package["engines"]["node"] == ">= 24.14.0"
        # No unreviewed package-manager hook executes during dependency preparation.
        assert not any((build_owner / p).exists() for p in [".pnpmfile.cjs", ".pnpmfile.mjs", "pnpmfile.cjs"])
        selection = {"profile": "patamaps-project-context-selection-1",
                     "id": "urn:qualification:fumadocs:source", "nonsecretInputs": True,
                     "paths": [e["path"] for e in selected], "symlinks": "internal-closed"}
        (evidence / "context-selection.json").write_text(json.dumps(selection, indent=2) + "\n")
        capture = json.loads(run("native-source-capture", [cli, "project-context-capture",
                             evidence / "context-selection.json", "--root", owner,
                             "--destination", work / "source-context"]))
        run("native-source-verify", [cli, "project-context-verify", work / "source-context"])
        run("native-source-stage", [cli, "project-context-stage", work / "source-context",
                                   "--destination", work / "restaged-source"])
        assert all(not os.path.lexists(work / "restaged-source" / e["path"]) for e in omitted)
        help_text = run("pnpm-install-help", [*pnpm, "help", "install"], cwd=build_owner).decode()
        assert "--frozen-lockfile" in help_text and "--ignore-scripts" in help_text
        # Include the owner's root tooling and the docs workspace dependency closure, not other applications.
        filters = ["--filter", "root", "--filter", "docs..."]
        packages = json.loads(run("declared-workspace-closure", [*pnpm, *filters, "list",
                                 "--recursive", "--depth", "-1", "--json"], cwd=build_owner))
        names = sorted(p["name"] for p in packages)
        assert all(name in names for name in ["root", "docs", "fumadocs-core", "fumadocs-mdx", "@fumadocs/story"])
        run("frozen-dependency-preparation", [*pnpm, *filters, "install", "--frozen-lockfile",
            "--ignore-scripts", "--store-dir", work / "store", "--network-concurrency=4",
            "--child-concurrency=1"], cwd=build_owner)
        installed = json.loads(run("installed-package-versions", [node, "-e",
            "const fs=require('node:fs');const p=require.resolve('next/package.json',{paths:[process.cwd()+'/apps/docs']});"
            "const t=require.resolve('turbo/package.json');console.log(JSON.stringify({next:JSON.parse(fs.readFileSync(p)).version,turboPath:t,turbo:JSON.parse(fs.readFileSync(t)).version}))"], cwd=build_owner))
        assert installed["next"] == "16.4.2"
        turbo = Path(installed["turboPath"]).parent
        docs = turbo / "docs"
        assert (docs / "README.md").is_file(), "Required installed Turbo documentation is unavailable"
        documentation = []
        target_docs = evidence / "turbo-docs"
        target_docs.mkdir()
        for path in [docs / "README.md", *sorted(p for p in docs.rglob("*") if p.is_file() and
                     any(key in p.name.lower() for key in ["filter", "running-tasks"]))[:8]]:
            data = path.read_bytes()
            assert len(data) <= 1024 * 1024
            destination = target_docs / path.relative_to(docs)
            destination.parent.mkdir(exist_ok=True, parents=True)
            destination.write_bytes(data)
            documentation.append({"path": path.relative_to(docs).as_posix(), "digest": sha(path), "bytes": len(data)})
        next_build = None
        if args.next_build:
            run("fumadocs-pre-build", [*pnpm, "--filter", "docs", "run", "build:pre"],
                cwd=build_owner, timeout=600)
            report["preBuildExecuted"] = True
            run("fumadocs-next-production-build", [*pnpm, "--filter", "docs", "exec", "next", "build"],
                cwd=build_owner, timeout=1200)
            report["nextBuildExecuted"] = True
            report["frameworkBuildEstablished"] = True
            output = build_owner / "apps/docs/.next"
            build_id = output / "BUILD_ID"
            app_paths = output / "server/app-paths-manifest.json"
            assert build_id.is_file() and app_paths.is_file(), "Next build outputs missing"
            manifest = json.loads(app_paths.read_text())
            next_build = {"buildIdDigest": sha(build_id), "buildIdBytes": build_id.stat().st_size,
                          "appPathCount": len(manifest), "appPathsManifestDigest": sha(app_paths)}
            (evidence / "next-build.json").write_text(json.dumps(next_build, indent=2) + "\n")
            audit("excluded-blobs-after-next-build", build_owner)
        assert all(sha(owner / e["path"]) == e["digest"] for e in inventory if not e["symlink"])
        assert not run("source-status-after", ["git", "status", "--porcelain=v1"], cwd=owner)
        audit("excluded-blobs-after-install", build_owner)
        report.update(status=("passed-pinned-fumadocs-next-production-build"
                              if args.next_build else "prepared-pinned-fumadocs-source-and-dependencies-not-built"),
            sourcePaths=len(selected), sourceBytes=sum(e["bytes"] for e in inventory),
            sourceInventoryDigest=sha(evidence / "selected-source.json"),
            omittedReservedPaths=[e["path"] for e in omitted],
            excludedUniqueBlobsAbsent=True, excludedPathsNeverMaterialized=True,
            sharedAllowedBlobIds=len({e["gitBlob"] for e in omitted} & {e["gitBlob"] for e in selected}),
            sourceContextDigest=capture["digest"], nativeSourceCaptureVerifiedAndStaged=True,
            originalSelectedSourceUnchanged=True, workspacePackages=names,
            installedNextVersion=installed["next"], installedTurboVersion=installed["turbo"],
            reviewedInstalledTurboDocs=documentation, dependencyLifecycleScriptsExecuted=False,
            nextBuildExecuted=report["nextBuildExecuted"], preBuildExecuted=report["preBuildExecuted"],
            postBuildExecuted=report["postBuildExecuted"],
            githubDiscussionPosted=False, oramaIndexUpdated=False, nextBuild=next_build,
            availableBytesAfter=capacity(), workflowFreeSpaceDeltaBytes=baseline_free-capacity(),
            limitations=(["Next production build passed; runtime/HTTP/browser/ServerAction boundaries unrun."
                          if args.next_build else "Preparation only; actual Next build/runtime/HTTP/browser/ServerAction boundaries unrun.",
                         "Only explicit nonsecret source is natively captured; installed dependency closure is not qualified.",
                         "No source-context backup/restoration archive, package release or performance claim."]))
    except BaseException as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        (evidence / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "error": report.get("error")}), flush=True)


if __name__ == "__main__":
    main()
