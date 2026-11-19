"""Review a retained, guarded owner API import observation; never claim browser acceptance."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import subprocess

CHILD = "0add0932ba05c111c9e9a96e307701270410fc6f00598ac21f37a5f1e78cb0ce"
PARENT = "2a83a7c2561473245fe815cf4bb9d2260e98b708383c218117a8e75ce45baffb"
PROFILES = [
    "4be4ef5f3dad95fc6092c78f82f37b69da0804383b566a25da30ad2d79800654",
    "c6f46fa5ec2ab296bb016b85b0afce7463f63f28cee307209176e9b2a1208e93",
    "ff48ffb6123348aa7c398970f5269df56ce49e928a91e87eee107fd031d5825e",
]
MODULES = [
    "bcrypt", "pydantic_core", "fastapi", "uvicorn", "sqlalchemy", "psycopg2",
    "asyncpg", "pydantic_settings", "jose", "passlib.context", "httpx", "redis",
    "greenlet", "alembic", "email_validator",
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def absent(pid):
    p = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "pid="],
        capture_output=True, text=True, timeout=5,
    )
    return p.returncode == 1 and not p.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--buildctl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "review output already exists")
    phase = args.phase.resolve()
    stages = [phase, phase / "repair1", phase / "repair2"]
    configs = [read(p / "frozen.json") for p in stages]
    baseline = configs[0]
    owner = Path(baseline["owner"])
    require(baseline["ownerCommit"] == "c61d51a57120abbbca65d4cb4a432c1cef9343bb", "owner revision")
    require(len(baseline["sourceInputs"]) == 387, "source binding count")
    require(len({x["path"] for x in baseline["sourceInputs"]}) == 387, "duplicate source binding")
    for entry in baseline["sourceInputs"]:
        path = (owner / entry["path"]).resolve()
        require(path.is_relative_to(owner), "source path escaped owner")
        require(digest(path) == entry["sha256"], "owner source input changed")
    for command, expected in [
        (["git", "rev-parse", "HEAD"], baseline["ownerCommit"]),
        (["git", "status", "--porcelain"], ""),
    ]:
        result = subprocess.run(command, cwd=owner, capture_output=True, text=True, check=True)
        require(result.stdout.strip() == expected, "owner checkout changed")
    status = json.loads(subprocess.check_output(
        [str(args.node), str(args.buildctl), "status"], text=True, timeout=15,
    ))
    require(status["parallelActivated"] is False, "unexpected parallel activation")
    require(status["legacyLease"] is None and status["transactionBlocked"] is False, "lease not finalized")
    requests = {r["id"]: r for r in status["requests"]}
    observations = []
    private_receipts = []
    for index, (directory, config) in enumerate(zip(stages, configs)):
        require(config["sourceInputs"] == baseline["sourceInputs"], "source bindings changed between attempts")
        require(config["bounds"] == baseline["bounds"], "preflight bounds changed")
        require(config["ownerCommit"] == baseline["ownerCommit"], "revision changed between attempts")
        expected = {"child.py": CHILD, "preflight.py": PARENT, "sandbox.sb": PROFILES[index]}
        require({e["path"]: e["sha256"] for e in config["runnerInputs"]} == expected, "unexpected runner inputs")
        for name, sha in expected.items():
            require(digest(directory / name) == sha, "runner bytes changed")
        receipt = read(directory / "receipt.json")
        private_receipts.append(receipt)
        code = receipt["childExitCode"]
        require(read(directory / "supervisor-exit.json")["exitCode"] == code, "terminal exit mismatch")
        require(receipt["sourceBindingRechecked"] is True and receipt["sourceInputCount"] == 387, "post-source binding missing")
        require(receipt["packagesInstalled"] == 0 and receipt["servicesStarted"] == 0, "unexpected service/install claim")
        require(receipt["networkAllowed"] is False and receipt["originalOwnerBrowserAccepted"] is False, "scope mismatch")
        for name in ["stdout", "stderr"]:
            require(digest(directory / "run" / name) == receipt[name]["sha256"], "raw log digest mismatch")
            require((directory / "run" / name).stat().st_size == receipt[name]["bytes"], "raw log size mismatch")
        stdout = (directory / "supervisor.stdout").read_text()
        match = re.search(r"^Storage guard record: (.+)$", stdout, re.M)
        require(match is not None, "guard record missing")
        guard_path = Path(match.group(1))
        require(guard_path.name == "run.json" and guard_path.parent.parent.name == "runs", "unexpected guard path")
        guard = read(guard_path)
        require(guard["exitCode"] == code and guard["filesDeleted"] == 0, "guard exit/deletion mismatch")
        require(not guard.get("newSurvivingContainers") and not guard.get("existingContainerUncertainty"), "container uncertainty")
        reservation = re.search(r"Build reservation queued: ([0-9a-f-]{36});", (directory / "supervisor.stderr").read_text())
        require(reservation is not None, "reservation missing")
        reservation_id = reservation.group(1)
        request = requests[reservation_id]
        require(request["state"] == "finished" and request["leaseReleaseCompleted"] is True, "reservation not released")
        require(request["enforcement"] == "native-exclusive" and request["exclusive"] is True, "exclusive fallback changed")
        require(request["limits"]["diskBytes"] == 4_000_000_000, "disk reservation changed")
        for name in ["launch.json", "supervisor.json", "run/process.json"]:
            path = directory / name
            if path.exists():
                require(absent(read(path)["pid"]), "owned process still present")
        observations.append({
            "attempt": index, "exitCode": code, "reservationId": reservation_id,
            "reservationFinishedAndReleased": True,
            "privateReceiptDigest": "sha256:" + digest(directory / "receipt.json"),
            "guardRecordDigest": "sha256:" + digest(guard_path),
            "sandboxProfileDigest": "sha256:" + PROFILES[index],
        })
    require(private_receipts[0]["childExitCode"] == 65 and private_receipts[0]["childReport"] is None, "initial failure changed")
    require("unterminated bracket expression" in (stages[0] / "run/stderr").read_text(), "initial cause changed")
    require(private_receipts[1]["childExitCode"] == 1 and private_receipts[1]["childReport"] is None, "launcher failure changed")
    require("posix_spawn" in (stages[1] / "run/stderr").read_text(), "launcher cause changed")
    for executable in configs[2]["interpreterExecutables"]:
        require(digest(Path(executable["path"])) == executable["sha256"], "interpreter executable changed")
    actual = private_receipts[-1]
    child = actual["childReport"]
    controls = None
    imports = []
    application = None
    if child is not None:
        require(read(stages[-1] / "run/child-report.json") == child, "child report mismatch")
        controls = child["sandboxControls"]
        require(set(controls) == {"networkDenied", "outsideWriteDenied", "dotenvReadDenied"}, "unexpected security controls")
        if child["imports"]:
            require(all(controls.values()), "imports preceded security controls")
            require([i["module"] for i in child["imports"]] == MODULES, "import targets changed")
            for item in child["imports"]:
                require(item["status"] in ["passed", "failed"], "invalid import outcome")
                safe = {"module": item["module"], "status": item["status"]}
                if item["status"] == "failed":
                    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", item["exceptionType"]) is not None, "invalid error class")
                    safe["exceptionType"] = item["exceptionType"]
                imports.append(safe)
        if child["application"] is not None:
            source = child["application"]
            application = {"status": source["status"]}
            if source["status"] == "failed":
                require(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", source["exceptionType"]) is not None, "invalid application error")
                application["exceptionType"] = source["exceptionType"]
            else:
                require(source["status"] == "passed", "invalid application outcome")
                for key in ["routeCount", "authLoginPresent", "authMePresent", "permissionsPresent"]:
                    application[key] = source[key]
    imported = bool(controls and all(controls.values()) and len(imports) == 15
                    and all(i["status"] == "passed" for i in imports)
                    and application and application["status"] == "passed"
                    and all(application[k] is True for k in ["authLoginPresent", "authMePresent", "permissionsPresent"]))
    output = {
        "schemaVersion": 1, "status": "verified-import-only-observation",
        "observedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ownerCommit": baseline["ownerCommit"], "sourceInputsRehashed": 387,
        "sourceBindingManifestDigest": "sha256:" + hashlib.sha256(json.dumps(baseline["sourceInputs"], sort_keys=True).encode()).hexdigest(),
        "pythonDriverDigest": "sha256:" + PARENT, "pythonProbeDigest": "sha256:" + CHILD,
        "attempts": observations, "sandboxControls": controls, "imports": imports,
        "applicationImport": application, "apiImportReadinessAccepted": imported,
        "packagesInstalled": 0, "servicesStarted": 0, "filesDeleted": 0,
        "apiStartupAccepted": False, "databaseAuthenticationAccepted": False,
        "originalOwnerBrowserAccepted": False, "installedBrowserWorkflowAccepted": False,
        "deploymentAccepted": False, "performanceAccepted": False, "completeGoalAccepted": False,
        "parallelActivated": False, "reviewerDigest": "sha256:" + digest(Path(__file__)),
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": output["status"], "apiImportReadinessAccepted": imported,
                      "libraryImportsAttempted": len(imports), "terminalExitCode": actual["childExitCode"]}))


if __name__ == "__main__":
    main()
