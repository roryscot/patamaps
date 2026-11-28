"""Reproducible bounded SDK/CLI measurements; never a Rust speed claim.

Inputs, expected decisions, raw samples and per-child wait4 usage are retained.
Only the optional discovery measurement uses an explicitly selected Node binary.
"""
import argparse
import copy
import contextlib
import hashlib
import json
import os
import platform
import random
import shutil
import signal
import statistics
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261010
TRIALS = 7
LIMIT = 16 * 1024 * 1024
AS_OF = "2026-10-10T00:00:00Z"


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def distribution(values):
    values = sorted(values)
    return {"count": len(values), "minimum": values[0], "median": statistics.median(values),
            "maximum": values[-1], "p95NearestRank": values[-1]}


def rss_observation(raw, system=None):
    system = system or platform.system()
    if type(raw) is not int or raw < 0:
        raise ValueError("Invalid wait4 RSS value")
    if system not in {"Darwin", "Linux"}:
        raise ValueError("Unverified wait4 RSS unit")
    unit = "bytes" if system == "Darwin" else "KiB"
    return {"peakRssRaw": raw, "peakRssRawUnit": unit,
            "peakRssBytes": raw * (1 if unit == "bytes" else 1024)}


def measured(argv, cwd, env, stdin=None, deadline=180, *, retained=None,
             monitor=None, maximum_log_bytes=LIMIT, cleanup=None):
    """Measure this exact child; retained mode never removes files or publishes stderr."""
    if type(maximum_log_bytes) is not int or not 0 < maximum_log_bytes <= LIMIT:
        raise ValueError("Measurement log bound")
    if not 0 < deadline <= 3600:
        raise ValueError("Measurement deadline")
    if stdin is not None and (not isinstance(stdin, bytes) or len(stdin) > LIMIT):
        raise ValueError("Measurement stdin bound")
    rss_observation(0)
    with contextlib.ExitStack() as files:
        if retained is None:
            out, err, inp = [files.enter_context(tempfile.TemporaryFile()) for _ in range(3)]
            paths = None
            measurement_record = None
        else:
            stem = Path(retained)
            paths = {name: Path(str(stem) + "." + name) for name in ["stdout", "stderr", "stdin"]}
            out, err, inp = [files.enter_context(paths[name].open("xb+")) for name in ["stdout", "stderr", "stdin"]]
            for path in paths.values():
                path.chmod(0o600)
            measurement_path = Path(str(retained) + ".measurement.json")
            measurement_record = files.enter_context(measurement_path.open("x"))
            measurement_path.chmod(0o600)
        if stdin is not None:
            inp.write(stdin)
        inp.seek(0)
        start = time.perf_counter_ns()
        child, usage, reaped, failure = None, None, False, None
        try:
            child = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env,
                                     stdin=inp, stdout=out, stderr=err, start_new_session=True)
            while True:
                pid, status, observed = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    usage, reaped = observed, True
                    child.returncode = os.waitstatus_to_exitcode(status)
                if max(os.fstat(out.fileno()).st_size, os.fstat(err.fileno()).st_size) > maximum_log_bytes:
                    raise ValueError("Measurement log bound exceeded")
                if monitor is not None:
                    monitor()
                if reaped:
                    break
                if (time.perf_counter_ns() - start) / 1e9 > deadline:
                    raise TimeoutError("Own benchmark child exceeded deadline")
                time.sleep(0.002)
        except BaseException as error:
            failure = error
        finally:
            if child is not None and not reaped:
                if cleanup is not None:
                    # A parent-death guardian needs SIGTERM/grace to stop its
                    # separately grouped workload. Failed samples have unknown
                    # rusage when this existing cleanup helper owns reaping.
                    cleanup(child)
                    if child.returncode is None:
                        raise RuntimeError("Measurement cleanup did not reap its child")
                else:
                    from project_watch import signal_group
                    signal_group(child.pid, signal.SIGKILL)
                    _, status, usage = os.wait4(child.pid, 0)
                    child.returncode = os.waitstatus_to_exitcode(status)
            elapsed = time.perf_counter_ns() - start
            sizes = {name: os.fstat(handle.fileno()).st_size for name, handle in [("stdout", out), ("stderr", err)]}
            out.seek(0); err.seek(0)
            stdout = out.read(maximum_log_bytes + 1)
            stderr = err.read(maximum_log_bytes + 1)
            sample = {"argv": [str(a) for a in argv], "pid": child.pid if child else None, "exitCode": child.returncode if child else None,
                      "wallNanoseconds": elapsed, "userSeconds": usage.ru_utime if usage else None,
                      "systemSeconds": usage.ru_stime if usage else None,
                      **(rss_observation(usage.ru_maxrss) if usage else dict(peakRssRaw=None, peakRssRawUnit=rss_observation(0)["peakRssRawUnit"], peakRssBytes=None)),
                      "stdoutBytes": sizes["stdout"],
                      "stdoutDigest": digest(stdout) if sizes["stdout"] <= maximum_log_bytes else None}
            if paths is None:
                sample["stderr"] = stderr.decode("utf-8", errors="replace")
            else:
                sample.update(stderrBytes=sizes["stderr"],
                              stderrDigest=digest(stderr) if sizes["stderr"] <= maximum_log_bytes else None,
                              retainedOutputs={name: str(path) for name, path in paths.items()},
                              measurementStatus="failed" if failure else "completed",
                              failureType=type(failure).__name__ if failure else None,
                              rssScope="largest-reaped-process-high-water-mark-not-concurrent-job-sum")
                json.dump(sample, measurement_record, indent=2)
                measurement_record.write("\n")
        if failure is not None:
            raise failure
        return sample, stdout


