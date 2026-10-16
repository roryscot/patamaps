"""Retained cross-stack fixture checks; no cleanup or implicit acceptance of later lanes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/cross-stack"
sys.path.insert(0, str(ROOT / "scripts/parity"))
from storage_guard import ensure_guarded


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["transport-http", "json-http", "bootstrap", "fixture", "discovery", "regression", "bindings", "docker", "workspace", "workspace-smoke", "development", "compatibility", "installed"], required=True)
    args = parser.parse_args()
    ensure_guarded()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = ROOT / ".tools/cross-stack" / (args.phase + "-" + stamp)
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, CARGO_INCREMENTAL="0", CARGO_PROFILE_DEV_DEBUG="0",
               CARGO_PROFILE_TEST_DEBUG="0", NEXT_TELEMETRY_DISABLED="1",
               CARGO_TARGET_DIR=str(ROOT / ".tools/cross-stack/target-service"),
               npm_config_cache=str(ROOT / ".tools/cross-stack/npm-cache"),
               npm_config_logs_max="1000000", NODE_OPTIONS="--max-old-space-size=2048")
    if args.phase in {"discovery", "regression", "bindings", "docker", "workspace", "workspace-smoke", "development", "compatibility", "installed"}:
        env["CARGO_TARGET_DIR"] = str(ROOT / "target")
        # Reuse the already compiled Intel test profile without discarding it.
        env.pop("CARGO_PROFILE_DEV_DEBUG", None)
        env.pop("CARGO_PROFILE_TEST_DEBUG", None)
    if args.phase in {"json-http", "transport-http"}:
        env["CARGO_TARGET_DIR"] = str(ROOT / "target")
    receipt = {"status": "running", "phase": args.phase, "profile": "patamaps-cross-stack-fixture-1",
               "startedUtc": datetime.now(timezone.utc).isoformat(), "commands": [],
               "retainedWork": work.relative_to(ROOT).as_posix(), "filesDeleted": [],
               "fullCrossStackAcceptance": False, "containerAcceptance": "not-run",
               "browserAcceptance": "not-run", "generatedRegistration": "not-evaluated-by-this-phase"}
    receipt_path = work / "receipt.json"

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    def run(label, argv, cwd=ROOT, timeout=300, input_bytes=None, expected_success=True):
        save()
        command = {"label": label, "argv": [str(v) for v in argv],
                   "cwd": Path(cwd).relative_to(ROOT).as_posix(), "expectedSuccess": expected_success}
        if input_bytes is not None:
            target = work / (label + ".stdin.json")
            with target.open("xb") as out:
                out.write(input_bytes)
            command["stdin"] = {"path": target.relative_to(ROOT).as_posix(), "digest": digest(input_bytes)}
        began = time.monotonic()
        with (work / (label + ".stdout.log")).open("xb") as out, (work / (label + ".stderr.log")).open("xb") as err:
            result = subprocess.run(command["argv"], cwd=cwd, env=env, stdout=out, stderr=err, timeout=timeout, input=input_bytes)
        command.update(exitCode=result.returncode, seconds=round(time.monotonic()-began, 3))
        for stream in ["stdout", "stderr"]:
            p = work / (label + "." + stream + ".log")
            command[stream] = {"path": p.relative_to(ROOT).as_posix(), "digest": digest(p.read_bytes())}
        receipt["commands"].append(command)
        save()
        print(json.dumps({"check": label, "exitCode": result.returncode, "seconds": command["seconds"]}), flush=True)
        if (result.returncode == 0) != expected_success:
            raise RuntimeError(label + " failed; retained logs in " + str(work))
        return (work / (label + ".stdout.log")).read_bytes()

    source = [p for p in FIXTURE.rglob("*") if p.is_file() and not any(
        v in {"node_modules", ".next", "target", "runs"} for v in p.relative_to(FIXTURE).parts)
        and p.name not in {"next-env.d.ts", "tsconfig.tsbuildinfo"}]
    before = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(source)}
    receipt["sourceInventory"] = before
    try:
        service = FIXTURE / "service/Cargo.toml"
        web = FIXTURE / "web"
        run("rust-version", ["rustc", "-Vv"])
        run("cargo-version", ["cargo", "--version"])
        run("node-version", ["node", "--version"])
        if args.phase == "bootstrap":
            assert not (service.parent / "Cargo.lock").exists(), "Refusing to replace an existing lock"
            assert not (web / "package-lock.json").exists(), "Refusing to replace an existing lock"
            assert not (web / "node_modules").exists(), "Refusing npm ci over retained dependencies"
            run("cargo-lock", ["cargo", "generate-lockfile", "--manifest-path", service])
            run("npm-lock", ["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=web)
            run("npm-native-install", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=web)
            run("cargo-fetch", ["cargo", "fetch", "--locked", "--manifest-path", service])
        elif args.phase == "regression":
            run("workspace-format", ["cargo", "fmt", "--all", "--", "--check"])
            run("workspace-clippy", ["cargo", "clippy", "--workspace", "--all-targets", "--locked", "--offline", "--", "-D", "warnings"])
            run("workspace-tests", ["cargo", "test", "--workspace", "--locked", "--offline"], timeout=600)
            run("workspace-doctests", ["cargo", "test", "--workspace", "--doc", "--locked", "--offline"])
            receipt["scope"] = "Native workspace lint, unit/integration and documentation regression gates; no cross-stack release acceptance"
        elif args.phase == "transport-http":
            run("transport-format", ["cargo", "fmt", "--all", "--", "--check"])
            run("transport-projection-tests", ["cargo", "test", "-p", "patamaps-projection", "--locked", "--offline"])
            profile=env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE", "debug")
            assert profile in {"debug", "release"}
            run("transport-cli", ["cargo", "build", "-p", "patamaps-cli", "--locked", "--offline", *(["--release"] if profile=="release" else [])], timeout=900)
            from project_http_transport import verify
            receipt["httpTransport"] = verify(ROOT, work, env, run)
        elif args.phase == "json-http":
            run("json-http-format", ["cargo", "fmt", "--all", "--", "--check"])
            run("json-http-projection-tests", ["cargo", "test", "-p", "patamaps-projection", "--locked", "--offline"])
            profile = env.get("PATAMAPS_CROSS_STACK_COMPILER_PROFILE", "debug")
            assert profile in {"debug", "release"}
            run("json-http-cli", ["cargo", "build", "-p", "patamaps-cli", "--locked", "--offline", *(["--release"] if profile == "release" else [])], timeout=900)
            from project_http_json import verify
            receipt["jsonHttpContracts"] = verify(ROOT, work, env, run)
            assert all(digest((ROOT / path).read_bytes()) == old for path,old in before.items())
            receipt["sourceUnchanged"] = True
        elif args.phase == "installed":
            from cross_stack_package import verify
            receipt["installedConsumer"] = verify(ROOT, work, env, run)
        elif args.phase == "compatibility":
            from cross_stack_compatibility import verify
            receipt["metamapCompatibility"] = verify(ROOT, work, env, run)
        elif args.phase == "development":
            from cross_stack_development import verify
            receipt["developmentPreview"] = verify(ROOT, work, env, run)
        elif args.phase in {"workspace", "workspace-smoke"}:
            from cross_stack_workspace import verify
            receipt["workspaceChecks"] = verify(ROOT, work, env, run, smoke=args.phase == "workspace-smoke")
            for path, old in before.items():
                assert digest((ROOT / path).read_bytes()) == old, "Fixture input changed: " + path
            receipt["sourceUnchanged"] = True
        elif args.phase == "docker":
            from cross_stack_docker import verify
            receipt["dockerObservationChecks"] = verify(ROOT, work, env, run)
            for path, old in before.items():
                assert digest((ROOT / path).read_bytes()) == old, "Fixture input changed: " + path
            receipt["sourceUnchanged"] = True
        elif args.phase == "bindings":
            from cross_stack_bindings import verify
            receipt["bindingChecks"] = verify(ROOT, work, env, run)
            receipt["generatedRegistration"] = "verified-for-declared-M2-scope"
            for path, old in before.items():
                assert digest((ROOT / path).read_bytes()) == old, "Fixture input changed: " + path
            receipt["sourceUnchanged"] = True
        elif args.phase == "discovery":
            from cross_stack_discovery import verify
            receipt["discoveryChecks"] = verify(ROOT, work, env, run)
            for path, old in before.items():
                assert digest((ROOT / path).read_bytes()) == old, "Fixture input changed: " + path
            receipt["sourceUnchanged"] = True
        else:
            run("rust-format", ["cargo", "fmt", "--manifest-path", service, "--", "--check"])
            run("rust-tests", ["cargo", "test", "--manifest-path", service, "--locked", "--offline"])
            run("rust-build", ["cargo", "build", "--manifest-path", service, "--locked", "--offline"])
            run("next-build", ["npm", "run", "build"], cwd=web)
            run("next-typecheck", ["npm", "run", "typecheck"], cwd=web)
            expected = json.loads((FIXTURE / "acceptance/expected.json").read_bytes())
            executable = Path(env["CARGO_TARGET_DIR"]) / "debug/catalog-service"
            config = FIXTURE / "config/service.toml"
            out = (work / "service.stdout.log").open("xb")
            err = (work / "service.stderr.log").open("xb")
            process = subprocess.Popen([str(executable), str(config), "127.0.0.1:0"], cwd=ROOT, env=env, stdout=out, stderr=err)
            try:
                deadline = time.monotonic() + 15
                address = None
                while time.monotonic() < deadline:
                    lines = (work / "service.stdout.log").read_text().splitlines()
                    address = next((v.removeprefix("LISTEN ") for v in lines if v.startswith("LISTEN ")), None)
                    if address:
                        break
                    if process.poll() is not None:
                        raise RuntimeError("Service exited before listening")
                    time.sleep(0.05)
                assert address and address.startswith("127.0.0.1:")
                base = "http://" + address
                observed = []
                cases = [("health", "GET", "/health", None, 200, expected["health"]["body"]),
                         ("create", "POST", "/items", expected["request"], 201, expected["response"]),
                         ("malformed", "POST", "/items", {"name": 4}, 400, {"error": "invalid-request"}),
                         ("extra-field", "POST", "/items", {"name": "ok", "unexpected": True}, 400, {"error": "invalid-request"}),
                         ("empty-name", "POST", "/items", {"name": ""}, 400, {"error": "invalid-request"}),
                         ("backend-failure", "POST", "/items", expected["backendFailureRequest"], 500, {"error": "backend-failure"})]
                for label, method, path, value, status, body in cases:
                    request = Request(base + path, data=None if value is None else json.dumps(value).encode(),
                                      headers={"content-type": "application/json"}, method=method)
                    try:
                        response = urlopen(request, timeout=10)
                    except HTTPError as e:
                        response = e
                    with response:
                        got_status = response.status
                        got = json.loads(response.read())
                    observed.append({"case": label, "status": got_status, "body": got})
                    assert (got_status, got) == (status, body), observed[-1]
                receipt["httpChecks"] = observed
                receipt["effectiveListener"] = address
                receipt["runtimeConfiguration"] = {"path": config.relative_to(ROOT).as_posix(),
                    "digest": digest(config.read_bytes()), "testListenerOverride": "127.0.0.1:0"}
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                out.close()
                err.close()
            for path, old in before.items():
                assert digest((ROOT / path).read_bytes()) == old, "Fixture input changed: " + path
            receipt["sourceUnchanged"] = True
        receipt.update(status="passed", completedUtc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
        print(json.dumps({"status": receipt["status"], "receipt": receipt_path.relative_to(ROOT).as_posix()}), flush=True)


if __name__ == "__main__":
    main()
