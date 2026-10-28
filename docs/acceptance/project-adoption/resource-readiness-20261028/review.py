#!/usr/bin/env python3
"""Summarize bounded resource observations without attributing an earlier failure."""
import argparse, hashlib, json, re
from pathlib import Path

def need(value, message):
    if not value:
        raise RuntimeError(message)
def read(p):
    return json.loads(p.read_text())
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--records", type=Path, required=True)
    p.add_argument("--checkout", type=Path, required=True)
    o = p.parse_args()
    observed = read(o.records / "observation.json")
    samples = observed["samples"]
    need(len(samples) == 3 and 30 <= observed["elapsedSeconds"] <= 45,
         "Incomplete observation interval")
    need(observed["recursiveScan"] is False and observed["nativeWorkloadStarted"] is False,
         "Observation scope changed")
    need(observed["collectorCpuLimitSeconds"] == 2 and observed["nice"] == 10,
         "Observation limits changed")
    free = [s["freeBytes"][str(o.checkout)] for s in samples]
    need(all(isinstance(n, int) and n > 0 for n in free), "Missing free-space data")
    def counter(sample, name):
        match = re.search(r"^" + re.escape(name) + r":\s+(\d+)\.", sample["vmStat"], re.M)
        need(match is not None, "Missing VM counter")
        return int(match.group(1))
    counts = {name: counter(samples[-1], name) - counter(samples[0], name)
              for name in ["Swapins", "Swapouts", "Compressions", "Decompressions"]}
    known = [s["knownFiles"] for s in samples]
    need(all(len(k) == len(known[0]) for k in known), "Metadata coverage changed")
    stable = all(rows == known[0] for rows in known[1:])
    all_available = all("unavailable" not in row for row in known[0])
    cases = []
    final_data = None
    for name in ["capacity-check.json", "capacity-check-second.json", "capacity-check-observer-error.json", "capacity-check-final.json"]:
        raw = read(o.records / name)
        need(raw["command"] == "run-project.mjs patamaps check"
             and raw["qualificationStarted"] is False, "Wrong admission command")
        cases.append({key: raw.get(key) for key in
                      ["exitCode", "timedOut", "timeoutSeconds", "cpuLimitSeconds", "elapsedSeconds", "observerError"]})
        if name.endswith("final.json") and raw.get("exitCode") == 0:
            final_data = json.loads(raw["stdout"])
    status = read(o.records / "scheduler-status.json")
    result = {
        "status": "completed-bounded-resource-readiness-review",
        "observationSeconds": observed["elapsedSeconds"],
        "sampleCount": len(samples),
        "minimumAvailableBytesObserved": min(free),
        "maximumAvailableBytesObserved": max(free),
        "availableByteRange": max(free) - min(free),
        "netAvailableByteChange": free[-1] - free[0],
        "swapUsageUnchanged": len({s["swapUsage"] for s in samples}) == 1,
        "vmCounterDeltas": counts,
        "knownFileMetadataStable": stable,
        "allSelectedKnownFileMetadataAvailable": all_available,
        "selectedKnownFileCount": len(known[0]),
        "activeReservationsBeforeAdmissionCheck": len(status["active"]),
        "queuedReservationsBeforeAdmissionCheck": len(status["queued"]),
        "admissionChecks": cases,
        "admissionEstablished": final_data is not None,
        "earlierGrowthCauseEstablished": False,
        "futureResourceStabilityEstablished": False,
        "nativeMemoryBoundEstablished": False,
        "watchQualificationStarted": False,
        "qualificationAccepted": False,
        "filesDeleted": 0,
        "servicesStopped": 0,
        "policyChanged": False
    }
    if final_data:
        policy = final_data["policy"]
        need(policy["maximumRunGrowthBytes"] == 4000000000 and
             policy["reserveFreeBytes"] == 500000000 and
             policy["maximumRetainedBytes"] == 100000000000, "Policy changed")
        result.update({
            "admissionAvailableBytes": final_data["availableBytes"],
            "retainedAllocatedBytesUpperBound": final_data["retainedAllocatedBytesUpperBound"],
            "reservedGrowthBytes": policy["maximumRunGrowthBytes"],
            "remainingRetentionAfterReservationBytes": policy["maximumRetainedBytes"]
                 - final_data["retainedAllocatedBytesUpperBound"] - policy["maximumRunGrowthBytes"]
        })
        need(result["remainingRetentionAfterReservationBytes"] >= 0, "Reservation does not fit")
    else:
        final = read(o.records / "capacity-check-final.json")
        result["finalAdmissionError"] = final.get("stderr", "")[:1000]
    context = o.checkout / "crates/patamaps-workspace/src/project_context.rs"
    source = context.read_bytes()
    need(b"let mut buffer = [0u8; 65536];" in source,
         "Context-hasher source observation changed")
    result["sourceObservation"] = {
        "path": "crates/patamaps-workspace/src/project_context.rs",
        "sha256": hashlib.sha256(source).hexdigest(),
        "contextFileHasherBufferBytes": 65536,
        "wholeVerifierMemoryBoundEstablished": False
    }
    print(json.dumps(result, indent=2))
if __name__ == "__main__":
    main()