def routing(n):
    rng = random.Random(SEED)
    entities, mappings = [], []
    for i in range(n):
        subject, target = f"urn:bench:command:{i}", f"urn:bench:handler:{i}"
        entities.extend([{"id": subject, "kind": "routing:command", "label": f"fixed-{rng.getrandbits(32)}"},
                         {"id": target, "kind": "routing:handler"}])
        mappings.append({"id": f"urn:bench:mapping:{i}", "relation": "routing:handled_by",
                         "sources": [subject], "targets": [target], "cardinality": "one-to-one",
                         "lossiness": "lossless", "provenance": {"status": "declared", "assertedBy": "benchmark-fixture"}})
    graph = {"schemaVersion": "0.1.0", "documentType": "graph", "id": "urn:bench:graph",
             "namespace": "benchmark", "revision": "1", "entities": entities, "mappings": mappings, "authorities": []}
    policy = {"schemaVersion": "0.1.0", "documentType": "policy", "id": "urn:bench:policy",
              "graph": {"id": graph["id"], "revision": "1"},
              "mappings": [{"select": {"relations": ["routing:handled_by"]}, "coverage": "total",
                            "determinism": "deterministic", "reversibility": "irreversible"}], "constraints": [], "evidence": []}
    spec = {"schemaVersion": "0.1.0", "documentType": "projection-spec", "id": "urn:bench:projection",
            "select": {"kinds": ["routing:command"]},
            "slots": [{"name": "handler", "relation": "routing:handled_by", "direction": "outgoing", "cardinality": "exactly-one"}]}
    return {"graph": graph, "packs": [json.loads((ROOT / "relation-packs/routing.json").read_text())],
            "policy": policy, "context": {}, "evaluatedAt": AS_OF, "projectionSpec": spec}


def case(name, inputs, status="viable", code=None, cost=None, queries=None, repair=None):
    return {"name": name, "inputs": inputs, "expectedStatus": status, "expectedCode": code,
            "expectedCost": cost, "projectionBatch": 32, "authorityQueries": queries or [], "repair": repair}


def footprint(cli, driver, output):
    cargo = Path.home() / ".cargo/bin/cargo"
    metadata = subprocess.run([cargo, "metadata", "--locked", "--offline", "--format-version", "1"],
                              cwd=ROOT, capture_output=True, check=True)
    packages = json.loads(metadata.stdout)["packages"]
    dependencies = []
    for package in packages:
        if package["source"] is None:
            continue
        manifest = Path(package["manifest_path"])
        archives = list((Path.home() / ".cargo/registry/cache").glob(f"*/{package['name']}-{package['version']}.crate"))
        source_bytes = sum(p.stat().st_size for p in manifest.parent.rglob("*") if p.is_file())
        dependencies.append({"name": package["name"], "version": package["version"], "license": package["license"],
                             "unpackedSourceBytes": source_bytes,
                             "cachedArchiveBytes": archives[0].stat().st_size if len(archives) == 1 else None})
    return {"cliBytes": cli.stat().st_size, "cliDigest": digest(cli.read_bytes()),
            "benchmarkDriverBytes": driver.stat().st_size, "benchmarkDriverDigest": digest(driver.read_bytes()),
            "cliSystemLibraries": subprocess.run(["/usr/bin/otool", "-L", str(cli)], capture_output=True, text=True, check=True).stdout,
            "cargoMetadataCommand": [str(cargo), "metadata", "--locked", "--offline", "--format-version", "1"],
            "cargoMetadataDigest": digest(metadata.stdout), "registryDependencyCount": len(dependencies),
            "dependencySourceBytes": sum(p["unpackedSourceBytes"] for p in dependencies),
            "dependencyCachedArchiveBytes": sum(p["cachedArchiveBytes"] or 0 for p in dependencies), "dependencies": dependencies,
            "sourceLock": digest((ROOT / "Cargo.lock").read_bytes()),
            "driverSourceLock": digest((ROOT / "examples/benchmark-native/Cargo.lock").read_bytes()),
            "driverSourceDigest": digest((ROOT / "examples/benchmark-native/src/main.rs").read_bytes()),
            "runtime": "Standalone CLI plus recorded system libraries; Node is only required by optional discovery. Rust/toolchain and registry sources are build dependencies, not consumer runtime.",
            "limits": "On-disk logical byte sizes, not allocated blocks; dependency sources include offline-build cache metadata. OS libraries, toolchain, user registry caches and build-object caches are not charged as CLI installation bytes."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for field in ["cli", "driver", "node", "reference", "output"]:
        setattr(args, field, getattr(args, field).resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "TMPDIR": tempfile.gettempdir()}
    engine = json.loads(subprocess.check_output([args.cli, "engine"], env=env))
    results, cli_results, startup, discovery = [], [], [], []
    inventory = []
    with tempfile.TemporaryDirectory(prefix="patamaps-phases-") as directory:
        work = Path(directory)
        for flag in ["--version", "engine"]:
            samples = []
            for _ in range(TRIALS):
                sample, stdout = measured([args.cli, flag], work, env)
                assert sample["exitCode"] == 0, sample
                if flag == "engine":
                    assert json.loads(stdout) == engine
                samples.append(sample)
            startup.append({"command": flag, "samples": samples,
                            "wallNanoseconds": distribution([s["wallNanoseconds"] for s in samples]),
                            "peakRssBytes": distribution([s["peakRssBytes"] for s in samples])})
        # Allocate and touch 64 MiB in a separate child as an RSS unit control.
        calibration = []
        for mib in [0, 64]:
            program = f"b=bytearray({mib}*1024*1024);b[::4096]=b'1'*len(b[::4096]);print(len(b))"
            sample, raw = measured([shutil.which("python3"), "-c", program], work, env)
            assert sample["exitCode"] == 0 and int(raw) == mib * 1024 * 1024
            calibration.append({"allocatedMiB": mib, **sample})
        assert 48 * 1024 * 1024 < calibration[1]["peakRssBytes"] - calibration[0]["peakRssBytes"] < 96 * 1024 * 1024
        cases = []
        for n in [1000, 10000, 100000]:
            inputs = routing(n)
            policy_path = work / f"routing-{n}-policy.json"
            policy_path.write_bytes(encoded(inputs["policy"]))
            for rejected in [False, True]:
                selected = copy.deepcopy(inputs)
                if rejected:
                    selected["graph"]["entities"].pop()
                label = f"routing-{n}-{'missing-endpoint' if rejected else 'valid'}"
                selected_graph = work / f"{label}-graph.json"
                selected_graph.write_bytes(encoded(selected["graph"]))
                over_limit = selected_graph.stat().st_size > LIMIT
                expectation = "controlled-input-limit-refusal" if over_limit else "rejected" if rejected else "viable"
                trials = []
                for _ in range(TRIALS):
                    sample, raw = measured([args.cli, "compile", selected_graph, policy_path, "--relation-pack",
                                            ROOT / "relation-packs/routing.json", "--as-of", AS_OF], work, env)
                    actual = json.loads(raw)
                    if over_limit:
                        assert sample["exitCode"] == 1 and any("INPUT_BYTE_LIMIT" in i["message"] for i in actual["issues"]), actual
                    else:
                        assert sample["exitCode"] == (1 if rejected else 0), actual
                        if rejected:
                            assert actual["status"] == "rejected", actual
                            assert any(i["code"] == "UNRESOLVED_ENDPOINT" for i in actual["issues"]), actual
                        else:
                            assert actual["documentType"] == "generation" and len(actual["activeMappings"]) == n, actual
                    sample["actualStatus"] = actual.get("status", "viable" if actual.get("documentType") == "generation" else None)
                    sample["findings"] = actual.get("issues", [])
                    trials.append(sample)
                cli_results.append({"name": label, "mappings": n, "expected": expectation,
                                    "graphPath": selected_graph.name, "graphBytes": selected_graph.stat().st_size,
                                    "graphDigest": digest(selected_graph.read_bytes()), "policyPath": policy_path.name,
                                    "samples": trials, "wallNanoseconds": distribution([s["wallNanoseconds"] for s in trials]),
                                    "peakRssBytes": distribution([s["peakRssBytes"] for s in trials])})
                if not over_limit:
                    cases.append(case(label, selected, "rejected" if rejected else "viable",
                                      "UNRESOLVED_ENDPOINT" if rejected else None))
            if n == 1000:
                deep = copy.deepcopy(inputs)
                authorities = [{"id": "urn:bench:authority:root", "concept": "urn:bench:command:0",
                                "source": "urn:bench:command:0", "facts": ["routing-identity", "signature"],
                                "mode": "canonical", "provenance": {"status": "declared", "assertedBy": "benchmark-owner"}}]
                parent = authorities[0]["id"]
                for depth in range(64):
                    identity = f"urn:bench:authority:delegation:{depth}"
                    authorities.append({"id": identity, "concept": "urn:bench:command:0", "source": "urn:bench:handler:0",
                                        "facts": ["routing-identity"], "mode": "delegated", "delegatedFrom": parent,
                                        "provenance": {"status": "declared", "assertedBy": "benchmark-owner"}})
                    parent = identity
                deep["graph"]["authorities"] = authorities
                cases.append(case("deep-delegation-64", deep, queries=[["urn:bench:command:0", "routing-identity", parent]] * 64))
        prepared = subprocess.run([args.driver, "prepare-branch"], env=env, capture_output=True, check=True)
        cases.append(json.loads(prepared.stdout))
        topology = json.loads((ROOT / "docs/acceptance/reference-topology.json").read_text())
        for identity, expected, code in [("original-controls", "viable", None),
                                         ("removed-route-page", "rejected", "TOPOLOGY_REQUIRED_RELATION_MISSING")]:
            captured = next(c["capture"] for c in topology["successor"] if c["id"] == identity)
            # The original controls predeclare these outcomes; no expected result is inferred from timing output.
            cases.append(case("topology-" + identity, captured["inputs"], expected, code))
        repair = json.loads((ROOT / "docs/acceptance/inspection-native.json").read_text())["repair"]["request"]
        cases.append(case("bounded-repair", repair["baseline"]["inputs"], "rejected", "UNRESOLVED_ENDPOINT", repair=repair))
        for value in cases:
            path = work / (value["name"] + "-case.json")
            path.write_bytes(encoded(value))
            sample, raw = measured([args.driver, path], work, env, deadline=180)
            assert sample["exitCode"] == 0, sample
            actual = json.loads(raw)
            assert actual["executor"] == engine["compiler"] and actual["expectedStatus"] == value["expectedStatus"]
            actual["wholeDriverProcess"] = sample
            phases = {phase for s in actual["samples"] for phase in s["phases"]}
            actual["phaseDistributionsNanoseconds"] = {phase: distribution([s["phases"][phase] for s in actual["samples"]]) for phase in sorted(phases)}
            results.append(actual)
            print(f"PASS {value['name']}: {value['expectedStatus']}, seven SDK samples", flush=True)
        content = 'import {z} from "zod"; export const Item=z.object({id:z.string(),count:z.number().int().nullable()});'
        receipt = {"path": "schemas/domain.ts", "digest": digest(content.encode()), "byteLength": len(content.encode())}
        request = {"schemaVersion": "0.1.0", "documentType": "adapter-request", "profile": "patamaps-workspace-draft-1",
                   "sourceId": "urn:bench:zod", "namespace": "bridge", "config": {"adapter": "typescript-zod", "roots": ["schemas"]},
                   "inputs": [{"receipt": receipt, "content": content}],
                   "invocationDigest": digest((ROOT / "adapters/metamap-process.mjs").read_bytes()),
                   "requestDigest": digest(encoded({"sourceId": "urn:bench:zod", "input": receipt}))}
        (work / "discovery-request.json").write_bytes(encoded(request))
        argv = [args.node, ROOT / "adapters/metamap-process.mjs", args.reference]
        for _ in range(TRIALS):
            sample, raw = measured(argv, work, env, stdin=encoded(request))
            actual = json.loads(raw)
            assert sample["exitCode"] == 0 and actual["requestDigest"] == request["requestDigest"] and actual["inputs"] == [receipt]
            assert actual["shard"]["entities"] and actual["shard"]["mappings"]
            sample["adapterVersion"] = actual["adapterVersion"]
            sample["entities"] = len(actual["shard"]["entities"])
            sample["mappings"] = len(actual["shard"]["mappings"])
            discovery.append(sample)
        with tarfile.open(args.output / "phase-inputs.tar.gz", "w:gz") as archive:
            for path in sorted(work.glob("*.json")):
                raw = path.read_bytes()
                inventory.append({"path": path.name, "bytes": len(raw), "digest": digest(raw)})
                archive.add(path, arcname=path.name)
    report = {"verifiedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seed": SEED, "trials": TRIALS,
              "host": platform.platform(), "architecture": platform.machine(), "engines": engine,
              "toolchain": subprocess.check_output([str(Path.home() / ".cargo/bin/rustc"), "-vV"], text=True),
              "processStartup": startup, "cliCompile": cli_results, "sdkCases": results,
              "discovery": {"scope": "Explicit TypeScript-Zod bridge process only; temporary source staging and provider parsing included; no Patamaps admission, process caching or dependency-closure attestation",
                            "nodeVersion": subprocess.check_output([args.node, "--version"], text=True).strip(),
                            "nodeBinaryBytes": args.node.stat().st_size, "nodeBinaryDigest": digest(args.node.read_bytes()),
                            "bridgeDigest": digest((ROOT / "adapters/metamap-process.mjs").read_bytes()),
                            "referenceHead": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.reference, text=True).strip(),
                            "samples": discovery, "wallNanoseconds": distribution([s["wallNanoseconds"] for s in discovery]),
                            "peakRssBytes": distribution([s["peakRssBytes"] for s in discovery])},
              "rssUnitCalibration": calibration, "footprint": footprint(args.cli, args.driver, args.output),
              "inputArchive": {"path": "phase-inputs.tar.gz", "digest": digest((args.output / "phase-inputs.tar.gz").read_bytes()),
                               "bytes": (args.output / "phase-inputs.tar.gz").stat().st_size, "inventory": inventory},
              "method": "Seven fresh CLI processes per control; filesystem caches are uncontrolled. Seven sequential SDK samples per case in one process, preceded by untimed decode and explicit identity warmup. Whole-process peak RSS includes fixture/setup/all warm trials, not per-phase allocations. wait4 observes each child independently. No Node in compiler/SDK PATH. Projection batch contains 32 distinct specs. Timers overlap only for aggregate capture/replay operations, so phase sums are not an end-to-end estimate.",
              "limits": "100k raw graphs exceed the 16 MiB ingress bound; these are controlled refusal timings, not successful capacity. Seven samples cannot establish tail latency. Discovery is one bounded adapter fixture; no TypeScript compiler timing baseline or Linux throughput was measured.",
              "comparison": "No Rust speed or memory advantage established; this is measurement coverage, with no performance optimization introduced."}
    (args.output / "phase-benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS: fixed input decisions, SDK phases, fresh CLI processes, explicit provider discovery, per-child RSS and retained footprint/input receipts.")


if __name__ == "__main__":
    main()
